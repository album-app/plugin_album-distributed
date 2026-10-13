"""Glob patterns that remember what their wildcards matched and can be filled with the matches of another pattern."""

import os
import re
from typing import List, Optional, Tuple

# separators in patterns and in the paths returned by glob - glob joins matches with "\\" on Windows
_SEPARATORS = "/\\" if os.sep == "\\" else "/"
_SEPARATOR_REGEX = re.compile("[%s]" % re.escape(_SEPARATORS))
_MAGIC_REGEX = re.compile(r"[*?[]")
_RECURSIVE = "**"
# glob matches case-insensitively where the file system is case-insensitive (Windows)
_FLAGS = re.IGNORECASE if os.path.normcase("A") == "a" else 0

# (sub folders matched by each "**" segment, text matched by each other wildcard)
Captures = Tuple[List[List[str]], List[str]]


def is_pattern(value) -> bool:
    """Check if an argument value is a glob pattern."""
    return isinstance(value, str) and _MAGIC_REGEX.search(value) is not None


class PathPattern:
    """A glob pattern, split into its literal leading folder and the path segments from the first wildcard on.

    ``capture`` returns what the wildcards matched in a path found by ``glob.glob(pattern, recursive=True)``,
    ``derive`` fills the wildcards of this pattern with the captures of another pattern:
    ``PathPattern("output/*_out.tif").derive(PathPattern("*.tif").capture("a.tif"))`` is ``output/a_out.tif``.
    """

    def __init__(self, pattern: str):
        """Split the pattern into its literal leading folder (``prefix``) and the ``segments`` after it."""
        self.pattern = pattern
        magic = _MAGIC_REGEX.search(pattern)
        first_wildcard = magic.start() if magic else len(pattern)
        prefix_end = (
            max(
                pattern.rfind(separator, 0, first_wildcard) for separator in _SEPARATORS
            )
            + 1
        )
        self.prefix = pattern[:prefix_end]
        self.segments = _split(pattern[prefix_end:])
        self.trailing_separator = bool(pattern) and pattern[-1] in _SEPARATORS

    def wildcard_count(self) -> int:
        """Return the number of wildcards (``*``, ``?``, ``[...]``) outside of ``**`` segments."""
        return sum(
            1
            for segment in self.segments
            if segment != _RECURSIVE
            for is_wildcard, _ in _tokenize(segment)
            if is_wildcard
        )

    def capture(self, path: str) -> Optional[Captures]:
        """Return what the wildcards matched in a path found by glob for this pattern, None if it does not match."""
        # glob keeps the literal leading folder as written, but drops its trailing separators
        prefix = self.prefix.rstrip(_SEPARATORS)
        if not path.startswith(prefix):
            return None
        start = len(prefix)
        return _match_segments(self.segments, _split(path[start:]))

    def derive(self, captures: Captures) -> Optional[str]:
        """Replace the wildcards of this pattern with the captures of another pattern.

        Each ``**`` segment is replaced by the sub folders matched by the corresponding ``**`` segment of the other
        pattern (or removed if there is none), each other wildcard by the text matched by the corresponding wildcard
        of the other pattern, in order. Returns None if this pattern has more wildcards than there are captures.
        """
        recursive, wildcards = list(captures[0]), list(captures[1])
        segments = []
        for segment in self.segments:
            if segment == _RECURSIVE:
                segments.extend(recursive.pop(0) if recursive else [])
                continue
            text = ""
            for is_wildcard, token in _tokenize(segment):
                if is_wildcard:
                    if not wildcards:
                        return None
                    text += wildcards.pop(0)
                else:
                    text += token
            segments.append(text)
        res = self.prefix + os.sep.join(segments)
        if self.trailing_separator and segments:
            res += os.sep
        return res


def _split(path: str) -> List[str]:
    # glob collapses repeated separators after the first wildcard
    return [segment for segment in _SEPARATOR_REGEX.split(path) if segment]


def _tokenize(segment: str) -> List[Tuple[bool, str]]:
    """Split a pattern segment into literal text and wildcards (``*``, ``?``, ``[...]``) as (is_wildcard, text)."""
    tokens: List[Tuple[bool, str]] = []
    literal = ""
    i, n = 0, len(segment)
    while i < n:
        token = None
        if segment[i] == "*":
            end = i
            while end < n and segment[end] == "*":
                end += 1
            token = "*"
        elif segment[i] == "?":
            token, end = "?", i + 1
        elif segment[i] == "[":
            end = i + 1
            if end < n and segment[end] == "!":
                end += 1
            if end < n and segment[end] == "]":
                end += 1
            while end < n and segment[end] != "]":
                end += 1
            if end < n:
                end += 1
                if end - i == 3 and segment[i + 1] != "!":
                    # a set with a single character is an escaped literal (see glob.escape), not a wildcard
                    literal += segment[i + 1]
                    i = end
                    continue
                token = segment[i:end]
        if token is None:
            literal += segment[i]
            i += 1
        else:
            if literal:
                tokens.append((False, literal))
                literal = ""
            tokens.append((True, token))
            i = end
    if literal:
        tokens.append((False, literal))
    return tokens


def _segment_regex(segment: str) -> str:
    """Translate a pattern segment like fnmatch, with one group per wildcard."""
    res = ""
    for is_wildcard, token in _tokenize(segment):
        if not is_wildcard:
            res += re.escape(token)
        elif token == "*":
            res += "(.*)"
        elif token == "?":
            res += "(.)"
        else:
            # escape characters with a special meaning in a regex set (like fnmatch does)
            chars = re.sub(r"([\\\[&~|])", r"\\\1", token[1:-1])
            if chars.startswith("!"):
                chars = "^" + chars[1:]
            elif chars.startswith("^"):
                chars = "\\" + chars
            res += "([%s])" % chars
    return res


def _match_segments(
    pattern_segments: List[str], path_segments: List[str]
) -> Optional[Captures]:
    if not pattern_segments:
        return ([], []) if not path_segments else None
    first, rest = pattern_segments[0], pattern_segments[1:]
    if first == _RECURSIVE:
        # "**" matches zero or more folders
        for count in range(len(path_segments) + 1):
            res = _match_segments(rest, path_segments[count:])
            if res is not None:
                return [path_segments[:count]] + res[0], res[1]
        return None
    if not path_segments:
        return None
    match = re.fullmatch(_segment_regex(first), path_segments[0], _FLAGS)
    if match is None:
        return None
    res = _match_segments(rest, path_segments[1:])
    if res is None:
        return None
    return res[0], list(match.groups()) + res[1]
