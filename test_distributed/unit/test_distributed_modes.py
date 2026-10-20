import unittest.mock
from argparse import Namespace
from unittest import mock
from unittest.mock import patch

from album.api import Album
from album.core.api.model.collection_solution import ICollectionSolution

from album.distributed import distributed_modes
from album.runner.album_logging import get_active_logger
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from unittest.mock import patch, MagicMock


class TestDistributedModes(unittest.TestCase):


    def setUp(self) -> None:
        super().setUp()
        self.album = None
        self.setup_tmp_resources()
        self.setup_album_instance()
        self.setup_collection(init_catalogs=False, init_collection=True)
        # the mocked solutions count as installed, the tests of a not installed solution override this
        self.album.is_installed = MagicMock(return_value=True)
        self.album.install = MagicMock()

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


    @patch('album.distributed.distributed_modes.mode_basic.run')
    def test_run_basic(self, run_mock):
        resolve_result = mock.create_autospec(ICollectionSolution)
        resolve_result.coordinates.return_value = "my-group:my-solution:my-version"
        self.album.resolve = MagicMock(return_value=resolve_result)
        distributed_modes.run(self.album, Namespace(solution='solution.py', mode='basic'))

        run_mock.assert_called_once()

    @patch('album.distributed.distributed_modes.mode_basic.run')
    @patch('album.distributed.distributed_modes.mode_queue.run')
    def test_run_queue(self, run_queue_mock, run_basic_mock):
        resolve_result = mock.create_autospec(ICollectionSolution)
        resolve_result.coordinates.return_value = "my-group:my-solution:my-version"
        self.album.resolve = MagicMock(return_value=resolve_result)
        with patch.object(sys, "argv", [""]):
            distributed_modes.run(self.album, Namespace(solution='solution.py', mode='queue'))

        run_queue_mock.assert_called_once()
        run_basic_mock.assert_not_called()

    @patch('album.distributed.distributed_modes.generate_run_tasks')
    def test_run_unknown_mode(self, generate_run_tasks_mock):
        with self.assertRaises(ValueError):
            distributed_modes.run(self.album, Namespace(solution='solution.py', mode='bogus'))
        generate_run_tasks_mock.assert_not_called()

    @patch('album.distributed.distributed_modes.mode_basic.run')
    @patch('album.distributed.distributed_modes.generate_run_tasks', return_value=[MagicMock()])
    def test_run_not_installed(self, _, run_mock):
        self.album.is_installed = MagicMock(return_value=False)
        with self.assertRaises(LookupError) as context:
            distributed_modes.run(self.album, Namespace(solution='solution.py', mode='basic', dry_run=False,
                                                        install=False))
        self.assertEqual(
            'Solution "solution.py" is not installed. Install it with "album install solution.py" or pass --install.',
            str(context.exception)
        )
        self.album.install.assert_not_called()
        run_mock.assert_not_called()

    @patch('album.distributed.distributed_modes.mode_basic.run')
    @patch('album.distributed.distributed_modes.generate_run_tasks', return_value=[MagicMock()])
    def test_run_install(self, _, run_mock):
        self.album.is_installed = MagicMock(return_value=False)
        # the solution is installed before the tasks run
        self.album.install.side_effect = lambda solution: run_mock.assert_not_called()
        distributed_modes.run(self.album, Namespace(solution='solution.py', mode='basic', dry_run=False,
                                                    install=True))
        self.album.install.assert_called_once_with('solution.py')
        run_mock.assert_called_once()

    @patch('album.distributed.distributed_modes.mode_basic.run')
    @patch('album.distributed.distributed_modes.generate_run_tasks', return_value=[MagicMock()])
    def test_run_install_already_installed(self, _, run_mock):
        distributed_modes.run(self.album, Namespace(solution='solution.py', mode='basic', dry_run=False,
                                                    install=True))
        self.album.install.assert_not_called()
        run_mock.assert_called_once()

    @patch('album.distributed.distributed_modes.mode_basic.run')
    @patch('album.distributed.distributed_modes.generate_run_tasks', return_value=[MagicMock()])
    def test_run_dry_run_not_installed(self, _, run_mock):
        self.album.is_installed = MagicMock(return_value=False)
        # the dry run lists the tasks and points out that the solution has to be installed
        with self.assertLogs(get_active_logger(), level='WARNING') as cm:
            distributed_modes.run(self.album, Namespace(solution='solution.py', mode='basic', dry_run=True,
                                                        install=False))
        self.assertIn('Solution "solution.py" is not installed.', cm.output[0])
        self.album.install.assert_not_called()
        run_mock.assert_called_once()

    @patch('album.distributed.distributed_modes.mode_basic.run')
    @patch('album.distributed.distributed_modes.generate_run_tasks', return_value=[MagicMock()])
    def test_run_dry_run_install(self, _, run_mock):
        self.album.is_installed = MagicMock(return_value=False)
        # the dry run does not install the solution
        with self.assertLogs(get_active_logger(), level='INFO') as cm:
            distributed_modes.run(self.album, Namespace(solution='solution.py', mode='basic', dry_run=True,
                                                        install=True))
        self.assertIn('Would install solution "solution.py" before running the tasks.', cm.output[0])
        self.album.install.assert_not_called()
        run_mock.assert_called_once()

    @patch('album.distributed.distributed_modes.mode_basic.run')
    @patch('album.distributed.distributed_modes.generate_run_tasks', return_value=[])
    def test_run_no_tasks_not_installed(self, _, run_mock):
        # without tasks nothing runs, so the solution does not have to be installed
        self.album.is_installed = MagicMock(return_value=False)
        distributed_modes.run(self.album, Namespace(solution='solution.py', mode='basic', dry_run=False,
                                                    install=False))
        self.album.install.assert_not_called()
        run_mock.assert_called_once()

    def test_get_run_mode_choices(self):
        self.assertEqual(["basic", "queue"], distributed_modes.get_run_mode_choices())


if __name__ == '__main__':
    unittest.main()
