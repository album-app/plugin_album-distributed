from typing import List

from album.api import Album
from album.core.api.model.task import ITask
from album.core.controller.task_manager import TaskManager
from album.distributed.task_summary import log_summary
from album.runner.album_logging import get_active_logger


def run(_: Album, args, tasks: List[ITask]):
    task_manager = TaskManager()
    task_manager.num_fetch_threads = args.threads
    if args.dry_run:
        for task in tasks:
            get_active_logger().info("Would run %s with args %s.." % (task.method().__name__, task.args()))
    else:
        for task in tasks:
            get_active_logger().info("Running %s with args %s.." % (task.method().__name__, task.args()))
            task_manager.register_task(task)
        task_manager.finish_tasks()
        failed = log_summary(tasks)
        if failed:
            raise RuntimeError("%s of %s task(s) failed." % (len(failed), len(tasks)))
