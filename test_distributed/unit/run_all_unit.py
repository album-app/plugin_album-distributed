import time
import unittest

from test_distributed.unit import test_argument_parsing, test_argument_matching, test_distributed_modes, \
    test_mode_basic, test_mode_queue, test_path_pattern


def main():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromModule(test_argument_parsing))
    suite.addTests(loader.loadTestsFromModule(test_argument_matching))
    suite.addTests(loader.loadTestsFromModule(test_distributed_modes))
    suite.addTests(loader.loadTestsFromModule(test_mode_basic))
    suite.addTests(loader.loadTestsFromModule(test_mode_queue))
    suite.addTests(loader.loadTestsFromModule(test_path_pattern))

    runner = unittest.TextTestRunner(verbosity=3)
    result = runner.run(suite)
    if result.wasSuccessful():
        time.sleep(5)
        print("Success")
        exit(0)
    else:
        print("Failed")
        exit(1)


main()
