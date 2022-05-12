import tempfile
import unittest.mock
from argparse import Namespace
from pathlib import Path
from unittest import mock
from unittest.mock import patch

from album.api import Album
from album.core.api.model.collection_solution import ICollectionSolution
from album.core.model.resolve_result import ResolveResult
from album.runner.core.api.model.solution import ISolution

from album.distributed import distributed_modes
from album.distributed.distributed_modes import _get_all_combinations


class TestDistributedModes(unittest.TestCase):

    @patch('album.distributed.distributed_modes.mode_basic.run')
    def test_run_basic(self, run_mock):
        album = mock.create_autospec(Album)
        resolve_result = mock.create_autospec(ICollectionSolution)
        album.resolve.return_value = resolve_result
        resolve_result.coordinates.return_value = "my-group:my-solution:my-version"

        distributed_modes.run(album, Namespace(solution='solution.py', mode='basic'))

        run_mock.assert_called_once()

    def test__generate_run_tasks_no_magic(self):
        album = mock.create_autospec(Album)
        resolve_result = mock.create_autospec(ICollectionSolution)
        album.resolve.return_value = resolve_result

        # single input, single output, no pattern
        argv = ["", "", "--input", "input.txt", "--output", "output.txt"]
        tasks = distributed_modes._generate_run_tasks(album, "solution.py", argv)
        self.assertEqual(1, len(tasks))
        self.assertEqual(['', '', '--input', 'input.txt', '--output', 'output.txt'], tasks[0].args()[2])

    def test__generate_run_tasks_with_magic(self):
        album = mock.create_autospec(Album)
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
        album.resolve.return_value = resolve_result

        with tempfile.TemporaryDirectory() as tmpdirname:
            tmpdir = Path(tmpdirname)
            inputfile1 = tmpdir.joinpath("input1.tif")
            inputfile2 = tmpdir.joinpath("bla", "input1.tif")
            outputfile1 = tmpdir.joinpath("output1.tif")
            outputfile2 = tmpdir.joinpath("bla", "output1.tif")
            inputfile2.parent.mkdir()
            inputfile1.touch()
            outputfile2.touch()
            # both input and output matches files that exist and don't exist
            input_pattern = str(tmpdir.joinpath("**", "input*.tif"))
            output_pattern = str(tmpdir.joinpath("**", "output*.tif"))
            argv = ["", "", "--input", input_pattern, "--output", output_pattern]
            tasks = distributed_modes._generate_run_tasks(album, "solution.py", argv)
            self.assertEqual(2, len(tasks))
            self.assertEqual(['', '', '--input', str(inputfile1), '--output', str(outputfile1)], tasks[0].args()[2])
            self.assertEqual(['', '', '--input', str(inputfile2), '--output', str(outputfile2)], tasks[1].args()[2])

    def test__get_all_combinations(self):
        with tempfile.TemporaryDirectory() as tmpdirname:
            tmpdir = Path(tmpdirname)
            inputfile1 = tmpdir.joinpath("input1.tif")
            inputfile2 = tmpdir.joinpath("bla", "input1.tif")
            outputfile1 = tmpdir.joinpath("output1.tif")
            outputfile2 = tmpdir.joinpath("bla", "output1.tif")
            inputfile1.touch()
            outputfile2.parent.mkdir()
            outputfile2.touch()

            potential_list_args = {
                "input": str(tmpdir.joinpath("**", "input*.tif")),
                "output": str(tmpdir.joinpath("**", "output*.tif"))
            }
            singular_args = {
                "something": "bla"
            }
            res = _get_all_combinations(potential_list_args, singular_args)
            print(res)
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
