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
import shutil
from datetime import date, datetime

# Garante acesso aos módulos em src/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import database

SAMPLE_XML_NFSE = """<?xml version="1.0" encoding="UTF-8"?>
<NFSe xmlns="http://www.sped.fazenda.gov.br/nfse">
    <infNFSe Id="NFS31062002222692924000139000000000006326047074951490">
        <dhEmi>2026-04-07T10:00:00-03:00</dhEmi>
        <nNFSe>63</nNFSe>
        <serie>1</serie>
        <emit>
            <CNPJ>22692924000139</CNPJ>
            <xNome>Empresa Prestadora Exemplo</xNome>
        </emit>
        <toma>
            <CNPJ>12345678000199</CNPJ>
            <xNome>Tomador dos Servicos</xNome>
        </toma>
        <valores>
            <vServPrest>
                <vServ>2500.00</vServ>
            </vServPrest>
            <vLiq>2375.00</vLiq>
            <trib>
                <tribMun>
                    <vISS>125.00</vISS>
                </tribMun>
            </trib>
        </valores>
        <xDescServ>Servicos de desenvolvimento de software</xDescServ>
    </infNFSe>
</NFSe>
"""

SAMPLE_XML_EVENTO_CANCELAMENTO = """<?xml version="1.0" encoding="utf-8"?>
<evento versao="1.01" xmlns="http://www.sped.fazenda.gov.br/nfse">
    <infEvento Id="EVT31062002222692924000139000000000006326047074951490101101001">
        <verAplic>EmissorWeb_1.6.0.0</verAplic>
        <ambGer>2</ambGer>
        <nSeqEvento>1</nSeqEvento>
        <dhProc>2026-04-07T12:51:38-03:00</dhProc>
        <nDFe>0</nDFe>
        <pedRegEvento versao="1.01" xmlns="http://www.sped.fazenda.gov.br/nfse">
            <infPedReg Id="PRE31062002222692924000139000000000006326047074951490101101">
                <tpAmb>1</tpAmb>
                <verAplic>EmissorWeb_1.</verAplic>
                <dhEvento>2026-04-07T12:51:38-03:00</dhEvento>
                <CNPJAutor>22692924000139</CNPJAutor>
                <chNFSe>31062002222692924000139000000000006326047074951490</chNFSe>
                <e101101>
                    <xDesc>Cancelamento de NFS-e</xDesc>
                    <cMotivo>1</cMotivo>
                    <xMotivo>erro na emissao</xMotivo>
                </e101101>
            </infPedReg>
        </pedRegEvento>
    </infEvento>
</evento>
"""


class TestCancellation(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_nfse.db")
        database.init_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_extract_event_metadata(self):
        meta = database.extract_event_metadata(SAMPLE_XML_EVENTO_CANCELAMENTO)
        self.assertIsNotNone(meta)
        self.assertEqual(meta["tipo_evento"], "cancelamento")
        self.assertEqual(meta["codigo_evento"], "101101")
        self.assertEqual(meta["chave_acesso"], "31062002222692924000139000000000006326047074951490")
        self.assertEqual(meta["motivo"], "erro na emissao")
        self.assertEqual(meta["data_evento"], "2026-04-07")
        self.assertEqual(meta["cnpj_autor"], "22692924000139")

    def test_cancel_nota_and_rename_files(self):
        # 1. Cria nota fiscal no banco e arquivos de teste em disco
        xml_file = os.path.join(self.temp_dir.name, "NFSe_20260407_000063.xml")
        pdf_file = os.path.join(self.temp_dir.name, "NFSe_20260407_000063.pdf")

        with open(xml_file, "w", encoding="utf-8") as f:
            f.write(SAMPLE_XML_NFSE)
        with open(pdf_file, "w", encoding="utf-8") as f:
            f.write("%PDF-dummy")

        nota_meta = database.extract_nota_metadata(SAMPLE_XML_NFSE, cnpj_consultado="22692924000139")
        nota_meta["caminho_xml"] = xml_file
        nota_meta["caminho_pdf"] = pdf_file
        row_id = database.upsert_nota_fiscal(nota_meta, db_path=self.db_path)
        self.assertIsNotNone(row_id)

        # 2. Executa cancelamento por chave de acesso
        res = database.cancel_nota_by_key(
            chave_acesso="31062002222692924000139000000000006326047074951490",
            motivo="erro na emissao",
            data_cancelamento="2026-04-07",
            nsu_evento=304,
            db_path=self.db_path
        )
        self.assertIsNotNone(res)
        self.assertEqual(res["status"], "cancelada")
        self.assertTrue(res["caminho_xml"].endswith("NFSe_20260407_000063_cancelada.xml"))
        self.assertTrue(res["caminho_pdf"].endswith("NFSe_20260407_000063_cancelada.pdf"))

        # 3. Verifica se os arquivos no disco foram renomeados
        self.assertFalse(os.path.exists(xml_file))
        self.assertFalse(os.path.exists(pdf_file))
        self.assertTrue(os.path.exists(res["caminho_xml"]))
        self.assertTrue(os.path.exists(res["caminho_pdf"]))

        # 4. Verifica no banco
        notas = database.query_notas(cnpj="22692924000139", db_path=self.db_path)
        self.assertEqual(len(notas), 1)
        self.assertEqual(notas[0]["status"], "cancelada")
        self.assertEqual(notas[0]["motivo_cancelamento"], "erro na emissao")
        self.assertEqual(notas[0]["nsu_cancelamento"], 304)

    def test_financial_summary_isolates_cancelled(self):
        # Cria uma nota ativa (faturada: 1000) e uma nota cancelada (faturada: 2500)
        meta_ativa = {
            "chave_acesso": "11111111111111111111111111111111111111111111111111",
            "numero_nfse": "1",
            "tipo": "prestado",
            "status": "autorizada",
            "data_emissao": "2026-04-01",
            "cnpj_consultado": "22692924000139",
            "valor_servico": 1000.0,
            "valor_liquido": 950.0,
            "valor_iss": 50.0
        }
        database.upsert_nota_fiscal(meta_ativa, db_path=self.db_path)

        meta_canc = {
            "chave_acesso": "22222222222222222222222222222222222222222222222222",
            "numero_nfse": "2",
            "tipo": "prestado",
            "status": "cancelada",
            "data_emissao": "2026-04-02",
            "cnpj_consultado": "22692924000139",
            "valor_servico": 2500.0,
            "valor_liquido": 2375.0,
            "valor_iss": 125.0
        }
        database.upsert_nota_fiscal(meta_canc, db_path=self.db_path)

        summary = database.get_financial_summary(cnpj="22692924000139", db_path=self.db_path)
        self.assertEqual(summary["total_notas"], 2)
        self.assertEqual(summary["total_canceladas"], 1)
        self.assertEqual(summary["valor_canceladas"], 2500.0)
        self.assertEqual(summary["total_prestadas"], 1)
        # O total faturado deve incluir APENAS a nota ativa (1000.00), e não 3500.00
        self.assertEqual(summary["total_faturado"], 1000.0)
        self.assertEqual(summary["total_iss"], 50.0)

    def test_import_existing_data_with_cancellations(self):
        # Cria estrutura de pastas com XML de NFS-e e XML de Evento de cancelamento
        notas_dir = os.path.join(self.temp_dir.name, "notas_fiscais")
        cnpj_dir = os.path.join(notas_dir, "22692924000139")
        prestados_dir = os.path.join(cnpj_dir, "prestados")
        sem_data_dir = os.path.join(cnpj_dir, "sem_data")
        os.makedirs(prestados_dir, exist_ok=True)
        os.makedirs(sem_data_dir, exist_ok=True)

        nfse_xml = os.path.join(prestados_dir, "NFSe_20260407_000063.xml")
        nfse_pdf = os.path.join(prestados_dir, "NFSe_20260407_000063.pdf")
        with open(nfse_xml, "w", encoding="utf-8") as f:
            f.write(SAMPLE_XML_NFSE)
        with open(nfse_pdf, "w", encoding="utf-8") as f:
            f.write("%PDF-dummy")

        evt_xml = os.path.join(sem_data_dir, "nsu_304.xml")
        with open(evt_xml, "w", encoding="utf-8") as f:
            f.write(SAMPLE_XML_EVENTO_CANCELAMENTO)

        stats = database.import_existing_data(notas_dir=notas_dir, db_path=self.db_path)
        self.assertEqual(stats["xmls_importados"], 1)
        self.assertEqual(stats["canceladas_atualizadas"], 1)

        # Verifica se a nota foi marcada como cancelada e os arquivos foram renomeados para _cancelada
        notas = database.query_notas(cnpj="22692924000139", db_path=self.db_path)
        self.assertEqual(len(notas), 1)
        self.assertEqual(notas[0]["status"], "cancelada")
        self.assertTrue(notas[0]["caminho_xml"].endswith("_cancelada.xml"))
        self.assertTrue(notas[0]["caminho_pdf"].endswith("_cancelada.pdf"))
        self.assertTrue(os.path.exists(notas[0]["caminho_xml"]))
        self.assertTrue(os.path.exists(notas[0]["caminho_pdf"]))


if __name__ == "__main__":
    unittest.main()
