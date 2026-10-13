import unittest.mock
from argparse import Namespace

from album.core.api.model.task import ITask
from album.runner.album_logging import get_active_logger

from album.distributed import mode_queue
from album.distributed.argument_matching import create_run_task


class TestModeQueue(unittest.TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.run_mock = unittest.mock.MagicMock()
        self.run_mock.__name__ = "run"
        self.tasks = [
            create_run_task(self.run_mock, "solution.py", ["", "--input", "a.tif"]),
            create_run_task(self.run_mock, "solution.py", ["", "--input", "b.tif"]),
            create_run_task(self.run_mock, "solution.py", ["", "--input", "c.tif"]),
        ]

    def test_run(self):
        with self.assertLogs(get_active_logger(), level='INFO') as cm:
            mode_queue.run(None, Namespace(dry_run=False, threads=2), self.tasks)

        self.assertEqual(3, self.run_mock.call_count)
        for name in "abc":
            self.run_mock.assert_any_call("solution.py", False, ["", "--input", "%s.tif" % name])
        self.assertEqual([ITask.Status.FINISHED] * 3, [task.status() for task in self.tasks])
        self.assertIn("Summary: 3 of 3 task(s) succeeded, 0 failed.", cm.output[-1])

    def test_run_dry_run(self):
        with self.assertLogs(get_active_logger(), level='INFO') as cm:
            mode_queue.run(None, Namespace(dry_run=True, threads=2), self.tasks)

        self.run_mock.assert_not_called()
        self.assertEqual(3, len(cm.output))

    def test_run_failure(self):
        def run(solution, run_immediately, argv):
            if "b.tif" in argv:
                raise RuntimeError("solution failed")

        self.run_mock.side_effect = run

        with self.assertLogs(get_active_logger(), level='INFO') as cm:
            with self.assertRaises(RuntimeError) as error:
                mode_queue.run(None, Namespace(dry_run=False, threads=1), self.tasks)

        self.assertEqual("1 of 3 task(s) failed.", str(error.exception))
        # the other tasks are still processed
        self.assertEqual(3, self.run_mock.call_count)
        self.assertEqual(
            [ITask.Status.FINISHED, ITask.Status.FAILED, ITask.Status.FINISHED], [task.status() for task in self.tasks]
        )
        self.assertIn("ERROR", cm.output[-2])
        self.assertIn("Summary: 2 of 3 task(s) succeeded, 1 failed.", cm.output[-2])
        self.assertIn("Failed task with arguments: --input b.tif", cm.output[-1])


if __name__ == '__main__':
    unittest.main()
