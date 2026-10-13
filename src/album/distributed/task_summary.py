"""Summary of the outcome of the run tasks."""

from typing import List

from album.core.api.model.task import ITask
from album.distributed.argument_matching import get_task_argv
from album.runner.album_logging import get_active_logger


def describe_task(task: ITask) -> str:
    """Return the solution arguments of a run task as a single string."""
    argv = get_task_argv(task)
    description = " ".join(str(arg) for arg in argv[1:]) if argv else ""
    return description if description else "(no arguments)"


def log_summary(tasks: List[ITask]) -> List[ITask]:
    """Log how many tasks succeeded, failed or were not run and list the arguments of the failed tasks.

    Returns the failed tasks.
    """
    succeeded = [task for task in tasks if task.status() == ITask.Status.FINISHED]
    failed = [task for task in tasks if task.status() == ITask.Status.FAILED]
    not_run = len(tasks) - len(succeeded) - len(failed)
    summary = "Summary: %s of %s task(s) succeeded, %s failed" % (
        len(succeeded),
        len(tasks),
        len(failed),
    )
    if not_run:
        summary += ", %s not run" % not_run
    if failed:
        get_active_logger().error(summary + ".")
        for task in failed:
            get_active_logger().error(
                "Failed task with arguments: %s" % describe_task(task)
            )
    else:
        get_active_logger().info(summary + ".")
    return failed
