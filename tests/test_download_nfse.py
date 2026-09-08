import unittest
from datetime import date
import sys
import os

# Ensure the root directory is in the sys.path to allow importing from download_nfse
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from download_nfse import parse_date


class TestParseDate(unittest.TestCase):
    def test_valid_date(self):
        """Test valid standard date string."""
        self.assertEqual(parse_date("01/05/2026"), date(2026, 5, 1))

    def test_valid_date_with_spaces(self):
        """Test valid date string with leading and trailing spaces."""
        self.assertEqual(parse_date("  15/10/2026  "), date(2026, 10, 15))

    def test_invalid_date_format(self):
        """Test date string with invalid format."""
        self.assertIsNone(parse_date("2026-05-01"))
        self.assertIsNone(parse_date("01-05-2026"))

    def test_invalid_date_values(self):
        """Test date string with invalid day or month values."""
        self.assertIsNone(parse_date("32/01/2026"))  # Invalid day
        self.assertIsNone(parse_date("01/13/2026"))  # Invalid month
        self.assertIsNone(parse_date("29/02/2026"))  # Invalid leap year

    def test_empty_string(self):
        """Test empty string."""
        self.assertIsNone(parse_date(""))

    def test_none_input(self):
        """Test None input."""
        self.assertIsNone(parse_date(None))

    def test_non_string_input(self):
        """Test integer and other non-string inputs."""
        self.assertIsNone(parse_date(12345))
        self.assertIsNone(parse_date({"date": "01/01/2026"}))
        self.assertIsNone(parse_date(["01/01/2026"]))


if __name__ == "__main__":
    unittest.main()
