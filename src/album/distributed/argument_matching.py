import argparse
import contextlib
import fnmatch
import glob
import os
import re

from album.api import Album
from album.core.model.task import Task
from album.runner.core.api.model.solution import ISolution


def generate_run_tasks(album_instance: Album, solution: str, argv):
    task_method = album_instance.run
    resolved_solution = album_instance.resolve(solution)
    args = __parse_args(resolved_solution.loaded_solution(), argv)[0]
    res = []
    solution_args = resolved_solution.database_entry().setup()["args"]
    solution_args_dict = {}
    for solution_arg in solution_args:
        solution_args_dict[solution_arg["name"]] = solution_arg

    potential_list_args = {}
    singular_args = {}
    for arg, arg_val in args.__dict__.items():
        if arg in solution_args_dict:
            arg_type = solution_args_dict[arg]["type"] if "type" in solution_args_dict[arg] else None
            if not arg_type or (arg_type == "file" or arg_type == "directory" or arg_type == "string"):
                potential_list_args[arg] = arg_val
            else:
                singular_args[arg] = arg_val
        else:
            singular_args[arg] = arg_val
    if len(potential_list_args) > 0:
        for entries in _get_all_combinations(potential_list_args, singular_args):
            task = Task()
            task._method = task_method
            argv_copy = argv.copy()
            for arg_entry in entries:
                try:
                    arg_val_index = argv_copy.index("--%s" % arg_entry)
                    argv_copy[arg_val_index + 1] = entries[arg_entry]
                except ValueError:
                    pass
            task._args = (solution, argv_copy, False)
            res.append(task)
    else:
        task = Task()
        task._method = task_method
        task._args = (solution, argv, False)
        res.append(task)
    return res


def _get_all_combinations(potential_list_args, singular_args):
    list_args = []
    for arg_name in potential_list_args:
        try:
            if glob.has_magic(potential_list_args[arg_name]):
                list_args.append(arg_name)
            else:
                singular_args[arg_name] = potential_list_args[arg_name]
        except:
            singular_args[arg_name] = potential_list_args[arg_name]
    res = []
    if list_args:
        for arg_name in list_args:
            other_list_arg_names = [arg_match for arg_match in list_args if arg_match != arg_name]
            paths = [potential_list_args[arg_match] for arg_match in other_list_arg_names]
            for in_match, out_matches in reverse_glob(potential_list_args[arg_name], reverse_path=paths, recursive=True):
                entry_args = {arg_name: in_match}
                for index, out_name in enumerate(other_list_arg_names):
                    entry_args[out_name] = out_matches[index]
                for singular_arg_name in singular_args:
                    entry_args[singular_arg_name] = singular_args[singular_arg_name]
                res.append(entry_args)
    else:
        entry_args = {}
        for singular_arg_name in singular_args:
            entry_args[singular_arg_name] = singular_args[singular_arg_name]
        res.append(entry_args)
    return res


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


# FIXME the documentation is still from the original glob library

"""Filename globbing utility."""


def reverse_glob(pathname, *, recursive=False, reverse_path=[]):
    """Return a list of paths matching a pathname pattern.

    The pattern may contain simple shell-style wildcards a la
    fnmatch. However, unlike fnmatch, filenames starting with a
    dot are special cases that are not matched by '*' and '?'
    patterns.

    If recursive is true, the pattern '**' will match any files and
    zero or more directories and subdirectories.
    """
    return list(reverse_iglob(pathname, recursive=recursive, reverse_path=reverse_path))


def reverse_iglob(pathname, *, recursive=False, reverse_path=[]):
    """Return an iterator which yields the paths matching a pathname pattern.

    The pattern may contain simple shell-style wildcards a la
    fnmatch. However, unlike fnmatch, filenames starting with a
    dot are special cases that are not matched by '*' and '?'
    patterns.

    If recursive is true, the pattern '**' will match any files and
    zero or more directories and subdirectories.
    """
    it = _iglob(pathname, recursive, False, reverse_path)
    if recursive and _isrecursive(pathname):
        s = next(it)  # skip empty string
        assert not s
    return it


def _iglob(pathname, recursive, dironly, reverse_path):
    dirname, basename = os.path.split(pathname)
    reverse_dirname_basename_list = [os.path.split(r_path) for r_path in reverse_path]
    # if (not reverse_basename) and reverse_dirname:
    #     reverse_basename = reverse_dirname
    #     reverse_dirname = ""
    if not _has_magic(pathname):
        assert not dironly
        if basename:
            if os.path.lexists(pathname):
                yield pathname, reverse_path
        else:
            # Patterns ending with a slash should match only directories
            if os.path.isdir(dirname):
                yield pathname, reverse_path
        return
    if not dirname:
        if recursive and _isrecursive(basename):
            yield from _glob2(dirname, basename, dironly,
                              [r_dirname_basename[0] for r_dirname_basename in reverse_dirname_basename_list],
                              [r_dirname_basename[1] for r_dirname_basename in reverse_dirname_basename_list])
        else:
            yield from _glob1(dirname, basename, dironly,
                              [r_dirname_basename[0] for r_dirname_basename in reverse_dirname_basename_list],
                              [r_dirname_basename[1] for r_dirname_basename in reverse_dirname_basename_list])
        return
    # `os.path.split()` returns the argument itself as a dirname if it is a
    # drive or UNC path.  Prevent an infinite recursion if a drive or UNC path
    # contains magic characters (i.e. r'\\?\C:').
    if dirname != pathname and _has_magic(dirname):
        dirs = _iglob(dirname, recursive, True, [r_dirname_basename[0] for r_dirname_basename in reverse_dirname_basename_list])
    else:
        dirs = [(dirname, [r_dirname_basename[0] for r_dirname_basename in reverse_dirname_basename_list])]
    if _has_magic(basename):
        if recursive and _isrecursive(basename):
            glob_in_dir = _glob2
        else:
            glob_in_dir = _glob1
    else:
        glob_in_dir = _glob0
    for (dirname, reverse_dirname_basename) in dirs:
        for res in glob_in_dir(dirname, basename, dironly, reverse_dirname_basename, [r_dirname_basename[1] for r_dirname_basename in reverse_dirname_basename_list]):
            yield unpack_glob_in_dir(dirname, reverse_dirname_basename, res)


def unpack_glob_in_dir(dirname, reverse_dirname, res):
    name = res[0]
    revert_path = [try_construct_path(reverse_dirname[i], path) for i, path in enumerate(res[1])]
    return os.path.join(dirname, name), revert_path


def try_construct_path(dir, name):
    if dir is not None and name is not None:
        if dir:
            return os.path.join(dir, name)
        else:
            return name
    else:
        return None


# These 2 helper functions non-recursively glob inside a literal directory.
# They return a list of basenames.  _glob1 accepts a pattern while _glob0
# takes a literal basename (so it only has to check for its existence).

def _glob1(dirname, pattern, dironly, reverse_dirname, reverse_basename):
    names = _listdir(dirname, dironly)
    match = fnmatch.filter(names, pattern)
    all_reverse_matches = []
    for m in match:
        reverse_match = []
        for r_basename in reverse_basename:
            regex = pat_translate(pattern)
            pat = re.compile(regex)
            groups = pat.match(m).groups()
            reverse_name = str(r_basename)
            stars = reverse_name.count("*")
            if stars >= len(groups):
                reverse_result = replace_stars_with_groups(groups, reverse_name)
                reverse_match.append(reverse_result)
            else:
                reverse_match.append(None)
        all_reverse_matches.append(reverse_match)

    res = zip(match, all_reverse_matches)
    return res


def replace_stars_with_groups(groups, reverse_name):
    start_index = 0
    reverse_result = reverse_name
    for i, group in enumerate(groups):
        new_index = reverse_result.index("*")
        if new_index == len(reverse_result) - 1:
            reverse_result = reverse_result[start_index: new_index] + group
        else:
            reverse_result = reverse_result[start_index: new_index] + group + reverse_result[
                                                                              new_index + 1: len(reverse_result)]
    return reverse_result


def _glob0(dirname, basename, dironly, reverse_dirname, reverse_basename):
    if not basename:
        # `os.path.split()` returns an empty basename for paths ending with a
        # directory separator.  'q*x/' should match only directories.
        if os.path.isdir(dirname):
            return [basename], [reverse_basename]
    else:
        if os.path.lexists(os.path.join(dirname, basename)):
            return [basename], [reverse_basename]
    return []

# This helper function recursively yields relative pathnames inside a literal
# directory.

def _glob2(dirname, pattern, dironly, reverse_dirname, reverse_pattern):
    assert _isrecursive(pattern)
    yield pattern[:0], [r_pattern[:0] for r_pattern in reverse_pattern]
    yield from _rlistdir(dirname, dironly, reverse_dirname)

# If dironly is false, yields all file names inside a directory.
# If dironly is true, yields only directory names.
def _iterdir(dirname, dironly):
    if not dirname:
        if isinstance(dirname, bytes):
            dirname = bytes(os.curdir, 'ASCII')
        else:
            dirname = os.curdir
    try:
        with os.scandir(dirname) as it:
            for entry in it:
                try:
                    if not dironly or entry.is_dir():
                        yield entry.name
                except OSError:
                    pass
    except OSError:
        return

def _listdir(dirname, dironly):
    with contextlib.closing(_iterdir(dirname, dironly)) as it:
        return list(it)

# Recursively yields relative pathnames inside a literal directory.
def _rlistdir(dirname, dironly, reverse_dirname):
    names = _listdir(dirname, dironly)
    for x in names:
        yield x, [x for r in reverse_dirname]
        path = os.path.join(dirname, x) if dirname else x
        reverse_path = [os.path.join(r_dirname, x) if dirname else x for r_dirname in reverse_dirname]
        for y1, y2 in _rlistdir(path, dironly, reverse_path):
            yield os.path.join(x, y1), [os.path.join(x, _y2) for _y2 in y2]


magic_check = re.compile('([*?[])')
magic_check_bytes = re.compile(b'([*?[])')


def _has_magic(s):
    if isinstance(s, bytes):
        match = magic_check_bytes.search(s)
    else:
        match = magic_check.search(s)
    return match is not None


def _isrecursive(pattern):
    if isinstance(pattern, bytes):
        return pattern == b'**'
    else:
        return pattern == '**'


def pat_translate(pat):
    """Translate a shell PATTERN to a regular expression.

    There is no way to quote meta-characters.
    Hacked to add capture groups
    """
    i, n = 0, len(pat)
    res = ''
    while i < n:
        c = pat[i]
        i = i+1
        if c == '*':
            res = res + '(.*)'
        elif c == '?':
            res = res + '(.)'
        elif c == '[':
            j = i
            if j < n and pat[j] == '!':
                j = j+1
            if j < n and pat[j] == ']':
                j = j+1
            while j < n and pat[j] != ']':
                j = j+1
            if j >= n:
                res = res + '\\['
            else:
                stuff = pat[i:j].replace('\\','\\\\')
                i = j+1
                if stuff[0] == '!':
                    stuff = '^' + stuff[1:]
                elif stuff[0] == '^':
                    stuff = '\\' + stuff
                res = '%s([%s])' % (res, stuff)
        else:
            res = res + re.escape(c)
    return res + '\Z(?ms)'
