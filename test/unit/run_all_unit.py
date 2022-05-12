import time
import unittest

from test.unit import test_argument_parsing, test_argument_matching, test_distributed_modes, test_mode_basic, test_mode_queue


def main():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromModule(test_argument_parsing))
    suite.addTests(loader.loadTestsFromModule(test_argument_matching))
    suite.addTests(loader.loadTestsFromModule(test_distributed_modes))
    suite.addTests(loader.loadTestsFromModule(test_mode_basic))
    suite.addTests(loader.loadTestsFromModule(test_mode_queue))

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
