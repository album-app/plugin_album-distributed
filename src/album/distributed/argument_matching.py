import argparse
import os
from collections import defaultdict
import glob
import itertools
from album.api import Album
from album.core.model.task import Task

from album.runner.core.api.model.solution import ISolution


def generate_run_tasks(album_instance: Album, solution: str, argv):
    resolved_solution = album_instance.resolve(solution)
    args = __parse_args(resolved_solution.loaded_solution(), argv)[0]
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
            task = Task(album_instance._controller.run_manager().run)
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
        # no list args, just run once
        task = Task(album_instance._controller.run_manager().run)
        task._args = (solution, argv, False)
        res.append(task)
    return res


def expand_args(potential_list_args):
    """
    Expand glob patterns in potential_list_args into lists of file paths.
    Non-glob values become single-element lists.
    """
    expanded = {}
    for key, pattern in potential_list_args.items():
        if isinstance(pattern, str) and any(c in pattern for c in "*?["):
            expanded[key] = glob.glob(pattern, recursive=True)
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
        if all(isinstance(v, str) and ("/" in v or v.endswith(".tif")) for v in values):
            file_args[key] = values
        else:
            single_args[key] = values

    # Group file-like args by directory
    grouped = {arg: defaultdict(list) for arg in file_args}
    for arg, values in file_args.items():
        for v in values:
            folder = os.path.dirname(v)
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
