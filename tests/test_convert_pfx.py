import unittest
import os
import sys
import subprocess
import tempfile
import shutil

# Ensure src and root directories are in sys.path
SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, SRC_DIR)
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestConvertPfxNonInteractive(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_non_interactive_missing_file(self):
        """Verifica se com stdin fechado (DEVNULL) o script retorna erro rapidamente sem bloquear."""
        non_existent_pfx = os.path.join(self.test_dir, "nao_existe.pfx")
        cmd = [sys.executable, os.path.join(SRC_DIR, "convert_pfx.py"), non_existent_pfx, "senha123"]
        result = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("encontrado", result.stdout)

    def test_non_interactive_empty_args_does_not_hang(self):
        """Sem argumentos e com DEVNULL no stdin, o script não deve travar."""
        cmd = [sys.executable, os.path.join(SRC_DIR, "convert_pfx.py")]
        result = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5
        )
        # O script deve executar e terminar rapidamente sem bloqueio de stdin
        self.assertTrue(len(result.stdout) > 0)


if __name__ == "__main__":
    unittest.main()
