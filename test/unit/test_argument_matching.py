import glob
import os
import re
import tempfile
import unittest.mock
from pathlib import Path
from unittest import mock

from album.api import Album
from album.core.api.model.collection_solution import ICollectionSolution
from album.core.model.resolve_result import ResolveResult
from album.runner.core.api.model.solution import ISolution

from album.distributed.argument_matching import reverse_glob, pat_translate, _get_all_combinations, generate_run_tasks


class TestReverseGlob(unittest.TestCase):

    def test__generate_run_tasks_no_magic(self):
        album = mock.create_autospec(Album)
        resolve_result = mock.create_autospec(ICollectionSolution)
        album.resolve.return_value = resolve_result

        # single input, single output, no pattern
        argv = ["", "", "--input", "input.txt", "--output", "output.txt"]
        tasks = generate_run_tasks(album, "solution.py", argv)
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
            tasks = generate_run_tasks(album, "solution.py", argv)
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

    def test_reverse_glob_input_exists_output_not(self):
        with tempfile.TemporaryDirectory() as tmpdirname:
            tmpdir = Path(tmpdirname)
            inputfile1 = tmpdir.joinpath("input1.tif")
            inputfile3 = tmpdir.joinpath("bla", "input1.tif")
            outputfile1 = tmpdir.joinpath("output1.tif")
            inputfile3.parent.mkdir()

            inputfile1.touch()
            inputfile3.touch()
            input_pattern = str(tmpdir.joinpath("input*.tif"))
            output_pattern = str(tmpdir.joinpath("output*.tif"))
            res = reverse_glob(input_pattern, reverse_path=[output_pattern], recursive=True)
            self.assertEqual(1, len(res))
            self.assertEqual((str(inputfile1), [str(outputfile1)]), res[0])

    def test_reverse_glob_recursive(self):
        with tempfile.TemporaryDirectory() as tmpdirname:
            tmpdir = Path(tmpdirname)
            inputfile2 = tmpdir.joinpath("input2.tif")
            inputfile3 = tmpdir.joinpath("bla", "input1.tif")
            outputfile2 = tmpdir.joinpath("output2.tif")
            outputfile3 = tmpdir.joinpath("bla", "output1.tif")
            inputfile3.parent.mkdir()
            inputfile2.touch()
            inputfile3.touch()

            input_pattern = str(tmpdir.joinpath("**", "in*ut*.tif"))
            output_pattern = str(tmpdir.joinpath("**", "out*ut*.tif"))
            res = reverse_glob(input_pattern, reverse_path=[output_pattern], recursive=True)
            self.assertEqual(2, len(res))
            self.assertEqual((str(inputfile2), [str(outputfile2)]), res[0])
            self.assertEqual((str(inputfile3), [str(outputfile3)]), res[1])

    def test_reverse_glob_recursive_relative(self):
        with tempfile.TemporaryDirectory() as tmpdirname:
            cwd = os.getcwd()
            os.chdir(tmpdirname)
            tmpdir = Path()
            inputfile2 = tmpdir.joinpath("input2.tif")
            inputfile3 = tmpdir.joinpath("bla", "input1.tif")
            outputfile2 = tmpdir.joinpath("output2.tif")
            outputfile3 = tmpdir.joinpath("bla", "output1.tif")
            inputfile3.parent.mkdir()
            inputfile2.touch()
            inputfile3.touch()

            input_pattern = str(tmpdir.joinpath("**", "in*ut*.tif"))
            output_pattern = str(tmpdir.joinpath("**", "out*ut*.tif"))
            res = reverse_glob(input_pattern, reverse_path=[output_pattern], recursive=True)
            self.assertEqual(2, len(res))
            self.assertEqual((str(inputfile2), [str(outputfile2)]), res[0])
            self.assertEqual((str(inputfile3), [str(outputfile3)]), res[1])
            os.chdir(cwd)

    def test_reverse_glob_output_in_different_dir(self):
        with tempfile.TemporaryDirectory() as tmpdirname:
            tmpdir = Path(tmpdirname)
            inputfile2 = tmpdir.joinpath("input2.tif")
            inputfile3 = tmpdir.joinpath("bla", "input1.tif")
            inputfile3.parent.mkdir()
            inputfile2.touch()
            inputfile3.touch()

            # from directory to filename
            input_pattern = str(tmpdir.joinpath("*", "*.tif"))
            output_pattern = str(tmpdir.joinpath("out", "*", "*.tif"))
            res = reverse_glob(input_pattern, reverse_path=[output_pattern], recursive=True)
            self.assertEqual(1, len(res))
            self.assertEqual((str(inputfile3), [str(tmpdir.joinpath("out", "bla", "input1.tif"))]), res[0])

    def test_reverse_glob_multiple_outputs(self):
        with tempfile.TemporaryDirectory() as tmpdirname:
            tmpdir = Path(tmpdirname)
            inputfile2 = tmpdir.joinpath("input2.tif")
            inputfile3 = tmpdir.joinpath("bla", "input1.tif")
            inputfile3.parent.mkdir()
            inputfile2.touch()
            inputfile3.touch()

            # from directory to filename
            input_pattern = str(tmpdir.joinpath("*", "*.tif"))
            output1_pattern = str(tmpdir.joinpath("out", "*", "*.tif"))
            output2_pattern = str(tmpdir.joinpath("out2", "*", "*_other.tif"))
            res = reverse_glob(input_pattern, reverse_path=[output1_pattern, output2_pattern], recursive=True)
            self.assertEqual(1, len(res))
            out1_expected = str(tmpdir.joinpath("out", "bla", "input1.tif"))
            out2_expected = str(tmpdir.joinpath("out2", "bla", "input1_other.tif"))
            self.assertEqual((str(inputfile3), [out1_expected, out2_expected]), res[0])

    @unittest.skip("TODO The implementation of reverse_glob does not yet support this")
    def test_reverse_glob_dirname_to_filename(self):
        with tempfile.TemporaryDirectory() as tmpdirname:
            tmpdir = Path(tmpdirname)
            inputfile2 = tmpdir.joinpath("input2.tif")
            inputfile3 = tmpdir.joinpath("bla", "input1.tif")
            inputfile3.parent.mkdir()
            inputfile2.touch()
            inputfile3.touch()

            # from directory to filename
            input_pattern = str(tmpdir.joinpath("*", "input*.tif"))
            output_pattern = "*_*.tif"
            res = reverse_glob(input_pattern, reverse_path=[output_pattern], recursive=True)
            self.assertEqual(1, len(res))
            self.assertEqual((str(inputfile3), ["bla_1.tif"]), res[0])

    def test_pat_translate(self):
        with tempfile.TemporaryDirectory() as tmpdirname:
            tmpdir = Path(tmpdirname)
            inputfile1 = tmpdir.joinpath("input1.tif")
            inputfile1.touch()
            input_pattern = str(tmpdir.joinpath("input*.tif"))
            names = glob.glob(input_pattern)
            regex = pat_translate(input_pattern)
            pat = re.compile(regex)
            groups = [pat.match(name).groups() for name in names]
            self.assertEqual(1, len(names))
            self.assertEqual(1, len(groups))
            self.assertEqual(str(inputfile1), names[0])
            self.assertEqual(1, len(groups[0]))
            self.assertEqual("1", groups[0][0])


if __name__ == '__main__':
    unittest.main()
