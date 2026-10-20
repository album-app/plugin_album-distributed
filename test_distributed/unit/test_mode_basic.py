import unittest.mock
from argparse import Namespace

from album.core.api.model.task import ITask
from album.runner.album_logging import get_active_logger

from album.distributed import mode_basic
from album.distributed.argument_matching import create_run_task


class TestModeBasic(unittest.TestCase):

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
            mode_basic.run(None, Namespace(dry_run=False), self.tasks)

        self.assertEqual(
            [unittest.mock.call("solution.py", False, ["", "--input", "%s.tif" % name]) for name in "abc"],
            self.run_mock.call_args_list
        )
        self.assertEqual([ITask.Status.FINISHED] * 3, [task.status() for task in self.tasks])
        self.assertIn("Summary: 3 of 3 task(s) succeeded, 0 failed.", cm.output[-1])

    def test_run_dry_run(self):
        with self.assertLogs(get_active_logger(), level='INFO') as cm:
            mode_basic.run(None, Namespace(dry_run=True), self.tasks)

        self.run_mock.assert_not_called()
        self.assertEqual(3, len(cm.output))
        self.assertIn("Would run run with args ('solution.py', False, ['', '--input', 'a.tif'])..", cm.output[0])

    def test_run_stops_at_first_failure(self):
        self.run_mock.side_effect = [None, RuntimeError("solution failed"), None]

        with self.assertLogs(get_active_logger(), level='INFO') as cm:
            with self.assertRaises(RuntimeError) as error:
                mode_basic.run(None, Namespace(dry_run=False), self.tasks)

        # the original error is passed on to album's error handling
        self.assertEqual("solution failed", str(error.exception))
        # the third task is not run anymore
        self.assertEqual(2, self.run_mock.call_count)
        self.assertEqual(
            [ITask.Status.FINISHED, ITask.Status.FAILED, ITask.Status.UNDEFINED], [task.status() for task in self.tasks]
        )
        self.assertIn("ERROR", cm.output[-2])
        self.assertIn("Summary: 1 of 3 task(s) succeeded, 1 failed, 1 not run.", cm.output[-2])
        self.assertIn("Failed task with arguments: --input b.tif", cm.output[-1])


if __name__ == '__main__':
    unittest.main()
