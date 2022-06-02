import inspect
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


if __name__ == '__main__':
    unittest.main()
