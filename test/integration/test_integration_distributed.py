import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from unittest.mock import patch

from album.api import Album
from album.argument_parsing import main
from album.core.api.model.collection_solution import ICollectionSolution
from album.core.model.resolve_result import ResolveResult
from album.runner.album_logging import get_active_logger
from album.runner.core.api.model.solution import ISolution


class TestIntegrationExampleCommand(unittest.TestCase):

    @patch('album.argument_parsing.create_album_instance', return_value=mock.create_autospec(Album))
    def test_run_basic_dry_run(self, create_album_instance_mock):
        # mocks
        resolve_result = mock.create_autospec(ICollectionSolution)
        create_album_instance_mock.return_value.resolve.return_value = resolve_result
        run_mock = mock.MagicMock()
        run_mock.__name__ = "run-mock"
        create_album_instance_mock.return_value.run = run_mock
        resolve_result.coordinates.return_value = "my-group:my-solution:my-version"

        with self.assertLogs(get_active_logger(), level='INFO') as cm:
            # run
            sys.argv = ["", "run-distributed", "solution.py", "--dry-run"]
            self.assertIsNone(main())

            # assert
            self.assertEqual(2, len(cm.output))
            self.assertIn("contact via ", cm.output[0])
            self.assertIn("Would run run-mock with args (\'solution.py\', [\'\'], False)..", cm.output[1])

    @patch('album.argument_parsing.create_album_instance', return_value=mock.create_autospec(Album))
    def test_run_basic(self, create_album_instance_mock):
        # mocks
        resolve_result = mock.create_autospec(ICollectionSolution)
        create_album_instance_mock.return_value.resolve.return_value = resolve_result
        run_mock = mock.MagicMock()
        run_mock.__name__ = "run-mock"
        create_album_instance_mock.return_value.run = run_mock
        resolve_result.coordinates.return_value = "my-group:my-solution:my-version"

        with self.assertLogs(get_active_logger(), level='INFO') as cm:
            # run
            sys.argv = ["", "run-distributed", "solution.py"]
            self.assertIsNone(main())

            # assert
            self.assertEqual(2, len(cm.output))
            self.assertIn("contact via ", cm.output[0])
            self.assertIn("Running run-mock with args (\'solution.py\', [\'\'], False)..", cm.output[1])
            run_mock.assert_called_with("solution.py", [""], False)

    @patch('album.argument_parsing.create_album_instance', return_value=mock.create_autospec(Album))
    def test_run_basic_with_magic(self, create_album_instance_mock):
        # mocks
        collection_entry = mock.create_autospec(ICollectionSolution)
        solution_setup_args = [
            {"name": "input"},
            {"name": "output"},
            {"name": "other"}
        ]
        solution_setup = {
            "args": solution_setup_args
        }
        loaded_solution = mock.create_autospec(ISolution)
        loaded_solution.setup = mock.MagicMock(return_value=solution_setup)
        collection_entry.setup = mock.MagicMock(return_value=solution_setup)
        resolve_result = ResolveResult("", None, collection_entry, None, loaded_solution)
        create_album_instance_mock.return_value.resolve.return_value = resolve_result
        run_mock = mock.MagicMock()
        run_mock.__name__ = "run-mock"
        create_album_instance_mock.return_value.run = run_mock
        resolve_result.coordinates = mock.MagicMock(return_value="my-group:my-solution:my-version")

        with tempfile.TemporaryDirectory() as tmpdirname:
            tmpdir = Path(tmpdirname)
            inputfile1 = tmpdir.joinpath("input1.tif")
            inputfile2 = tmpdir.joinpath("bla", "input1.tif")
            outputfile1 = tmpdir.joinpath("output1.tif")
            outputfile2 = tmpdir.joinpath("bla", "output1.tif")
            inputfile2.parent.mkdir()
            inputfile1.touch()
            outputfile2.touch()
            input_pattern = str(tmpdir.joinpath("**", "input*.tif"))
            output_pattern = str(tmpdir.joinpath("**", "output*.tif"))

            with self.assertLogs(get_active_logger(), level='INFO') as cm:
                # run
                sys.argv = ["", "run-distributed", "solution.py", "--input", input_pattern, "--output", output_pattern,
                            "--other", "sun"]
                self.assertIsNone(main())

                # assert
                self.assertEqual(3, len(cm.output))
                self.assertIn("contact via ", cm.output[0])
                self.assertIn(
                    "Running run-mock with args (\'solution.py\', ['', '--input', \'%s\', '--output', \'%s\', '--other', 'sun'], False).." % (
                        str(inputfile1).replace('\\', '\\\\'), str(outputfile1).replace('\\', '\\\\')), cm.output[1])
                self.assertIn(
                    "Running run-mock with args (\'solution.py\', ['', '--input', \'%s\', '--output', \'%s\', '--other', 'sun'], False).." % (
                        str(inputfile2).replace('\\', '\\\\'), str(outputfile2).replace('\\', '\\\\')), cm.output[2])

    @patch('album.argument_parsing.create_album_instance', return_value=mock.create_autospec(Album))
    def test_run_queue(self, create_album_instance_mock):
        # mocks
        resolve_result = mock.create_autospec(ICollectionSolution)
        create_album_instance_mock.return_value.resolve.return_value = resolve_result
        run_mock = mock.MagicMock()
        run_mock.__name__ = "run-mock"
        create_album_instance_mock.return_value.run = run_mock
        resolve_result.coordinates.return_value = "my-group:my-solution:my-version"

        with self.assertLogs(get_active_logger(), level='INFO') as cm:
            # run
            sys.argv = ["", "run-distributed", "solution.py", "--mode", "queue", "--threads", "5"]
            self.assertIsNone(main())

            # assert
            self.assertEqual(6, len(cm.output))
            self.assertIn("contact via ", cm.output[0])
            self.assertIn("Running run-mock with args (\'solution.py\', [\'\'], False)..", cm.output[1])
            self.assertIn("Initializing 5 worker threads", cm.output[2])
            self.assertIn("registering task 0", cm.output[3])
            self.assertIn("starting task 0", cm.output[4])
            self.assertIn("finished task 0", cm.output[5])
            run_mock.assert_called_with("solution.py", [""], False)


if __name__ == '__main__':
    unittest.main()
