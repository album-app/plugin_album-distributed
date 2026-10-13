import contextlib
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
from album.runner.album_logging import get_active_logger
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

    def mock_solution(self, *args):
        """Let album resolve a solution with the given arguments (names of untyped arguments or argument dicts)."""
        collection_entry = mock.create_autospec(ICollectionSolution)
        solution_setup = {"args": [arg if isinstance(arg, dict) else {"name": arg} for arg in args]}
        loaded_solution = mock.create_autospec(ISolution)
        loaded_solution.setup = mock.MagicMock(return_value=solution_setup)
        collection_entry.setup = mock.MagicMock(return_value=solution_setup)
        self.album.resolve = MagicMock(return_value=ResolveResult("", None, collection_entry, None, loaded_solution))

    def generate_argvs(self, tmpdir, argv):
        """Generate the tasks in tmpdir (to use relative patterns like in the README) and return their argv."""
        with working_directory(tmpdir):
            tasks = generate_run_tasks(self.album, "solution.py", argv)
        for task in tasks:
            self.assertEqual("solution.py", task.args()[0])
            self.assertIs(False, task.args()[1])
        return [task.args()[2] for task in tasks]

    def test_readme_single_pattern(self):
        self.mock_solution("input_data")
        with tempfile.TemporaryDirectory() as tmpdir:
            touch(tmpdir, "a.tif", "b.tif", "c.png")
            argvs = self.generate_argvs(tmpdir, ["", "--input_data", "*.tif"])
        self.assertEqual([["", "--input_data", "a.tif"], ["", "--input_data", "b.tif"]], argvs)

    def test_readme_single_pattern_folder(self):
        self.mock_solution("input_data")
        with tempfile.TemporaryDirectory() as tmpdir:
            data = os.path.join(tmpdir, "data")
            touch(data, "input1.tif", "input2.tif", "other.tif")
            argvs = self.generate_argvs(tmpdir, ["", "--input_data", data + "/input*.tif"])
        self.assertEqual(
            [["", "--input_data", os.path.join(data, "input%s.tif" % i)] for i in [1, 2]], argvs
        )

    def test_readme_single_pattern_recursive(self):
        self.mock_solution("input_data")
        with tempfile.TemporaryDirectory() as tmpdir:
            touch(tmpdir, "a.tif", os.path.join("sub", "b.tif"), os.path.join("sub", "deeper", "c.tif"))
            argvs = self.generate_argvs(tmpdir, ["", "--input_data", "**/*.tif"])
        self.assertEqual(
            [
                ["", "--input_data", "a.tif"],
                ["", "--input_data", os.path.join("sub", "b.tif")],
                ["", "--input_data", os.path.join("sub", "deeper", "c.tif")],
            ],
            argvs
        )

    def test_readme_derive_suffix(self):
        self.mock_solution("input_data", "output_data")
        with tempfile.TemporaryDirectory() as tmpdir:
            touch(tmpdir, "a.tif", "b.tif")
            argvs = self.generate_argvs(tmpdir, ["", "--input_data", "*.tif", "--output_data", "*_out.tif"])
        self.assertEqual(
            [
                ["", "--input_data", "a.tif", "--output_data", "a_out.tif"],
                ["", "--input_data", "b.tif", "--output_data", "b_out.tif"],
            ],
            argvs
        )

    def test_readme_derive_suffix_recursive(self):
        self.mock_solution("input_data", "output_data")
        with tempfile.TemporaryDirectory() as tmpdir:
            touch(tmpdir, "a.tif", os.path.join("sub", "b.tif"))
            argvs = self.generate_argvs(tmpdir, ["", "--input_data", "**/*.tif", "--output_data", "**/*_out.tif"])
        self.assertEqual(
            [
                ["", "--input_data", "a.tif", "--output_data", "a_out.tif"],
                ["", "--input_data", os.path.join("sub", "b.tif"), "--output_data", os.path.join("sub", "b_out.tif")],
            ],
            argvs
        )

    def test_readme_derive_output_folder(self):
        self.mock_solution("input_data", "output_data")
        with tempfile.TemporaryDirectory() as tmpdir:
            touch(tmpdir, "a.tif", "b.tif")
            argvs = self.generate_argvs(tmpdir, ["", "--input_data", "*.tif", "--output_data", "output/*.tif"])
        self.assertEqual(
            [
                ["", "--input_data", "a.tif", "--output_data", "output/a.tif"],
                ["", "--input_data", "b.tif", "--output_data", "output/b.tif"],
            ],
            argvs
        )

    def test_readme_derive_output_folder_recursive(self):
        self.mock_solution("input_data", "output_data")
        with tempfile.TemporaryDirectory() as tmpdir:
            touch(tmpdir, "a.tif", os.path.join("sub", "b.tif"))
            argvs = self.generate_argvs(tmpdir, ["", "--input_data=**/*.tif", "--output_data=output/**/*.tif"])
        self.assertEqual(
            [
                ["", "--input_data=a.tif", "--output_data=output/a.tif"],
                ["", "--input_data=" + os.path.join("sub", "b.tif"),
                 "--output_data=output/" + os.path.join("sub", "b.tif")],
            ],
            argvs
        )

    def test_readme_existing_outputs_correspond_by_name(self):
        self.mock_solution("input_data", "output_data")
        with tempfile.TemporaryDirectory() as tmpdir:
            # the outputs of a previous run exist - they also match the input pattern, but are not used as inputs
            touch(tmpdir, "a.tif", "b.tif", "a_out.tif", "b_out.tif")
            argvs = self.generate_argvs(tmpdir, ["", "--input_data", "*.tif", "--output_data", "*_out.tif"])
        self.assertEqual(
            [
                ["", "--input_data", "a.tif", "--output_data", "a_out.tif"],
                ["", "--input_data", "b.tif", "--output_data", "b_out.tif"],
            ],
            argvs
        )

    def test_existing_outputs_correspond_by_name_in_other_folder(self):
        self.mock_solution("input_data", "output_data")
        with tempfile.TemporaryDirectory() as tmpdir:
            touch(tmpdir, "a.tif", "b.tif", os.path.join("output", "a.tif"), os.path.join("output", "b.tif"))
            argvs = self.generate_argvs(tmpdir, ["", "--input_data", "**/*.tif", "--output_data", "output/*.tif"])
        self.assertEqual(
            [
                ["", "--input_data", "a.tif", "--output_data", os.path.join("output", "a.tif")],
                ["", "--input_data", "b.tif", "--output_data", os.path.join("output", "b.tif")],
            ],
            argvs
        )

    def test_existing_outputs_partially(self):
        # e.g. the task for b.tif failed in the previous run - running the same command again processes b.tif, too
        self.mock_solution("input_data", "output_data")
        with tempfile.TemporaryDirectory() as tmpdir:
            touch(tmpdir, "a.tif", "b.tif", "a_out.tif")
            with self.assertLogs(get_active_logger(), level="WARNING") as cm:
                argvs = self.generate_argvs(tmpdir, ["", "--input_data", "*.tif", "--output_data", "*_out.tif"])
        self.assertEqual(
            [
                ["", "--input_data", "a.tif", "--output_data", "a_out.tif"],
                ["", "--input_data", "b.tif", "--output_data", "b_out.tif"],
            ],
            argvs
        )
        self.assertIn(
            "1 file(s) matched by --input_data have no existing counterpart for --output_data, "
            "using the derived value(s): b_out.tif",
            cm.output[0]
        )

    def test_existing_outputs_partially_in_other_folder(self):
        self.mock_solution("input_data", "output_data")
        with tempfile.TemporaryDirectory() as tmpdir:
            touch(
                tmpdir, os.path.join("images", "a.tif"), os.path.join("images", "b.tif"), os.path.join("out", "a.tif")
            )
            with self.assertLogs(get_active_logger(), level="WARNING"):
                argvs = self.generate_argvs(tmpdir, ["", "--input_data", "images/*.tif", "--output_data", "out/*.tif"])
        self.assertEqual(
            [
                ["", "--input_data", os.path.join("images", "a.tif"), "--output_data", os.path.join("out", "a.tif")],
                ["", "--input_data", os.path.join("images", "b.tif"), "--output_data", "out/b.tif"],
            ],
            argvs
        )

    def test_constant_argument(self):
        self.mock_solution("input_data", "output_dir")
        with tempfile.TemporaryDirectory() as tmpdir:
            touch(tmpdir, "a.tif", os.path.join("sub", "b.tif"))
            # a value without pattern is passed to every task, no matter if it exists or where it lives
            argvs = self.generate_argvs(tmpdir, ["", "--input_data", "**/*.tif", "--output_dir", "results/"])
            self.assertEqual(
                [
                    ["", "--input_data", "a.tif", "--output_dir", "results/"],
                    ["", "--input_data", os.path.join("sub", "b.tif"), "--output_dir", "results/"],
                ],
                argvs
            )
            other = tempfile.gettempdir()
            argvs = self.generate_argvs(tmpdir, ["", "--output_dir=%s" % other, "--input_data", "*.tif"])
            self.assertEqual([["", "--output_dir=%s" % other, "--input_data", "a.tif"]], argvs)

    def test_first_pattern_on_command_line_defines_tasks(self):
        # the solution declares output_data first, but input_data comes first on the command line
        self.mock_solution("output_data", "input_data")
        with tempfile.TemporaryDirectory() as tmpdir:
            touch(tmpdir, os.path.join("raw", "s1", "img.tif"), os.path.join("results", "s1.tif"))
            argvs = self.generate_argvs(
                tmpdir, ["", "--input_data", "raw/*/*.tif", "--output_data", "results/*.tif"]
            )
        self.assertEqual(
            [["", "--input_data", os.path.join("raw", "s1", "img.tif"),
              "--output_data", os.path.join("results", "s1.tif")]],
            argvs
        )

    def test_no_tasks_no_match(self):
        self.mock_solution("input_data")
        with tempfile.TemporaryDirectory() as tmpdir:
            touch(tmpdir, "a.png")
            with self.assertLogs(get_active_logger(), level="WARNING") as cm:
                argvs = self.generate_argvs(tmpdir, ["", "--input_data", "*.tif"])
        self.assertEqual([], argvs)
        self.assertIn(
            "No tasks generated: none of the patterns matches an existing file or folder: --input_data '*.tif'.",
            cm.output[0]
        )

    def test_no_tasks_not_derivable(self):
        self.mock_solution("input_data", "output_data")
        with tempfile.TemporaryDirectory() as tmpdir:
            touch(tmpdir, "a.tif")
            with self.assertLogs(get_active_logger(), level="WARNING") as cm:
                argvs = self.generate_argvs(tmpdir, ["", "--input_data", "*.tif", "--output_data", "out/*/*.tif"])
        self.assertEqual([], argvs)
        self.assertIn("No tasks generated: --output_data 'out/*/*.tif' does not match existing files", cm.output[0])

    def test_text_with_wildcard_characters(self):
        # values of string arguments that match no file and do not look like a path are no patterns
        self.mock_solution(
            {"name": "input_data", "type": "file"},
            {"name": "prompt", "type": "string"},
            {"name": "title"},
            {"name": "count", "type": "integer"},
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            touch(tmpdir, "a.tif", "b.tif")
            for text in ["Is this a cell?", "count cells in [nucleus]", "Sample [x]", "a*b"]:
                argv = ["", "--input_data", "*.tif", "--prompt", text, "--title", text, "--count", "*"]
                with self.assertLogs(get_active_logger(), level="INFO") as cm:
                    argvs = self.generate_argvs(tmpdir, argv)
                self.assertEqual(
                    [
                        ["", "--input_data", name, "--prompt", text, "--title", text, "--count", "*"]
                        for name in ["a.tif", "b.tif"]
                    ],
                    argvs
                )
                self.assertIn(
                    "--prompt '%s' matches no existing file and does not look like a path, passing it unchanged to "
                    "every task." % text,
                    "\n".join(cm.output)
                )
                self.assertNotIn("WARNING", "\n".join(cm.output))
            # text before the pattern of the input files
            argvs = self.generate_argvs(tmpdir, ["", "--prompt", "Is this a cell?", "--input_data", "*.tif"])
            self.assertEqual(
                [["", "--prompt", "Is this a cell?", "--input_data", name] for name in ["a.tif", "b.tif"]], argvs
            )
            # without any file pattern, the solution runs once
            argvs = self.generate_argvs(tmpdir, ["", "--prompt", "Is this a cell?"])
            self.assertEqual([["", "--prompt", "Is this a cell?"]], argvs)

    def test_derive_typed_arguments(self):
        self.mock_solution(
            {"name": "input_data", "type": "string"},
            {"name": "output_data", "type": "string"},
            {"name": "output_dir", "type": "directory"},
            {"name": "log", "type": "file"},
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            touch(tmpdir, "a.tif", "b.tif")
            # string arguments are derived if they look like a path, file and directory arguments in any case
            argvs = self.generate_argvs(
                tmpdir,
                ["", "--input_data", "*.tif", "--output_data", "*_out.tif", "--output_dir", "out_*", "--log", "log_*"]
            )
        self.assertEqual(
            [
                ["", "--input_data", "%s.tif" % name, "--output_data", "%s_out.tif" % name,
                 "--output_dir", "out_%s" % name, "--log", "log_%s" % name]
                for name in ["a", "b"]
            ],
            argvs
        )

    def test_no_tasks_first_pattern_does_not_match(self):
        # a typo in the input pattern must not lead to tasks derived from the existing outputs
        self.mock_solution("input_data", "output_data")
        with tempfile.TemporaryDirectory() as tmpdir:
            touch(
                tmpdir, os.path.join("images", "a.tif"), os.path.join("images", "b.tif"),
                os.path.join("out", "a.tif"), os.path.join("out", "b.tif"),
            )
            with self.assertLogs(get_active_logger(), level="WARNING") as cm:
                argvs = self.generate_argvs(tmpdir, ["", "--input_data", "imgs/*.tif", "--output_data", "out/*.tif"])
        self.assertEqual([], argvs)
        self.assertIn(
            "No tasks generated: the first pattern on the command line, --input_data 'imgs/*.tif', matches no "
            "existing file or folder.",
            cm.output[0]
        )

    def test_partially_overlapping_patterns(self):
        # "*1.tif" matches a part of the files of "a*.tif", but is not more specific - no file is dropped
        self.mock_solution("input_data", "reference")
        with tempfile.TemporaryDirectory() as tmpdir:
            touch(tmpdir, "a1.tif", "a2.tif", "b1.tif")
            argvs = self.generate_argvs(tmpdir, ["", "--input_data", "a*.tif", "--reference", "*1.tif"])
        self.assertEqual(
            [
                ["", "--input_data", input_data, "--reference", reference]
                for input_data in ["a1.tif", "a2.tif"]
                for reference in ["a1.tif", "b1.tif"]
            ],
            argvs
        )

    def test_more_specific_pattern(self):
        # the results of a previous run match the input pattern, too - they are not used as inputs
        self.mock_solution("input_data", "output_data")
        with tempfile.TemporaryDirectory() as tmpdir:
            touch(tmpdir, "a.tif", "a_out.tif")
            with self.assertLogs(get_active_logger(), level="INFO") as cm:
                argvs = self.generate_argvs(tmpdir, ["", "--input_data", "*.tif", "--output_data", "*_out.tif"])
        self.assertEqual([["", "--input_data", "a.tif", "--output_data", "a_out.tif"]], argvs)
        self.assertIn(
            "Not using 1 file(s) matched by --input_data that are also matched by a more specific pattern: a_out.tif",
            "\n".join(cm.output)
        )

    def test_no_tasks_nothing_corresponds(self):
        self.mock_solution("input_data", "mask")
        with tempfile.TemporaryDirectory() as tmpdir:
            touch(tmpdir, os.path.join("images", "a.tif"), os.path.join("masks", "x.png"))
            with self.assertLogs(get_active_logger(), level="INFO") as cm:
                argvs = self.generate_argvs(tmpdir, ["", "--input_data", "images/*.tif", "--mask", "masks/*.png"])
        self.assertEqual([], argvs)
        self.assertIn("pairing them by folder", cm.output[0])
        self.assertIn(
            "No tasks generated: none of the files matched by --input_data 'images/*.tif' has matching values for "
            "--mask.",
            cm.output[-1]
        )


class TestPatternMatching(unittest.TestCase):

    def test_get_all_combinations_no_patterns(self):
        res = list(get_all_combinations({"input": "a.tif", "output": None}, {"threads": "3"}))
        self.assertEqual([{"input": "a.tif", "output": None, "threads": "3"}], res)

    def test_get_all_combinations_derive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            touch(tmpdir, "a.tif", os.path.join("sub", "b.tif"))
            potential_list_args = {
                "input": os.path.join(tmpdir, "**", "*.tif"),
                "output": os.path.join(tmpdir, "out", "**", "*_out.tif"),
                "log": os.path.join(tmpdir, "log.txt"),
            }
            res = list(get_all_combinations(potential_list_args, {"something": "bla"}))
        self.assertEqual(
            [
                {
                    "input": os.path.join(tmpdir, "a.tif"),
                    "output": os.path.join(tmpdir, "out", "a_out.tif"),
                    "log": os.path.join(tmpdir, "log.txt"),
                    "something": "bla",
                },
                {
                    "input": os.path.join(tmpdir, "sub", "b.tif"),
                    "output": os.path.join(tmpdir, "out", "sub", "b_out.tif"),
                    "log": os.path.join(tmpdir, "log.txt"),
                    "something": "bla",
                },
            ],
            res
        )

    def test_get_all_combinations_pair_by_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # names correspond via the wildcards, the folders differ
            touch(
                tmpdir, os.path.join("images", "img_1.tif"), os.path.join("images", "img_2.tif"),
                os.path.join("labels", "lbl_2.png"), os.path.join("labels", "lbl_1.png"),
            )
            potential_list_args = {
                "image": os.path.join(tmpdir, "images", "img_*.tif"),
                "label": os.path.join(tmpdir, "labels", "lbl_*.png"),
            }
            res = list(get_all_combinations(potential_list_args, {}))
        self.assertEqual(
            [
                {"image": os.path.join(tmpdir, "images", "img_%s.tif" % i),
                 "label": os.path.join(tmpdir, "labels", "lbl_%s.png" % i)}
                for i in [1, 2]
            ],
            res
        )

    def test_get_all_combinations_pair_by_folder(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # names do not correspond - fall back to pairing the files of the same folder
            touch(
                tmpdir, os.path.join("s1", "img.tif"), os.path.join("s1", "meta.json"),
                os.path.join("s2", "img.tif"), os.path.join("s2", "meta.json"), os.path.join("s3", "img.tif"),
            )
            potential_list_args = {
                "image": os.path.join(tmpdir, "*", "*.tif"),
                "meta": os.path.join(tmpdir, "*", "*.json"),
            }
            with self.assertLogs(get_active_logger(), level="INFO") as cm:
                res = list(get_all_combinations(potential_list_args, {}))
        self.assertEqual(
            [
                {"image": os.path.join(tmpdir, s, "img.tif"), "meta": os.path.join(tmpdir, s, "meta.json")}
                for s in ["s1", "s2"]
            ],
            res
        )
        self.assertIn("pairing them by folder", cm.output[0])
        self.assertIn("Skipping 1 file(s) matched by --image without a matching value for --meta", cm.output[1])

    def test_get_all_combinations_duplicate_derived_values(self):
        # the tasks would overwrite each other's results: output/a.tif for s1/a.tif and s2/a.tif with "**",
        # output/s1.tif for s1/a.tif and s1/b.tif with "*/*.tif" (the n-th wildcard gets the text of the n-th wildcard)
        with tempfile.TemporaryDirectory() as tmpdir:
            touch(tmpdir, os.path.join("s1", "a.tif"), os.path.join("s1", "b.tif"), os.path.join("s2", "a.tif"))
            for input_pattern, output_pattern in [
                (os.path.join(tmpdir, "**", "*.tif"), os.path.join(tmpdir, "output", "*.tif")),
                (os.path.join(tmpdir, "*", "*.tif"), os.path.join(tmpdir, "output", "*.tif")),
            ]:
                potential_list_args = {"input": input_pattern, "output": output_pattern}
                with self.assertLogs(get_active_logger(), level="WARNING") as cm:
                    res = list(get_all_combinations(potential_list_args, {}))
                self.assertEqual([], res)
                self.assertIn(
                    "No tasks generated: several tasks would use the same value for --output and overwrite each "
                    "other's results: ",
                    cm.output[0]
                )

    def test_get_all_combinations_shared_derived_folder(self):
        # several tasks can write into the same folder
        with tempfile.TemporaryDirectory() as tmpdir:
            touch(tmpdir, os.path.join("s1", "a.tif"), os.path.join("s1", "b.tif"))
            input_pattern = os.path.join(tmpdir, "*", "*.tif")
            expected = [
                {"input": os.path.join(tmpdir, "s1", name), "output": os.path.join(tmpdir, "out", "s1") + os.sep}
                for name in ["a.tif", "b.tif"]
            ]
            output_pattern = os.path.join(tmpdir, "out", "*", "")
            res = list(get_all_combinations({"input": input_pattern, "output": output_pattern}, {}))
            self.assertEqual(expected, res)
            # an argument of type directory does not need the trailing separator
            res = list(
                get_all_combinations(
                    {"input": input_pattern, "output": os.path.join(tmpdir, "out", "*")}, {}, {"output": "directory"}
                )
            )
            self.assertEqual([dict(entry, output=entry["output"][:-1]) for entry in expected], res)


@contextlib.contextmanager
def working_directory(path):
    cwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(cwd)


def touch(folder, *names):
    for name in names:
        path = Path(folder).joinpath(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()


if __name__ == '__main__':
    unittest.main()
