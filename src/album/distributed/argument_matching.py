import argparse
import os
from collections import defaultdict
import glob
import itertools
from album.api import Album
from album.core.api.model.task import ITask
from album.core.model.task import Task

from album.runner.core.api.model.solution import ISolution


def generate_run_tasks(album_instance: Album, solution: str, argv):
    resolved_solution = album_instance.resolve(solution)
    args = __parse_args(resolved_solution.loaded_solution(), argv)[0]
    run_method = album_instance._controller.run_manager().run
    res = []
    solution_args = resolved_solution.database_entry().setup()["args"]
    solution_args_dict = {}
    for solution_arg in solution_args:
        solution_args_dict[solution_arg["name"]] = solution_arg

    # separate args into potential list args (file, directory, string) and singular args (int, float, bool, etc)
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

    # generate all combinations of list args while keeping singular args constant
    if len(potential_list_args) > 0:
        for entries in get_all_combinations(potential_list_args, singular_args):
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


def expand_args(potential_list_args):
    """
    Expand glob patterns in potential_list_args into lists of file paths.
    Non-glob values become single-element lists.
    """
    expanded = {}
    for key, pattern in potential_list_args.items():
        if isinstance(pattern, str) and any(c in pattern for c in "*?["):
            # sorted: glob order depends on the file system, keep task order deterministic
            expanded[key] = sorted(glob.glob(pattern, recursive=True))
        else:
            expanded[key] = [pattern]
    return expanded


def get_all_combinations(potential_list_args, singular_args):
    """
    Yield dicts that combine:
      - all list-args, grouped by directory if they are file paths
      - all single/fixed args
    """
    expanded = expand_args(potential_list_args)

    # Split args into "file-like" (look like paths) vs "always single"
    file_args, single_args = {}, {}
    for key, values in expanded.items():
        if all(isinstance(v, str) and (_has_path_separator(v) or v.endswith(".tif")) for v in values):
            file_args[key] = values
        else:
            single_args[key] = values

    # Group file-like args by directory
    grouped = {arg: defaultdict(list) for arg in file_args}
    for arg, values in file_args.items():
        for v in values:
            # glob keeps the literal part of a pattern as written and joins the matches with the native separator,
            # so the same folder can be spelled "data/sub" and "data\sub" on Windows
            folder = os.path.normcase(os.path.normpath(os.path.dirname(v)))
            grouped[arg][folder].append(v)

    # If no file args, just yield product of single args
    if not file_args:
        for combo in itertools.product(*(single_args[k] for k in single_args)):
            entry = dict(zip(single_args.keys(), combo))
            entry.update(singular_args)
            yield entry
        return

    # Consider only dirs that contain ALL file-args
    common_dirs = set.intersection(*(set(grouped[arg].keys()) for arg in grouped))

    for folder in sorted(common_dirs):
        keys = list(file_args.keys()) + list(single_args.keys())
        values = [grouped[arg][folder] for arg in file_args] + [single_args[arg] for arg in single_args]

        for combo in itertools.product(*values):
            entry = dict(zip(keys, combo))
            entry.update(singular_args)
            yield entry


def _has_path_separator(value: str) -> bool:
    """Check for "/" and os.sep, the separator glob uses to join the matched paths (a backslash on Windows)."""
    return "/" in value or os.sep in value


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
