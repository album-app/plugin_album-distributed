import argparse
import glob
import sys

from album.api import Album
from album.core.model.task import Task
from album.runner.core.api.model.solution import ISolution

from album.distributed import mode_basic
from album.distributed.reverse_glob import reverse_glob


def get_run_mode_choices():
    return ["basic"]


def run(album_instance: Album, args):
    mode = args.mode
    tasks = _generate_run_tasks(album_instance, args.solution, argv=sys.argv)
    if mode == "basic":
        mode_basic.run(album_instance, args, tasks)


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


def _generate_run_tasks(album_instance: Album, solution: str, argv):
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
            task._args = (solution, False, argv_copy)
            res.append(task)
    else:
        task = Task()
        task._method = task_method
        task._args = (solution, False, argv)
        res.append(task)
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
