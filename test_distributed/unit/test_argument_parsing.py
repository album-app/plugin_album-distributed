import contextlib
import inspect
import io
import sys
import unittest.mock

from album.argument_parsing import create_parser

from album.distributed import distributed_modes


class TestArgumentParsing(unittest.TestCase):

    def test_create_parser(self):
        parser = create_parser()
        sys.argv = ["", "run-distributed", "1234"]
        args = parser.parse_known_args()
        self.assertEqual("1234", args[0].solution)
        self.assertEqual(inspect.getsource(distributed_modes.run), inspect.getsource(args[0].func))
        self.assertEqual("basic", args[0].mode)

    def test_create_parser_modes(self):
        parser = create_parser()
        for mode in ["basic", "queue"]:
            args = parser.parse_known_args(["run-distributed", "1234", "--mode", mode])
            self.assertEqual(mode, args[0].mode)

    def test_create_parser_unknown_mode(self):
        parser = create_parser()
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output), self.assertRaises(SystemExit):
            parser.parse_known_args(["run-distributed", "1234", "--mode", "bogus"])
        self.assertIn("invalid choice: 'bogus'", output.getvalue())

    def test_create_parser_install(self):
        parser = create_parser()
        self.assertFalse(parser.parse_known_args(["run-distributed", "1234"])[0].install)
        self.assertTrue(parser.parse_known_args(["run-distributed", "1234", "--install"])[0].install)

    def test_create_parser_threads(self):
        parser = create_parser()
        self.assertEqual(3, parser.parse_known_args(["run-distributed", "1234"])[0].threads)
        self.assertEqual(16, parser.parse_known_args(["run-distributed", "1234", "--threads", "16"])[0].threads)

    def test_create_parser_invalid_threads(self):
        # with less than one worker thread, the queue mode would wait forever for the tasks to finish
        parser = create_parser()
        for threads, message in [("0", "has to be at least 1, got 0"), ("-2", "has to be at least 1, got -2"),
                                 ("many", "invalid number: 'many'")]:
            output = io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                with self.assertRaises(SystemExit):
                    parser.parse_known_args(["run-distributed", "1234", "--threads", threads])
            self.assertIn("--threads: " + message, output.getvalue())


if __name__ == '__main__':
    unittest.main()
