import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from unittest.mock import patch, MagicMock

from album.api import Album
from album.argument_parsing import main
from album.core.api.model.collection_solution import ICollectionSolution

from album.core.model.resolve_result import ResolveResult
from album.runner.album_logging import get_active_logger
from album.runner.core.api.model.solution import ISolution


class TestIntegrationExampleCommand(unittest.TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.album = None
        self.setup_tmp_resources()
        self.setup_album_instance()
        self.setup_collection(init_catalogs=False)

    def setup_tmp_resources(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.closed_tmp_file = tempfile.NamedTemporaryFile(delete=False)
        self.closed_tmp_file.close()

    def setup_collection(self, init_catalogs=True, init_collection=True):
        if init_catalogs:
            with patch(
                "album.core.model.configuration.Configuration.get_initial_catalogs"
            ) as get_initial_catalogs_mock:
                get_initial_catalogs_mock.return_value = {}

                # create collection
                self.album_controller.collection_manager().load_or_create()
        elif init_collection:
            with patch(
                "album.core.controller.collection.catalog_handler.CatalogHandler.add_initial_catalogs"
            ):
                self.album_controller.collection_manager().load_or_create()
        # check everything is freshly initialized
        self.assertTrue(
            self.album_controller.collection_manager().get_collection_index().is_empty()
        )

    def setup_album_instance(self):
        if self.album:
            raise AttributeError(
                "Only one instance of an Album should be used!"
                "Either use setup_album_instance or setup_album_controller!"
            )
        with patch("album.api.configure_root_logger"):
            self.album = (
                Album.Builder().base_cache_path(Path(self.tmp_dir.name)).build()
            )
        self.album_controller = self.album._controller
        self.album_patch = patch(
            "album.argument_parsing.create_album_instance", return_value=self.album
        )
        self.album_patch.start()

    def test_run_basic_dry_run(self):
        # mocks
        resolve_result = mock.create_autospec(ICollectionSolution)
        resolve_result.coordinates.return_value = "my-group:my-solution:my-version"
        self.album.resolve = MagicMock(return_value=resolve_result)

        run_mock = mock.MagicMock()
        run_mock.__name__ = "run-mock"
        self.album._controller.run_manager().run = run_mock

        with self.assertLogs(get_active_logger(), level='INFO') as cm:
            # run
            sys.argv = ["", "run-distributed", "solution.py", "--dry-run"]
            self.assertIsNone(main())

            # assert
            self.assertEqual(3, len(cm.output))
            self.assertIn("Would run run-mock with args (\'solution.py\', False, [\'\'])..", cm.output[2])

    def test_run_basic(self):
        # mocks
        resolve_result = mock.create_autospec(ICollectionSolution)
        resolve_result.coordinates.return_value = "my-group:my-solution:my-version"
        self.album.resolve = MagicMock(return_value=resolve_result)

        run_mock = mock.MagicMock()
        run_mock.__name__ = "run-mock"
        self.album._controller.run_manager().run = run_mock

        with self.assertLogs(get_active_logger(), level='INFO') as cm:
            # run
            sys.argv = ["", "run-distributed", "solution.py"]
            self.assertIsNone(main())

            # assert
            self.assertEqual(4, len(cm.output))
            self.assertIn("Summary: 1 of 1 task(s) succeeded, 0 failed.", cm.output[3])
            self.assertIn("Running run-mock with args (\'solution.py\', False, [\'\'])..", cm.output[2])
            run_mock.assert_called_with("solution.py", False, [""])

    def test_run_basic_with_magic(self):
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
        resolve_result.coordinates = mock.MagicMock()
        resolve_result.coordinates.return_value = "my-group:my-solution:my-version"
        self.album.resolve = MagicMock(return_value=resolve_result)

        run_mock = mock.MagicMock()
        run_mock.__name__ = "run-mock"
        self.album._controller.run_manager().run = run_mock

        with tempfile.TemporaryDirectory() as tmpdirname:
            tmpdir = Path(tmpdirname)
            inputfile1 = tmpdir.joinpath("input1.tif")
            inputfile2 = tmpdir.joinpath("bla", "input1.tif")
            outputfile1 = tmpdir.joinpath("output1.tif")
            outputfile2 = tmpdir.joinpath("bla", "output1.tif")
            inputfile2.parent.mkdir()
            inputfile1.touch()
            inputfile2.touch()
            outputfile1.touch()
            outputfile2.touch()
            input_pattern = str(tmpdir.joinpath("**", "input*.tif"))
            output_pattern = str(tmpdir.joinpath("**", "output*.tif"))

            with self.assertLogs(get_active_logger(), level='INFO') as cm:
                # run
                sys.argv = ["", "run-distributed", "solution.py", "--input", input_pattern, "--output", output_pattern,
                            "--other", "sun"]
                self.assertIsNone(main())

                # assert
                self.assertEqual(5, len(cm.output))
                self.assertIn("Summary: 2 of 2 task(s) succeeded, 0 failed.", cm.output[4])
                self.assertIn(
                    "Running run-mock with args (\'solution.py\', False, ['', '--input', \'%s\', '--output', \'%s\', '--other', 'sun']).." % (
                        str(inputfile1).replace('\\', '\\\\'), str(outputfile1).replace('\\', '\\\\')), cm.output[2])
                self.assertIn(
                    "Running run-mock with args (\'solution.py\', False, ['', '--input', \'%s\', '--output', \'%s\', '--other', 'sun']).." % (
                        str(inputfile2).replace('\\', '\\\\'), str(outputfile2).replace('\\', '\\\\')), cm.output[3])

    def test_run_basic_dry_run_derived_output(self):
        # mocks
        collection_entry = mock.create_autospec(ICollectionSolution)
        solution_setup = {"args": [{"name": "input_data"}, {"name": "output_data"}]}
        loaded_solution = mock.create_autospec(ISolution)
        loaded_solution.setup = mock.MagicMock(return_value=solution_setup)
        collection_entry.setup = mock.MagicMock(return_value=solution_setup)
        resolve_result = ResolveResult("", None, collection_entry, None, loaded_solution)
        resolve_result.coordinates = mock.MagicMock()
        resolve_result.coordinates.return_value = "my-group:my-solution:my-version"
        self.album.resolve = MagicMock(return_value=resolve_result)

        run_mock = mock.MagicMock()
        run_mock.__name__ = "run-mock"
        self.album._controller.run_manager().run = run_mock

        with tempfile.TemporaryDirectory() as tmpdirname:
            Path(tmpdirname).joinpath("a.tif").touch()
            Path(tmpdirname).joinpath("b.tif").touch()
            cwd = os.getcwd()
            os.chdir(tmpdirname)
            try:
                with self.assertLogs(get_active_logger(), level='INFO') as cm:
                    # run - the outputs do not exist yet and are derived from the inputs
                    sys.argv = ["", "run-distributed", "solution.py", "--input_data", "*.tif",
                                "--output_data", "output/*_out.tif", "--dry-run"]
                    self.assertIsNone(main())
            finally:
                os.chdir(cwd)

            # assert - the dry run lists the argv of each task
            run_mock.assert_not_called()
            self.assertEqual(4, len(cm.output))
            for i, name in enumerate(["a", "b"]):
                self.assertIn(
                    "Would run run-mock with args ('solution.py', False, "
                    "['', '--input_data', '%s.tif', '--output_data', 'output/%s_out.tif']).." % (name, name),
                    cm.output[2 + i]
                )

    def test_run_queue(self):
        # mocks
        resolve_result = mock.create_autospec(ICollectionSolution)
        resolve_result.coordinates.return_value = "my-group:my-solution:my-version"
        self.album.resolve = MagicMock(return_value=resolve_result)
        run_mock = mock.MagicMock()
        run_mock.__name__ = "run-mock"
        self.album._controller.run_manager().run = run_mock

        with self.assertLogs(get_active_logger(), level='INFO') as cm:
            # run
            sys.argv = ["", "run-distributed", "solution.py", "--mode", "queue", "--threads", "5"]
            self.assertIsNone(main())

            # assert
            self.assertEqual(8, len(cm.output))
            self.assertIn("Running run-mock with args (\'solution.py\', False, [\'\'])..", cm.output[2])
            self.assertIn("Initializing 5 worker threads", cm.output[3])
            self.assertIn("registering task 0", cm.output[4])
            self.assertIn("starting task 0", cm.output[5])
            self.assertIn("finished task 0", cm.output[6])
            self.assertIn("Summary: 1 of 1 task(s) succeeded, 0 failed.", cm.output[7])
            run_mock.assert_called_with("solution.py", False, [""])

    def test_run_queue_failure_exit_status(self):
        # mocks
        resolve_result = mock.create_autospec(ICollectionSolution)
        resolve_result.coordinates.return_value = "my-group:my-solution:my-version"
        self.album.resolve = MagicMock(return_value=resolve_result)
        run_mock = mock.MagicMock(side_effect=RuntimeError("solution failed"))
        run_mock.__name__ = "run-mock"
        self.album._controller.run_manager().run = run_mock

        with self.assertLogs(get_active_logger(), level='INFO') as cm:
            # run
            sys.argv = ["", "run-distributed", "solution.py", "--mode", "queue", "--threads", "1"]
            with self.assertRaises(SystemExit) as exit_context:
                main()

            # assert - the command fails instead of exiting with status 0
            self.assertNotEqual(0, exit_context.exception.code)
            self.assertIsNotNone(exit_context.exception.code)
            self.assertTrue(any("Summary: 0 of 1 task(s) succeeded, 1 failed." in line for line in cm.output))
            self.assertIn("album command failed: 1 of 1 task(s) failed.", cm.output[-1])


if __name__ == '__main__':
    unittest.main()
