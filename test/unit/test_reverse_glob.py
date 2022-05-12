import glob
import os
import re
import tempfile
import unittest.mock
from pathlib import Path

from album.distributed.reverse_glob import reverse_glob, pat_translate


class TestReverseGlob(unittest.TestCase):

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
            print(res)
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
            print(res)
            self.assertEqual(2, len(res))
            self.assertEqual((str(inputfile2), [str(outputfile2)]), res[0])
            self.assertEqual((str(inputfile3), [str(outputfile3)]), res[1])

    def test_reverse_glob_recursive_relative(self):
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmpdirname:
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
            print(res)
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
            print(res)
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
            print(res)
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
            print(res)
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
