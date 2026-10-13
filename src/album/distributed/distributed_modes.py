import sys

from album.api import Album

from album.distributed import mode_basic, mode_queue
from album.distributed.argument_matching import generate_run_tasks


def get_run_mode_choices():
    return ["basic", "queue"]


def run(album_instance: Album, args):
    mode = args.mode
    if mode not in get_run_mode_choices():
        raise ValueError('Unknown mode "%s". Choose one of: %s.' % (mode, ", ".join(get_run_mode_choices())))
    tasks = generate_run_tasks(album_instance, args.solution, argv=sys.argv)
    if mode == "basic":
        mode_basic.run(album_instance, args, tasks)
    elif mode == "queue":
        mode_queue.run(album_instance, args, tasks)
