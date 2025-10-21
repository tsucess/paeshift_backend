"""
Simple test file to verify that the test runner is working.
"""

from django.test import TestCase


class SimpleTestCase(TestCase):
    """A simple test case to verify that the test runner is working."""

    def test_true_is_true(self):
        """Test that True is True."""
        self.assertTrue(True)

    def test_one_plus_one_equals_two(self):
        """Test that 1 + 1 = 2."""
        self.assertEqual(1 + 1, 2)
