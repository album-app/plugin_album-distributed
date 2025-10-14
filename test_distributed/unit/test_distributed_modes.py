import unittest.mock
from argparse import Namespace
from unittest import mock
from unittest.mock import patch

from album.api import Album
from album.core.api.model.collection_solution import ICollectionSolution

from album.distributed import distributed_modes
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


if __name__ == '__main__':
    unittest.main()
