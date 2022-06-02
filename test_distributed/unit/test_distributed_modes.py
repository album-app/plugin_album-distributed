import unittest.mock
from argparse import Namespace
from unittest import mock
from unittest.mock import patch

from album.api import Album
from album.core.api.model.collection_solution import ICollectionSolution

from album.distributed import distributed_modes


class TestDistributedModes(unittest.TestCase):

    @patch('album.distributed.distributed_modes.mode_basic.run')
    def test_run_basic(self, run_mock):
        album = mock.create_autospec(Album)
        resolve_result = mock.create_autospec(ICollectionSolution)
        album.resolve.return_value = resolve_result
        resolve_result.coordinates.return_value = "my-group:my-solution:my-version"

        distributed_modes.run(album, Namespace(solution='solution.py', mode='basic'))

        run_mock.assert_called_once()


if __name__ == '__main__':
    unittest.main()
