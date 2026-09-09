import unittest
import sys
import os
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from gui import format_date_text
from download_nfse import parse_date


class TestDateMask(unittest.TestCase):
    """Testes para máscara de formatação automática de data na GUI e parser do backend."""

    def test_format_full_numeric_date(self):
        """01012026 deve ser formatado como 01/01/2026."""
        self.assertEqual(format_date_text("01012026"), "01/01/2026")
        self.assertEqual(format_date_text("31122026"), "31/12/2026")

    def test_format_already_formatted_date(self):
        """01/01/2026 não deve duplicar barras."""
        self.assertEqual(format_date_text("01/01/2026"), "01/01/2026")
        self.assertEqual(format_date_text("  15/10/2026  "), "15/10/2026")

    def test_format_progressive_typing(self):
        """Simula a digitação caractere por caractere."""
        self.assertEqual(format_date_text("0"), "0")
        self.assertEqual(format_date_text("01"), "01/")
        self.assertEqual(format_date_text("010"), "01/0")
        self.assertEqual(format_date_text("0101"), "01/01/")
        self.assertEqual(format_date_text("01012"), "01/01/2")
        self.assertEqual(format_date_text("010120"), "01/01/20")
        self.assertEqual(format_date_text("0101202"), "01/01/202")
        self.assertEqual(format_date_text("01012026"), "01/01/2026")

    def test_format_backspace(self):
        """Simula backspace sem reinserir barras desnecessárias."""
        self.assertEqual(format_date_text("01", is_backspace=True), "01")
        self.assertEqual(format_date_text("0101", is_backspace=True), "01/01")
        self.assertEqual(format_date_text("0101202", is_backspace=True), "01/01/202")
        self.assertEqual(format_date_text("01012026", is_backspace=True), "01/01/2026")

    def test_format_ignores_non_digits(self):
        """Caracteres não numéricos (exceto barras válidas) devem ser ignorados."""
        self.assertEqual(format_date_text("abc01012026xyz"), "01/01/2026")
        self.assertEqual(format_date_text("01-01-2026"), "01/01/2026")
        self.assertEqual(format_date_text(""), "")
        self.assertEqual(format_date_text(None), "")

    def test_parse_date_both_formats(self):
        """parse_date deve aceitar tanto DD/MM/YYYY quanto DDMMYYYY com o mesmo resultado."""
        expected = date(2026, 8, 1)
        self.assertEqual(parse_date("01/08/2026"), expected)
        self.assertEqual(parse_date("01082026"), expected)
        self.assertEqual(parse_date("  01082026  "), expected)


if __name__ == "__main__":
    unittest.main()
