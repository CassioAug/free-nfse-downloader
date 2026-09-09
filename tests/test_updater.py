#!/usr/bin/env python3
# free-nfse-downloader
# Copyright (C) 2026 Cassio Soares
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# -*- coding: utf-8 -*-

import os
import sys
import json
import shutil
import tempfile
import unittest
import zipfile
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import updater
from scripts.apply_update import apply_files


class TestUpdaterVersionLogic(unittest.TestCase):
    def test_parse_version(self):
        self.assertEqual(updater.parse_version("v2.1.0"), (2, 1, 0))
        self.assertEqual(updater.parse_version("2.1.0"), (2, 1, 0))
        self.assertEqual(updater.parse_version("2.2"), (2, 2, 0))
        self.assertEqual(updater.parse_version("3"), (3, 0, 0))
        self.assertEqual(updater.parse_version("v2.10.3-beta1"), (2, 10, 3))
        self.assertEqual(updater.parse_version(""), (0, 0, 0))

    def test_is_newer_version(self):
        # Versão superior
        self.assertTrue(updater.is_newer_version("v2.2.0", "2.1.0"))
        self.assertTrue(updater.is_newer_version("2.1.1", "2.1.0"))
        self.assertTrue(updater.is_newer_version("v3.0.0", "2.9.9"))
        self.assertTrue(updater.is_newer_version("v2.10.0", "v2.9.0"))

        # Mesma versão ou inferior
        self.assertFalse(updater.is_newer_version("v2.1.0", "2.1.0"))
        self.assertFalse(updater.is_newer_version("2.1.0", "2.1.0"))
        self.assertFalse(updater.is_newer_version("2.0.9", "2.1.0"))
        self.assertFalse(updater.is_newer_version("v1.9.9", "2.1.0"))


class TestUpdaterNetworkCheck(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_check_for_updates_available(self, mock_urlopen):
        fake_response = MagicMock()
        fake_response.status = 200
        fake_data = {
            "tag_name": "v2.2.0",
            "name": "Release v2.2.0 - Nova Funcionalidade",
            "body": "Novidades incríveis nesta versão.",
            "html_url": "https://github.com/CassioAug/free-nfse-downloader/releases/tag/v2.2.0",
            "assets": [
                {
                    "name": "free-nfse-downloader-v2.2.0.zip",
                    "browser_download_url": "https://github.com/CassioAug/free-nfse-downloader/releases/download/v2.2.0/free-nfse-downloader-v2.2.0.zip"
                }
            ]
        }
        fake_response.read.return_value = json.dumps(fake_data).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = fake_response

        info = updater.check_for_updates(current_version="2.1.0")
        self.assertIsNotNone(info)
        self.assertEqual(info["version"], "2.2.0")
        self.assertEqual(info["tag_name"], "v2.2.0")
        self.assertEqual(info["zip_url"], "https://github.com/CassioAug/free-nfse-downloader/releases/download/v2.2.0/free-nfse-downloader-v2.2.0.zip")
        self.assertIn("Novidades incríveis", info["body"])

    @patch("urllib.request.urlopen")
    def test_check_for_updates_already_updated(self, mock_urlopen):
        fake_response = MagicMock()
        fake_response.status = 200
        fake_data = {
            "tag_name": "v2.1.0",
            "name": "Release v2.1.0",
            "body": "Notas...",
            "assets": []
        }
        fake_response.read.return_value = json.dumps(fake_data).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = fake_response

        info = updater.check_for_updates(current_version="2.1.0")
        self.assertIsNone(info)

    @patch("urllib.request.urlopen")
    def test_check_for_updates_network_error(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("Falha de conexão ou timeout")
        info = updater.check_for_updates(current_version="2.1.0")
        self.assertIsNone(info)


class TestUpdaterDataPreservation(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="fnfse_test_update_")
        self.app_dir = os.path.join(self.test_dir, "app")
        self.staging_dir = os.path.join(self.test_dir, "staging")

        os.makedirs(self.app_dir)
        os.makedirs(self.staging_dir)

        # 1. Simular arquivos existentes do usuário no app_dir
        # Certificados confidenciais
        cert_dir = os.path.join(self.app_dir, "certificados")
        os.makedirs(cert_dir)
        self.cert_file = os.path.join(cert_dir, "meu_certificado_a1.pem")
        with open(self.cert_file, "w", encoding="utf-8") as f:
            f.write("DADOS_CONFIDENCIAIS_DO_CERTIFICADO")

        # Notas fiscais baixadas
        notas_dir = os.path.join(self.app_dir, "notas_fiscais", "12345678000199", "prestados")
        os.makedirs(notas_dir)
        self.nota_file = os.path.join(notas_dir, "nota_100.xml")
        with open(self.nota_file, "w", encoding="utf-8") as f:
            f.write("<xml>NOTA_FISCAL_BAIXADA</xml>")

        # Cache de NSU
        cache_dir = os.path.join(self.app_dir, "cache_nsu")
        os.makedirs(cache_dir)
        self.cache_file = os.path.join(cache_dir, "index.json")
        with open(self.cache_file, "w", encoding="utf-8") as f:
            f.write('{"nsu": 100}')

        # Código antigo da aplicação
        self.gui_file = os.path.join(self.app_dir, "gui.py")
        with open(self.gui_file, "w", encoding="utf-8") as f:
            f.write("versao_antiga = True")

        # 2. Simular arquivos novos na pasta de staging
        self.new_gui_file = os.path.join(self.staging_dir, "gui.py")
        with open(self.new_gui_file, "w", encoding="utf-8") as f:
            f.write("versao_nova = True")

        self.new_module_file = os.path.join(self.staging_dir, "novo_recurso.py")
        with open(self.new_module_file, "w", encoding="utf-8") as f:
            f.write("def recurso(): pass")

        # Tentativa de pacote que contém pastas proibidas
        staging_cert = os.path.join(self.staging_dir, "certificados")
        os.makedirs(staging_cert)
        with open(os.path.join(staging_cert, "dummy.pem"), "w", encoding="utf-8") as f:
            f.write("INTRUSO")

        staging_notas = os.path.join(self.staging_dir, "notas_fiscais")
        os.makedirs(staging_notas)
        with open(os.path.join(staging_notas, "dummy.xml"), "w", encoding="utf-8") as f:
            f.write("INTRUSO")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_apply_files_preserves_user_data_and_updates_code(self):
        copied = apply_files(self.staging_dir, self.app_dir)
        self.assertGreaterEqual(copied, 2)

        # 1. Código deve ter sido atualizado
        with open(self.gui_file, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "versao_nova = True")

        new_module_dst = os.path.join(self.app_dir, "novo_recurso.py")
        self.assertTrue(os.path.exists(new_module_dst))

        # 2. Certificados do usuário devem estar 100% preservados
        self.assertTrue(os.path.exists(self.cert_file))
        with open(self.cert_file, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "DADOS_CONFIDENCIAIS_DO_CERTIFICADO")

        # 3. Nenhum arquivo espúrio deve ter sido copiado para certificados
        self.assertFalse(os.path.exists(os.path.join(self.app_dir, "certificados", "dummy.pem")))

        # 4. Notas fiscais devem permanecer intactas
        self.assertTrue(os.path.exists(self.nota_file))
        with open(self.nota_file, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "<xml>NOTA_FISCAL_BAIXADA</xml>")
        self.assertFalse(os.path.exists(os.path.join(self.app_dir, "notas_fiscais", "dummy.xml")))

        # 5. Cache de NSU preservado
        self.assertTrue(os.path.exists(self.cache_file))
        with open(self.cache_file, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), '{"nsu": 100}')


if __name__ == "__main__":
    unittest.main()
