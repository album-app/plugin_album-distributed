import argparse
import os
from collections import Counter, defaultdict
import glob
import itertools
import re
from typing import Dict, List, Optional

from album.api import Album
from album.core.api.model.task import ITask
from album.core.model.task import Task

from album.runner.album_logging import get_active_logger
from album.runner.core.api.model.solution import ISolution

from album.distributed.path_pattern import PathPattern, is_pattern

# a file extension at the end of a value, like ".tif" in "*_out.tif"
_FILE_EXTENSION_REGEX = re.compile(r"\.[A-Za-z0-9]+$")


def generate_run_tasks(album_instance: Album, solution: str, argv):
    # the arguments are taken from the solution file - generating the tasks does not need an installed solution
    loaded_solution = album_instance.resolve(solution).loaded_solution()
    args = __parse_args(loaded_solution, argv)[0]
    run_method = album_instance._controller.run_manager().run
    res = []
    solution_args = loaded_solution.setup()["args"]
    solution_args_dict = {}
    for solution_arg in solution_args:
        solution_args_dict[solution_arg["name"]] = solution_arg

    # separate args into potential list args (file, directory, string) and singular args (int, float, bool, etc)
    potential_list_args = {}
    singular_args = {}
    arg_types = {}
    for arg, arg_val in args.__dict__.items():
        if arg in solution_args_dict:
            arg_type = solution_args_dict[arg]["type"] if "type" in solution_args_dict[arg] else None
            if not arg_type or (arg_type == "file" or arg_type == "directory" or arg_type == "string"):
                potential_list_args[arg] = arg_val
                arg_types[arg] = arg_type
            else:
                singular_args[arg] = arg_val
        else:
            singular_args[arg] = arg_val

    # generate all combinations of list args while keeping singular args constant
    if len(potential_list_args) > 0:
        # the first pattern on the command line defines the tasks
        potential_list_args = dict(sorted(potential_list_args.items(), key=lambda item: _arg_position(argv, item[0])))
        for entries in get_all_combinations(potential_list_args, singular_args, arg_types):
            argv_copy = argv.copy()
            for arg_entry in entries:
                if entries[arg_entry] != args.__dict__.get(arg_entry):
                    set_arg_value(argv_copy, arg_entry, entries[arg_entry])
            res.append(create_run_task(run_method, solution, argv_copy))
    else:
        # no list args, just run once
        res.append(create_run_task(run_method, solution, argv))
    return res


def create_run_task(run_method, solution: str, argv) -> Task:
    """Create a task calling ``RunManager.run(solution_to_resolve, run_immediately=False, argv=None)``.

    Task only supports positional arguments, so they have to follow the order of the run signature.
    """
    return Task(run_method, (solution, False, argv))


def get_task_argv(task: ITask):
    """Return the solution argv of a task created by ``create_run_task``."""
    return task.args()[2]


def set_arg_value(argv, arg_name: str, value) -> None:
    """Replace the value of ``--arg_name`` in argv (in place).

    Both ``--arg_name value`` and ``--arg_name=value`` are supported.
    """
    flag = "--%s" % arg_name
    found = False
    for i, token in enumerate(argv):
        if token == flag and i + 1 < len(argv):
            argv[i + 1] = str(value)
            found = True
        elif token.startswith(flag + "="):
            argv[i] = "%s=%s" % (flag, value)
            found = True
    if not found:
        raise ValueError(
            "Cannot set argument %s to %s: %s not found in %s. "
            "Please spell out the full argument name (%s VALUE or %s=VALUE)." % (flag, value, flag, argv, flag, flag)
        )


def get_all_combinations(potential_list_args, singular_args, arg_types: Optional[Dict[str, Optional[str]]] = None):
    """
    Yield one dict of argument values per task:
      - arguments without a pattern are constants and passed unchanged to every task,
      - one task is generated per file matched by the first pattern (in the order of potential_list_args, which is the
        order of the command line), it has to match existing files,
      - other patterns that match existing files are paired with it by corresponding names, or by folder if no names
        correspond,
      - patterns that match no existing file are derived from the matched file (e.g. ``*_out.tif``) if the argument
        is a file or directory or the value looks like a path, other values (e.g. ``Is this a cell?``) are passed
        unchanged,
      - all singular args are passed unchanged.

    ``arg_types`` maps the argument names to the types declared by the solution (missing or None: no type).
    """
    patterns = {arg: value for arg, value in potential_list_args.items() if is_pattern(value)}
    constants = {arg: value for arg, value in potential_list_args.items() if arg not in patterns}
    for pattern_values in (_match_patterns(patterns, arg_types or {}) if patterns else [{}]):
        entry = dict(constants)
        entry.update(pattern_values)
        entry.update(singular_args)
        yield entry


def _match_patterns(patterns: Dict[str, str], arg_types: Dict[str, Optional[str]]) -> List[Dict[str, str]]:
    """Return the values of the pattern arguments for each task."""
    matches = {arg: sorted(glob.glob(pattern, recursive=True), key=_sort_key) for arg, pattern in patterns.items()}
    # text like "Is this a cell?" contains wildcards, but is not meant as a pattern
    unchanged = {
        arg: pattern
        for arg, pattern in patterns.items()
        if not matches[arg] and not _is_derivable(pattern, arg_types.get(arg))
    }
    for arg, pattern in unchanged.items():
        get_active_logger().info(
            "--%s '%s' matches no existing file and does not look like a path, passing it unchanged to every task."
            % (arg, pattern)
        )
    path_patterns = {arg: pattern for arg, pattern in patterns.items() if arg not in unchanged}
    res = _match_path_patterns(path_patterns, matches, arg_types) if path_patterns else [{}]
    for entry in res:
        entry.update(unchanged)
    return res


def _match_path_patterns(
    patterns: Dict[str, str], matches: Dict[str, List[str]], arg_types: Dict[str, Optional[str]]
) -> List[Dict[str, str]]:
    existing = [arg for arg in patterns if matches[arg]]
    if not existing:
        _warn_no_tasks("none of the patterns matches an existing file or folder: %s." % _describe(patterns))
        return []
    primary, others = existing[0], existing[1:]
    first = next(iter(patterns))
    if first != primary:
        # do not derive the values of a mistyped input pattern from the files matched by e.g. the output pattern
        _warn_no_tasks(
            "the first pattern on the command line, --%s '%s', matches no existing file or folder. The tasks are "
            "generated for the files matched by the first pattern - check it for typos or put the pattern of the "
            "input files first." % (first, patterns[first])
        )
        return []
    derived = [arg for arg in patterns if not matches[arg]]
    path_patterns = {arg: PathPattern(pattern) for arg, pattern in patterns.items()}

    for arg in derived:
        if path_patterns[arg].wildcard_count() > path_patterns[primary].wildcard_count():
            _warn_no_tasks(
                "--%s '%s' does not match existing files and has more wildcards than --%s '%s', so its values "
                "cannot be derived from the files matched by --%s."
                % (arg, patterns[arg], primary, patterns[primary], primary)
            )
            return []

    # a file matched by the first pattern is not used if another pattern matches a part of its files,
    # e.g. "*.tif" also matches the "*_out.tif" files of a previous run
    primary_files = {_normalize(path) for path in matches[primary]}
    taken = set()
    for arg in others:
        files = {_normalize(path) for path in matches[arg]}
        if files < primary_files:
            taken |= files
    primary_values = [path for path in matches[primary] if _normalize(path) not in taken] or matches[primary]
    if len(primary_values) < len(matches[primary]):
        ignored = [path for path in matches[primary] if _normalize(path) in taken]
        get_active_logger().info(
            "Not using %s file(s) matched by --%s that are also matched by a more specific pattern: %s"
            % (len(ignored), primary, _shorten(ignored))
        )
    captures = {path: path_patterns[primary].capture(path) for path in primary_values}

    # pair other patterns matching existing files by corresponding names, fall back to pairing by folder
    by_name: Dict[str, Dict[str, str]] = {}
    by_folder: Dict[str, Dict[str, List[str]]] = {}
    for arg in others:
        existing_values = {_normalize(path): path for path in matches[arg]}
        corresponding: Dict[str, str] = {}
        not_existing: Dict[str, str] = {}
        for path in primary_values:
            path_captures = captures[path]
            value = path_patterns[arg].derive(path_captures) if path_captures is not None else None
            if value is None:
                continue
            if _normalize(value) in existing_values:
                corresponding[path] = existing_values[_normalize(value)]
            else:
                not_existing[path] = value
        if corresponding:
            # files without counterpart get the derived value, like the files of a pattern that matches no file -
            # running the same command again after some tasks failed processes the files of the failed tasks, too
            corresponding.update(not_existing)
            by_name[arg] = corresponding
            if not_existing:
                get_active_logger().warning(
                    "%s file(s) matched by --%s have no existing counterpart for --%s, using the derived value(s): %s"
                    % (len(not_existing), primary, arg, _shorten(list(not_existing.values())))
                )
        else:
            get_active_logger().info(
                "The names of the files matched by --%s do not correspond to the files matched by --%s, "
                "pairing them by folder." % (arg, primary)
            )
            by_folder[arg] = defaultdict(list)
            for path in matches[arg]:
                by_folder[arg][_folder(path)].append(path)

    res: List[Dict[str, str]] = []
    skipped: Dict[tuple, List[str]] = defaultdict(list)
    for path in primary_values:
        values = {primary: path}
        missing: List[str] = []
        for arg in by_name:
            if path in by_name[arg]:
                values[arg] = by_name[arg][path]
            else:
                missing.append(arg)
        missing += [arg for arg in by_folder if not by_folder[arg].get(_folder(path))]
        path_captures = captures[path]
        for arg in derived:
            value = path_patterns[arg].derive(path_captures) if path_captures is not None else None
            if value is not None:
                values[arg] = value
            else:
                missing.append(arg)
        if missing:
            skipped[tuple(missing)].append(path)
            continue
        folder_args = list(by_folder)
        for combination in itertools.product(*(by_folder[arg][_folder(path)] for arg in folder_args)):
            entry = dict(values)
            entry.update(zip(folder_args, combination, strict=True))
            res.append(entry)

    for missing_args, paths in skipped.items():
        get_active_logger().warning(
            "Skipping %s file(s) matched by --%s without a matching value for %s: %s"
            % (len(paths), primary, ", ".join("--%s" % arg for arg in missing_args), _shorten(paths))
        )
    for arg in derived:
        values_count = Counter(_normalize(entry[arg]) for entry in res)
        duplicates = sorted({entry[arg] for entry in res if values_count[_normalize(entry[arg])] > 1})
        if not duplicates:
            continue
        if arg_types.get(arg) == "directory" or path_patterns[arg].trailing_separator:
            # several tasks writing into the same folder is fine
            get_active_logger().info("Several tasks use the same folder for --%s: %s" % (arg, _shorten(duplicates)))
        else:
            _warn_no_tasks(
                "several tasks would use the same value for --%s and overwrite each other's results: %s. The n-th "
                "wildcard of --%s '%s' is replaced by the text matched by the n-th wildcard of --%s '%s' - use a "
                "pattern that keeps the parts that differ (e.g. '**' for the sub folders)."
                % (arg, _shorten(duplicates), arg, patterns[arg], primary, patterns[primary])
            )
            return []
    if not res:
        _warn_no_tasks(
            "none of the files matched by --%s '%s' has matching values for %s."
            % (primary, patterns[primary], ", ".join("--%s" % arg for arg in patterns if arg != primary))
        )
    return res


def _is_derivable(pattern: str, arg_type: Optional[str]) -> bool:
    """Check if the values of a pattern that matches no file can be derived from the files matched by another pattern.

    That is the case for file and directory arguments and for values that look like a path - with a folder
    (``output/*.tif``) or a file extension (``*_out.tif``). Text like ``Is this a cell?`` is passed unchanged.
    """
    if arg_type in ("file", "directory"):
        return True
    return "/" in pattern or os.sep in pattern or _FILE_EXTENSION_REGEX.search(pattern) is not None


def _warn_no_tasks(reason: str) -> None:
    get_active_logger().warning("No tasks generated: %s" % reason)


def _describe(patterns: Dict[str, str]) -> str:
    return ", ".join("--%s '%s'" % (arg, pattern) for arg, pattern in patterns.items())


def _shorten(paths: List[str], limit: int = 5) -> str:
    return ", ".join(paths[:limit]) + (", ..." if len(paths) > limit else "")


def _normalize(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))


def _folder(path: str) -> str:
    return os.path.normcase(os.path.dirname(os.path.normpath(path)))


def _sort_key(path: str):
    # files of a folder before the files of its sub folders
    return _folder(path), _normalize(path)


def _arg_position(argv, arg_name: str) -> int:
    """Return the index of ``--arg_name`` in argv, len(argv) if it is not given."""
    flag = "--%s" % arg_name
    for i, token in enumerate(argv):
        if token == flag or token.startswith(flag + "="):
            return i
    return len(argv)


# TODO this is copied from album.core.controller.script_manager and should be made available from there
def __parse_args(active_solution: ISolution, args: list):
    """Parse arguments of loaded solution."""
    parser = argparse.ArgumentParser()

    class FileAction(argparse.Action):
        def __init__(self, option_strings, dest, nargs=None, **kwargs):
            if nargs is not None:
                raise ValueError("nargs not allowed")
            super(FileAction, self).__init__(option_strings, dest, **kwargs)

        def __call__(self, p, namespace, values, option_string=None):
            setattr(namespace, self.dest, active_solution.get_arg(self.dest)['action'](values))

    for element in active_solution.setup()["args"]:
        if 'action' in element.keys():
            parser.add_argument("--" + element["name"], action=FileAction)
        else:
            parser.add_argument("--" + element["name"])

    return parser.parse_known_args(args=args)
