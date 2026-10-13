import glob
import os
import unittest

from album.distributed.path_pattern import PathPattern, is_pattern


class TestPathPattern(unittest.TestCase):
    def test_is_pattern(self):
        self.assertTrue(is_pattern("*.tif"))
        self.assertTrue(is_pattern("input?.tif"))
        self.assertTrue(is_pattern("input[0-9].tif"))
        self.assertFalse(is_pattern("input.tif"))
        self.assertFalse(is_pattern("results/"))
        self.assertFalse(is_pattern(None))
        self.assertFalse(is_pattern(3))

    def test_prefix_and_segments(self):
        pattern = PathPattern("data/sub/in*/**/*.tif")
        self.assertEqual("data/sub/", pattern.prefix)
        self.assertEqual(["in*", "**", "*.tif"], pattern.segments)
        self.assertEqual(2, pattern.wildcard_count())

        pattern = PathPattern("*_out.tif")
        self.assertEqual("", pattern.prefix)
        self.assertEqual(["*_out.tif"], pattern.segments)
        self.assertEqual(1, pattern.wildcard_count())

    def test_capture(self):
        self.assertEqual(([], ["a"]), PathPattern("*.tif").capture("a.tif"))
        self.assertEqual(
            ([], ["1"]),
            PathPattern("data/input*.tif").capture(os.path.join("data", "input1.tif")),
        )
        self.assertEqual(
            ([], ["p", "2"]), PathPattern("in*ut*.tif").capture("input2.tif")
        )
        self.assertEqual(
            ([], ["1", "a"]), PathPattern("in?_[a-c].tif").capture("in1_a.tif")
        )
        self.assertIsNone(PathPattern("*.tif").capture("a.png"))

    def test_capture_recursive(self):
        pattern = PathPattern("**/*.tif")
        self.assertEqual(([[]], ["a"]), pattern.capture("a.tif"))
        self.assertEqual(
            ([["sub"]], ["b"]), pattern.capture(os.path.join("sub", "b.tif"))
        )
        self.assertEqual(
            ([["sub", "deeper"]], ["c"]),
            pattern.capture(os.path.join("sub", "deeper", "c.tif")),
        )

    def test_capture_absolute(self):
        folder = os.path.abspath("data")
        pattern = PathPattern(os.path.join(folder, "**", "input*.tif"))
        self.assertEqual(
            ([["bla"]], ["1"]),
            pattern.capture(os.path.join(folder, "bla", "input1.tif")),
        )
        # glob keeps the literal folder as written and joins the matched part with os.sep
        pattern = PathPattern(folder + "/" + "*.tif")
        self.assertEqual(([], ["a"]), pattern.capture(os.path.join(folder, "a.tif")))

    def test_derive(self):
        captures = PathPattern("*.tif").capture("a.tif")
        self.assertEqual("a_out.tif", PathPattern("*_out.tif").derive(captures))
        self.assertEqual("output/a.tif", PathPattern("output/*.tif").derive(captures))
        # "**" without a corresponding "**" in the other pattern is removed
        self.assertEqual("a_out.tif", PathPattern("**/*_out.tif").derive(captures))
        # more wildcards than captures
        self.assertIsNone(PathPattern("*_*.tif").derive(captures))

    def test_derive_recursive(self):
        captures = PathPattern("**/*.tif").capture(
            os.path.join("sub", "deeper", "b.tif")
        )
        self.assertEqual(
            os.path.join("sub", "deeper", "b_out.tif"),
            PathPattern("**/*_out.tif").derive(captures),
        )
        self.assertEqual(
            "output/" + os.path.join("sub", "deeper", "b.tif"),
            PathPattern("output/**/*.tif").derive(captures),
        )
        # without "**" the sub folders are dropped
        self.assertEqual("output/b.tif", PathPattern("output/*.tif").derive(captures))

    def test_derive_multiple_wildcards(self):
        captures = PathPattern("in*ut*.tif").capture("input2.tif")
        self.assertEqual("output2.tif", PathPattern("out*ut*.tif").derive(captures))
        captures = PathPattern("*/*.tif").capture(os.path.join("bla", "input1.tif"))
        self.assertEqual(
            "out/" + os.path.join("bla", "input1.tif"),
            PathPattern("out/*/*.tif").derive(captures),
        )

    def test_derive_directory(self):
        captures = PathPattern("data/*/").capture(
            os.path.join("data", "sample1") + os.sep
        )
        self.assertEqual(
            "results/sample1" + os.sep, PathPattern("results/*/").derive(captures)
        )

    def test_character_sets(self):
        pattern = PathPattern("img[0-9]_[!x][&~|]*.tif")
        self.assertEqual(4, pattern.wildcard_count())
        self.assertEqual(([], ["1", "a", "&", "b"]), pattern.capture("img1_a&b.tif"))
        self.assertEqual(([], ["2", "b", "|", ""]), pattern.capture("img2_b|.tif"))
        self.assertIsNone(pattern.capture("img1_x&b.tif"))
        self.assertIsNone(pattern.capture("imga_a&b.tif"))

    def test_escaped_literals(self):
        # glob.escape turns special characters into sets with a single character - these are no wildcards
        folder = glob.escape(os.path.join("data[1]", "a*b?"))
        pattern = PathPattern(os.path.join(folder, "*.tif"))
        self.assertEqual(1, pattern.wildcard_count())
        captures = pattern.capture(os.path.join("data[1]", "a*b?", "c.tif"))
        self.assertEqual(([], ["c"]), captures)
        self.assertEqual("out/c.tif", PathPattern("out/*.tif").derive(captures))


if __name__ == "__main__":
    unittest.main()
