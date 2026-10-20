from typing import List

from album.api import Album
from album.core.api.model.task import ITask
from album.distributed.task_summary import log_summary
from album.runner.album_logging import get_active_logger


def run(_: Album, args, tasks: List[ITask]):
    if args.dry_run:
        for task in tasks:
            get_active_logger().info("Would run %s with args %s.." % (task.method().__name__, task.args()))
    else:
        # stop at the first failing task
        for task in tasks:
            get_active_logger().info("Running %s with args %s.." % (task.method().__name__, task.args()))
            task.set_status(ITask.Status.RUNNING)
            try:
                task.method()(*task.args())
            except Exception:
                task.set_status(ITask.Status.FAILED)
                log_summary(tasks)
                raise
            task.set_status(ITask.Status.FINISHED)
        log_summary(tasks)
