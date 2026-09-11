import unittest
import os
import sys
import tempfile
import shutil
from datetime import date
from unittest.mock import MagicMock, patch

# Ensure src and root directories are in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import nsu_index


class TestNsuLocationCache(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.orig_cache_dir = nsu_index.NSU_CACHE_DIR
        nsu_index.NSU_CACHE_DIR = self.test_dir

    def tearDown(self):
        nsu_index.NSU_CACHE_DIR = self.orig_cache_dir
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_save_and_load_cache(self):
        cnpj = "13043647000142"
        env = "1"
        target_date = date(2026, 8, 1)
        nsu_index.save_nsu_location_cache(cnpj, env, target_date, 384)

        cached_nsu, origem = nsu_index.load_nsu_location_cache(cnpj, env, target_date)
        self.assertEqual(cached_nsu, 384)
        self.assertEqual(origem, "exato")

    def test_locate_nsu_by_date_applies_safety_margin(self):
        cnpj = "13043647000142"
        env = "1"
        target_date = date(2026, 8, 1)
        # Salva NSU 384 (situação da CRITEC)
        nsu_index.save_nsu_location_cache(cnpj, env, target_date, 384)

        dummy_download = MagicMock()
        # Ao localizar, deve aplicar margem de segurança de 50
        nsu_inicial = nsu_index.locate_nsu_by_date(
            dummy_download,
            "https://dummy",
            target_date,
            cnpj_label=cnpj,
            env_choice=env,
            ignore_cache=False
        )
        self.assertEqual(nsu_inicial, 384 - 50)
        # Nenhuma requisição à rede deve ter sido feita graças ao cache
        dummy_download.assert_not_called()

    def test_locate_nsu_by_date_small_nsu_clamps_to_one(self):
        cnpj = "13043647000142"
        env = "1"
        target_date = date(2026, 8, 1)
        # Salva NSU 20 (< safety margin)
        nsu_index.save_nsu_location_cache(cnpj, env, target_date, 20)

        dummy_download = MagicMock()
        nsu_inicial = nsu_index.locate_nsu_by_date(
            dummy_download,
            "https://dummy",
            target_date,
            cnpj_label=cnpj,
            env_choice=env,
            ignore_cache=False
        )
        self.assertEqual(nsu_inicial, 1)

    @patch("nsu_index._extend_nsu_index")
    def test_locate_nsu_by_date_ignore_cache_bypasses(self, mock_extend):
        cnpj = "13043647000142"
        env = "1"
        target_date = date(2026, 8, 1)
        nsu_index.save_nsu_location_cache(cnpj, env, target_date, 384)

        dummy_download = MagicMock()
        nsu_inicial = nsu_index.locate_nsu_by_date(
            dummy_download,
            "https://dummy",
            target_date,
            cnpj_label=cnpj,
            env_choice=env,
            ignore_cache=True
        )
        # Bypassed cache and called index extension
        mock_extend.assert_called_once()
        self.assertEqual(nsu_inicial, 1)


if __name__ == "__main__":
    unittest.main()
