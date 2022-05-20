from typing import List

from album.api import Album
from album.core.api.model.task import ITask
from album.runner.album_logging import get_active_logger


def run(_: Album, args, tasks: List[ITask]):
    if args.dry_run:
        for task in tasks:
            get_active_logger().info("Would run %s with args %s.." % (task.method().__name__, task.args()))
    else:
        for task in tasks:
            get_active_logger().info("Running %s with args %s.." % (task.method().__name__, task.args()))
            task.method()(*task.args())
