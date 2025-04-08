#!/usr/bin/env python3
"""
Test runner for the Oura Ring Data Comparison application.
"""
import unittest
import sys
import os

def run_tests():
    """Discover and run all tests in the tests directory."""
    # Get the directory containing the tests
    test_dir = os.path.join(os.path.dirname(__file__), 'tests')
    
    # Discover tests in the tests directory
    test_suite = unittest.defaultTestLoader.discover(test_dir)
    
    # Run the tests
    test_runner = unittest.TextTestRunner(verbosity=2)
    result = test_runner.run(test_suite)
    
    # Return appropriate exit code
    return 0 if result.wasSuccessful() else 1

if __name__ == '__main__':
    sys.exit(run_tests()) 