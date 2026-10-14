import sys

from album.api import Album

from album.distributed import mode_basic, mode_queue
from album.distributed.argument_matching import generate_run_tasks
from album.runner.album_logging import get_active_logger

_NOT_INSTALLED = 'Solution "%s" is not installed. Install it with "album install %s" or pass --install.'


def get_run_mode_choices():
    return ["basic", "queue"]


def run(album_instance: Album, args):
    mode = args.mode
    if mode not in get_run_mode_choices():
        raise ValueError('Unknown mode "%s". Choose one of: %s.' % (mode, ", ".join(get_run_mode_choices())))
    tasks = generate_run_tasks(album_instance, args.solution, argv=sys.argv)
    if tasks:
        install_if_needed(album_instance, args)
    if mode == "basic":
        mode_basic.run(album_instance, args, tasks)
    elif mode == "queue":
        mode_queue.run(album_instance, args, tasks)


def install_if_needed(album_instance: Album, args) -> None:
    """Make sure the solution is installed before the tasks run - like ``album run``, with ``--install`` it is
    installed if needed. A dry run only lists the tasks, so it does not need an installed solution."""
    solution = args.solution
    if album_instance.is_installed(solution):
        return
    install = getattr(args, "install", False)
    if getattr(args, "dry_run", False):
        if install:
            get_active_logger().info('Would install solution "%s" before running the tasks.' % solution)
        else:
            get_active_logger().warning(_NOT_INSTALLED % (solution, solution))
    elif install:
        album_instance.install(solution)
    else:
        raise LookupError(_NOT_INSTALLED % (solution, solution))
