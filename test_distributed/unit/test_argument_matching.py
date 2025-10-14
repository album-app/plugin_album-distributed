import tempfile
import unittest.mock
from pathlib import Path
from unittest import mock
from unittest.mock import patch, MagicMock

from album.api import Album
from album.core.api.model.collection_solution import ICollectionSolution
from album.core.model.resolve_result import ResolveResult

from album.distributed.argument_matching import generate_run_tasks, get_all_combinations
from album.runner.core.api.model.solution import ISolution


class TestReverseGlob(unittest.TestCase):

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


    def test__generate_run_tasks_no_magic(self):
        resolve_result = mock.create_autospec(ICollectionSolution)

        self.album.resolve = MagicMock(return_value=resolve_result)

        # single input, single output, no pattern
        argv = ["", "", "--input", "input.txt", "--output", "output.txt"]
        tasks = generate_run_tasks(self.album, "solution.py", argv)
        self.assertEqual(1, len(tasks))
        self.assertEqual(['', '', '--input', 'input.txt', '--output', 'output.txt'], tasks[0].args()[1])

    def test__generate_run_tasks_with_magic(self):
        collection_entry = mock.create_autospec(ICollectionSolution)
        solution_setup_args = [
            {"name": "input"},
            {"name": "output"}
        ]
        solution_setup = {
            "args": solution_setup_args
        }
        loaded_solution = mock.create_autospec(ISolution)
        loaded_solution.setup = mock.MagicMock(return_value=solution_setup)
        collection_entry.setup = mock.MagicMock(return_value=solution_setup)
        resolve_result = ResolveResult("", None, collection_entry, None, loaded_solution)

        self.album.resolve = MagicMock(return_value=resolve_result)

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

            # both input and output matches files that exist and don't exist
            input_pattern = str(tmpdir.joinpath("**", "input*.tif"))
            output_pattern = str(tmpdir.joinpath("**", "output*.tif"))
            argv = ["", "", "--input", input_pattern, "--output", output_pattern]
            tasks = generate_run_tasks(self.album, "solution.py", argv)
            self.assertEqual(2, len(tasks))
            self.assertEqual(['', '', '--input', str(inputfile1), '--output', str(outputfile1)], tasks[0].args()[1])
            self.assertEqual(['', '', '--input', str(inputfile2), '--output', str(outputfile2)], tasks[1].args()[1])

    def test_get_all_combinations(self):
        with tempfile.TemporaryDirectory() as tmpdirname:
            tmpdir = Path(tmpdirname)
            inputfile1 = tmpdir.joinpath("input1.tif")
            inputfile2 = tmpdir.joinpath("bla", "input1.tif")
            outputfile1 = tmpdir.joinpath("output1.tif")
            outputfile2 = tmpdir.joinpath("bla", "output1.tif")
            inputfile1.touch()
            outputfile1.touch()
            outputfile2.parent.mkdir()
            outputfile2.touch()
            inputfile2.touch()

            potential_list_args = {
                "input": str(tmpdir.joinpath("**", "input*.tif")),
                "output": str(tmpdir.joinpath("**", "output*.tif"))
            }
            singular_args = {
                "something": "bla"
            }
            res = list(get_all_combinations(potential_list_args, singular_args))
            self.assertEqual(2, len(res))
            self.assertEqual(3, len(res[0]))
            self.assertEqual(3, len(res[1]))
            self.assertIn("input", res[0])
            self.assertIn("output", res[0])
            self.assertIn("something", res[0])
            self.assertEqual(str(inputfile1), res[0]["input"])
            self.assertEqual(str(outputfile1), res[0]["output"])
            self.assertEqual("bla", res[0]["something"])
            self.assertIn("input", res[1])
            self.assertIn("output", res[1])
            self.assertIn("something", res[1])
            self.assertEqual(str(inputfile2), res[1]["input"])
            self.assertEqual(str(outputfile2), res[1]["output"])
            self.assertEqual("bla", res[1]["something"])




if __name__ == '__main__':
    unittest.main()
