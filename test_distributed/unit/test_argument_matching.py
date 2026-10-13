import inspect
import os
import tempfile
import unittest.mock
from pathlib import Path
from unittest import mock
from unittest.mock import patch, MagicMock

from album.api import Album
from album.core.api.model.collection_solution import ICollectionSolution
from album.core.controller.run_manager import RunManager
from album.core.model.resolve_result import ResolveResult

from album.distributed.argument_matching import generate_run_tasks, get_all_combinations, set_arg_value
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

    def assert_run_task(self, task, solution, argv):
        """Check that the task calls the real RunManager.run with the given solution and argv."""
        self.assertIs(RunManager.run, task.method().__func__)
        # bind the task arguments to the real signature - mocking run would hide a wrong argument order
        bound = inspect.signature(RunManager.run).bind(None, *task.args()).arguments
        self.assertEqual(solution, bound["solution_to_resolve"])
        self.assertIs(False, bound["run_immediately"])
        self.assertEqual(argv, bound["argv"])

    def test__generate_run_tasks_no_magic(self):
        resolve_result = mock.create_autospec(ICollectionSolution)

        self.album.resolve = MagicMock(return_value=resolve_result)

        # single input, single output, no pattern
        argv = ["", "", "--input", "input.txt", "--output", "output.txt"]
        tasks = generate_run_tasks(self.album, "solution.py", argv)
        self.assertEqual(1, len(tasks))
        self.assert_run_task(tasks[0], "solution.py", ['', '', '--input', 'input.txt', '--output', 'output.txt'])

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
            self.assert_run_task(
                tasks[0], "solution.py", ['', '', '--input', str(inputfile1), '--output', str(outputfile1)]
            )
            self.assert_run_task(
                tasks[1], "solution.py", ['', '', '--input', str(inputfile2), '--output', str(outputfile2)]
            )

    def test__generate_run_tasks_with_magic_equals_syntax(self):
        collection_entry = mock.create_autospec(ICollectionSolution)
        solution_setup = {"args": [{"name": "input"}, {"name": "other"}]}
        loaded_solution = mock.create_autospec(ISolution)
        loaded_solution.setup = mock.MagicMock(return_value=solution_setup)
        collection_entry.setup = mock.MagicMock(return_value=solution_setup)
        resolve_result = ResolveResult("", None, collection_entry, None, loaded_solution)

        self.album.resolve = MagicMock(return_value=resolve_result)

        with tempfile.TemporaryDirectory() as tmpdirname:
            tmpdir = Path(tmpdirname)
            inputfile1 = tmpdir.joinpath("input1.tif")
            inputfile2 = tmpdir.joinpath("input2.tif")
            inputfile1.touch()
            inputfile2.touch()

            # --arg=value syntax has to be substituted as well, other arguments stay untouched
            input_pattern = str(tmpdir.joinpath("input*.tif"))
            argv = ["", "--input=%s" % input_pattern, "--other=sun"]
            tasks = generate_run_tasks(self.album, "solution.py", argv)
            self.assertEqual(2, len(tasks))
            self.assert_run_task(tasks[0], "solution.py", ["", "--input=%s" % inputfile1, "--other=sun"])
            self.assert_run_task(tasks[1], "solution.py", ["", "--input=%s" % inputfile2, "--other=sun"])
            # the original argv is not modified
            self.assertEqual(["", "--input=%s" % input_pattern, "--other=sun"], argv)

    def test_set_arg_value(self):
        argv = ["", "--input", "*.tif", "--output=*_out.tif", "--inputs", "x", "--input_b=y"]
        set_arg_value(argv, "input", "a.tif")
        set_arg_value(argv, "output", "a_out.tif")
        # arguments sharing a prefix with the replaced ones are not touched
        self.assertEqual(["", "--input", "a.tif", "--output=a_out.tif", "--inputs", "x", "--input_b=y"], argv)

    def test_set_arg_value_not_found(self):
        argv = ["", "--inp", "*.tif"]
        with self.assertRaises(ValueError):
            set_arg_value(argv, "input", "a.tif")
        self.assertEqual(["", "--inp", "*.tif"], argv)

    def test_get_all_combinations_native_separator(self):
        # glob returns paths with the native separator (backslashes on Windows), they still need to be paired by folder
        with tempfile.TemporaryDirectory() as tmpdirname:
            tmpdir = Path(tmpdirname)
            for folder in ["a", "b"]:
                tmpdir.joinpath(folder).mkdir()
                tmpdir.joinpath(folder, "input1.png").touch()
                tmpdir.joinpath(folder, "output1.png").touch()

            potential_list_args = {
                "input": os.path.join(str(tmpdir), "**", "input*.png"),
                "output": os.path.join(str(tmpdir), "**", "output*.png"),
            }
            res = list(get_all_combinations(potential_list_args, {}))
            self.assertEqual(
                [
                    {"input": str(tmpdir.joinpath(folder, "input1.png")),
                     "output": str(tmpdir.joinpath(folder, "output1.png"))}
                    for folder in ["a", "b"]
                ],
                res
            )

    def test_get_all_combinations_mixed_separators(self):
        # glob keeps the literal part of a pattern as written ("/") but joins the matches with the native separator, so
        # "<tmp>/*/a.png" and "<tmp>/sub/*.json" spell the same folder differently on Windows - still the same folder
        with tempfile.TemporaryDirectory() as tmpdirname:
            tmpdir = Path(tmpdirname)
            tmpdir.joinpath("sub").mkdir()
            tmpdir.joinpath("sub", "a.png").touch()
            tmpdir.joinpath("sub", "a.json").touch()

            potential_list_args = {
                "input": tmpdirname + "/*/a.png",
                "output": tmpdirname + "/sub/*.json",
            }
            res = list(get_all_combinations(potential_list_args, {}))
            self.assertEqual(1, len(res))
            self.assertEqual(os.path.normpath(tmpdir.joinpath("sub", "a.png")), os.path.normpath(res[0]["input"]))
            self.assertEqual(os.path.normpath(tmpdir.joinpath("sub", "a.json")), os.path.normpath(res[0]["output"]))

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
