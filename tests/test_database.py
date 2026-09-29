#!/usr/bin/env python3
# free-nfse-downloader
# Copyright (C) 2026 Cassio Soares
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import os
import sys
import unittest
import tempfile
import sqlite3
import json
from datetime import date, datetime

# Garante acesso aos módulos em src/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import database

SAMPLE_XML_PRESTADO = """<?xml version="1.0" encoding="UTF-8"?>
<NFSe xmlns="http://www.sped.fazenda.gov.br/nfse">
    <infNFSe Id="NFS31240212345678000199000000000000000000000000000001">
        <xLocEmi>Belo Horizonte</xLocEmi>
        <dhEmi>2026-05-15T14:30:00-03:00</dhEmi>
        <nNFSe>123</nNFSe>
        <serie>1</serie>
        <emit>
            <CNPJ>12345678000199</CNPJ>
            <xNome>Empresa Prestadora Teste Ltda</xNome>
            <IM>123456</IM>
            <enderEmit>
                <xMun>Belo Horizonte</xMun>
            </enderEmit>
        </emit>
        <toma>
            <CNPJ>98765432000188</CNPJ>
            <xNome>Cliente Tomador S/A</xNome>
            <IM>654321</IM>
            <enderToma>
                <xMun>Sao Paulo</xMun>
            </enderToma>
        </toma>
        <valores>
            <vServPrest>
                <vServ>1000.00</vServ>
            </vServPrest>
            <vLiq>950.00</vLiq>
            <trib>
                <tribNac>
                    <vPIS>6.50</vPIS>
                    <vCOFINS>30.00</vCOFINS>
                    <vINSS>0.00</vINSS>
                    <vIR>15.00</vIR>
                    <vCSLL>10.00</vCSLL>
                </tribNac>
                <tribMun>
                    <tpRetISS>1</tpRetISS>
                    <pAliq>5.00</pAliq>
                    <vISS>50.00</vISS>
                </tribMun>
            </trib>
        </valores>
        <cTribNac>010701</cTribNac>
        <xDescServ>Desenvolvimento e integracao de software</xDescServ>
    </infNFSe>
</NFSe>
"""

SAMPLE_XML_TOMADO = """<?xml version="1.0" encoding="UTF-8"?>
<NFSe xmlns="http://www.sped.fazenda.gov.br/nfse">
    <infNFSe Id="NFS31240298765432000188000000000000000000000000000002">
        <dhEmi>2026-05-20T10:00:00-03:00</dhEmi>
        <nNFSe>456</nNFSe>
        <emit>
            <CNPJ>98765432000188</CNPJ>
            <xNome>Fornecedor de Servicos Gerais</xNome>
        </emit>
        <toma>
            <CNPJ>12345678000199</CNPJ>
            <xNome>Empresa Prestadora Teste Ltda</xNome>
        </toma>
        <valores>
            <vServ>500.00</vServ>
            <vISS>25.00</vISS>
        </valores>
        <xDescServ>Servicos de consultoria especializada</xDescServ>
    </infNFSe>
</NFSe>
"""


class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_nfse.db")
        database.init_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_init_db(self):
        conn = database.get_connection(self.db_path)
        try:
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
            names = [r["name"] for r in tables]
            self.assertIn("notas_fiscais", names)
            self.assertIn("nsu_index", names)
            self.assertIn("sync_history", names)
        finally:
            conn.close()

    def test_extract_nota_metadata(self):
        meta = database.extract_nota_metadata(SAMPLE_XML_PRESTADO, cnpj_consultado="12345678000199")
        self.assertIsNotNone(meta)
        self.assertEqual(meta["chave_acesso"], "31240212345678000199000000000000000000000000000001")
        self.assertEqual(meta["numero_nfse"], "123")
        self.assertEqual(meta["serie"], "1")
        self.assertEqual(meta["tipo"], "prestado")
        self.assertEqual(meta["data_emissao"], "2026-05-15")
        self.assertEqual(meta["prestador_cnpj_cpf"], "12345678000199")
        self.assertEqual(meta["prestador_nome"], "Empresa Prestadora Teste Ltda")
        self.assertEqual(meta["tomador_cnpj_cpf"], "98765432000188")
        self.assertEqual(meta["tomador_nome"], "Cliente Tomador S/A")
        self.assertEqual(meta["valor_servico"], 1000.0)
        self.assertEqual(meta["valor_iss"], 50.0)
        self.assertEqual(meta["valor_pis"], 6.50)
        self.assertEqual(meta["valor_cofins"], 30.00)
        self.assertEqual(meta["valor_ir"], 15.00)
        self.assertEqual(meta["valor_csll"], 10.00)
        self.assertEqual(meta["iss_retido"], 1)
        self.assertEqual(meta["codigo_tributacao_nacional"], "010701")
        self.assertEqual(meta["discriminacao_servico"], "Desenvolvimento e integracao de software")

    def test_upsert_nota_fiscal(self):
        meta1 = database.extract_nota_metadata(SAMPLE_XML_PRESTADO, cnpj_consultado="12345678000199")
        meta1["caminho_xml"] = "/tmp/fake_nfse.xml"
        row_id = database.upsert_nota_fiscal(meta1, db_path=self.db_path)
        self.assertIsNotNone(row_id)

        # Atualização com caminho_pdf
        meta1["caminho_pdf"] = "/tmp/fake_nfse.pdf"
        row_id2 = database.upsert_nota_fiscal(meta1, db_path=self.db_path)
        self.assertEqual(row_id, row_id2)

        # Verifica dados no banco
        notas = database.query_notas(cnpj="12345678000199", db_path=self.db_path)
        self.assertEqual(len(notas), 1)
        self.assertEqual(notas[0]["caminho_pdf"], "/tmp/fake_nfse.pdf")
        self.assertEqual(notas[0]["caminho_xml"], "/tmp/fake_nfse.xml")

    def test_nsu_index(self):
        database.save_nsu_index_entry("12345678000199", "1", 100, date(2026, 5, 1), db_path=self.db_path)
        database.save_nsu_index_entry("12345678000199", "1", 200, date(2026, 5, 15), db_path=self.db_path)

        index = database.load_nsu_index("12345678000199", "1", db_path=self.db_path)
        self.assertEqual(len(index), 2)
        self.assertEqual(index[100], date(2026, 5, 1))
        self.assertEqual(index[200], date(2026, 5, 15))

    def test_sync_history(self):
        sync_id = database.record_sync_history(
            cnpj="12345678000199",
            ambiente="1",
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 31),
            nsu_ini=100,
            nsu_fim=250,
            total=15,
            status="sucesso",
            db_path=self.db_path
        )
        self.assertIsNotNone(sync_id)

        conn = database.get_connection(self.db_path)
        try:
            row = conn.execute("SELECT * FROM sync_history WHERE id = ?", (sync_id,)).fetchone()
            self.assertEqual(row["total_baixadas"], 15)
            self.assertEqual(row["status"], "sucesso")
        finally:
            conn.close()

    def test_financial_summary_and_query(self):
        # Insere prestada
        m1 = database.extract_nota_metadata(SAMPLE_XML_PRESTADO, cnpj_consultado="12345678000199")
        database.upsert_nota_fiscal(m1, db_path=self.db_path)

        # Insere tomada
        m2 = database.extract_nota_metadata(SAMPLE_XML_TOMADO, cnpj_consultado="12345678000199")
        database.upsert_nota_fiscal(m2, db_path=self.db_path)

        summary = database.get_financial_summary(cnpj="12345678000199", db_path=self.db_path)
        self.assertEqual(summary["total_notas"], 2)
        self.assertEqual(summary["total_prestadas"], 1)
        self.assertEqual(summary["total_tomadas"], 1)
        self.assertEqual(summary["total_faturado"], 1000.0)
        self.assertEqual(summary["total_tomado_servico"], 500.0)
        self.assertEqual(summary["total_iss"], 75.0)

        # Filtro por tipo
        prestadas = database.query_notas(cnpj="12345678000199", tipo="prestado", db_path=self.db_path)
        self.assertEqual(len(prestadas), 1)
        self.assertEqual(prestadas[0]["numero_nfse"], "123")

        # Filtro por busca textual
        buscas = database.query_notas(search_text="consultoria", db_path=self.db_path)
        self.assertEqual(len(buscas), 1)
        self.assertEqual(buscas[0]["numero_nfse"], "456")

    def test_import_existing_data(self):
        # Cria estrutura de pastas mock
        notas_dir = os.path.join(self.temp_dir.name, "notas_fiscais", "12345678000199", "prestados")
        cache_dir = os.path.join(self.temp_dir.name, "cache_nsu")
        os.makedirs(notas_dir, exist_ok=True)
        os.makedirs(cache_dir, exist_ok=True)

        xml_file = os.path.join(notas_dir, "NFSe_20260515_000123.xml")
        with open(xml_file, "w", encoding="utf-8") as f:
            f.write(SAMPLE_XML_PRESTADO)

        idx_file = os.path.join(cache_dir, "12345678000199_1_index.json")
        with open(idx_file, "w", encoding="utf-8") as f:
            json.dump({"100": "2026-05-01", "200": "2026-05-15"}, f)

        stats = database.import_existing_data(notas_dir=self.temp_dir.name, cache_dir=cache_dir, db_path=self.db_path)
        self.assertEqual(stats["xmls_importados"], 1)
        self.assertEqual(stats["nsu_index_importados"], 2)

        # Valida que foi importado no banco
        index = database.load_nsu_index("12345678000199", "1", db_path=self.db_path)
        self.assertEqual(len(index), 2)
        notas = database.query_notas(cnpj="12345678000199", db_path=self.db_path)
        self.assertEqual(len(notas), 1)
        self.assertEqual(notas[0]["numero_nfse"], "123")


if __name__ == "__main__":
    unittest.main()
