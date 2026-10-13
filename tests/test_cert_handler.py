#!/usr/bin/env python3
"""
Testes unitários para o módulo cert_handler (detecção de certificados A3 e A1).
"""
import unittest
from unittest.mock import patch
import os
import sys

# Garante inclusão de src no sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

import cert_handler


class TestCertHandlerA3Detection(unittest.TestCase):
    def test_detect_microsoft_smart_card_ksp(self):
        """Certificado A3 usando minidriver da Microsoft (ex.: G&D StarSign CUT)"""
        cert_info = {
            "subject": "CN=MEP REFRIGERACAO EIRELI:13043647000142, OU=RFB e-CNPJ A3, O=ICP-Brasil",
            "provider": "Microsoft Smart Card Key Storage Provider",
            "thumbprint": "93d949e6ad41b7e8fe6606ea3ecf28263ed247c2",
        }
        self.assertTrue(cert_handler.is_token_certificate(cert_info))

    def test_detect_safesign_legacy_provider(self):
        """Certificado A3 com middleware completo SafeSign"""
        cert_info = {
            "subject": "CN=EMPRESA TESTE:12345678000199, OU=RFB e-CNPJ A3",
            "provider": "SafeSign Standard Cryptographic Service Provider",
            "thumbprint": "1234567890abcdef",
        }
        self.assertTrue(cert_handler.is_token_certificate(cert_info))

    def test_detect_ic_standard_provider(self):
        """Certificado A3 com provider IC Standard"""
        cert_info = {
            "subject": "CN=EMPRESA TESTE:12345678000199",
            "provider": "SafeSign IC Standard Provider",
            "thumbprint": "abcdef1234567890",
        }
        self.assertTrue(cert_handler.is_token_certificate(cert_info))

    def test_detect_by_subject_icp_brasil_a3(self):
        """Certificado A3 identificado pelo Subject ICP-Brasil mesmo com outro provider de hardware"""
        cert_info = {
            "subject": "CN=FULANO DE TAL:12345678900, OU=Autenticacao, OU=e-CPF A3, O=ICP-Brasil",
            "provider": "Crypto Hardware Provider",
            "thumbprint": "aabbccddeeff001122",
        }
        self.assertTrue(cert_handler.is_token_certificate(cert_info))

    def test_reject_a1_software_certificate(self):
        """Certificado A1 em software NÃO deve ser classificado como Token A3"""
        cert_info = {
            "subject": "CN=MEP INSTALACOES:22692924000139, OU=RFB e-CNPJ A1, O=ICP-Brasil",
            "provider": "Microsoft Enhanced Cryptographic Provider v1.0",
            "thumbprint": "89d385a6403dbf2eda87c4baa67b64a5bcaf74c7",
        }
        self.assertFalse(cert_handler.is_token_certificate(cert_info))

    def test_reject_empty_or_none(self):
        """Casos com dados nulos ou vazios"""
        self.assertFalse(cert_handler.is_token_certificate(None))
        self.assertFalse(cert_handler.is_token_certificate({}))
        self.assertFalse(cert_handler.is_token_certificate({"provider": "", "subject": ""}))

    @patch("cert_handler.list_windows_store_certs")
    def test_list_token_certs_filters_correctly(self, mock_list_certs):
        """Valida que list_token_certs retorna somente certificados A3"""
        mock_list_certs.return_value = [
            {
                "subject": "CN=MEP REFRIGERACAO:13043647000142, OU=RFB e-CNPJ A3",
                "provider": "Microsoft Smart Card Key Storage Provider",
                "thumbprint": "93d949e6ad41b7e8fe6606ea3ecf28263ed247c2",
            },
            {
                "subject": "CN=MEP INSTALACOES:22692924000139, OU=RFB e-CNPJ A1",
                "provider": "Microsoft Enhanced Cryptographic Provider v1.0",
                "thumbprint": "89d385a6403dbf2eda87c4baa67b64a5bcaf74c7",
            }
        ]

        tokens = cert_handler.list_token_certs()
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0]["thumbprint"], "93d949e6ad41b7e8fe6606ea3ecf28263ed247c2")


if __name__ == "__main__":
    unittest.main()
