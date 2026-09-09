import unittest
import os
import sys
import io
from datetime import date


class TestEncodingCompatibility(unittest.TestCase):
    """Testes para garantir que mensagens e arquivos não quebrem em terminais Windows legados."""

    def test_cp1252_and_cp850_clean_in_project_files(self):
        """Verifica se nenhum arquivo Python contém caracteres fora de CP1252/CP850 em print/logger."""
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        problematic = []

        for root, dirs, files in os.walk(base_dir):
            if any(p in root for p in ['.git', '__pycache__', 'venv', '.venv', 'cache_nsu', 'notas_fiscais']):
                continue
            for f in files:
                if f.endswith('.py') and f != 'test_encoding.py':
                    path = os.path.join(root, f)
                    with open(path, 'r', encoding='utf-8') as fp:
                        for idx, line in enumerate(fp, 1):
                            if 'print(' in line or 'logger.' in line:
                                for ch in line:
                                    if ord(ch) > 127:
                                        try:
                                            ch.encode('cp1252')
                                            ch.encode('cp850')
                                        except UnicodeEncodeError:
                                            problematic.append(
                                                f"{f}:{idx} char '{ch}' (U+{ord(ch):04X}): {line.strip()}"
                                            )
                                            break

        self.assertEqual(problematic, [], f"Encontrados caracteres incompatíveis com CP1252/CP850:\n" + "\n".join(problematic))

    def test_nsu_index_progress_messages_encodable(self):
        """Valida que mensagens de status do nsu_index são encodificáveis em CP1252 e CP850."""
        nsu = 100
        test_date = date(2026, 8, 1)

        # Formatos de mensagens usadas em nsu_index.py
        msg_ok = f"  NSU {nsu}: {test_date.strftime('%d/%m/%Y')} [OK]\n"
        msg_empty = f"  NSU {nsu}: sem dados (1/3)\n"
        msg_final = f"  NSU exato: {nsu} -> inicial: {nsu - 30}\n"

        for encoding in ['cp1252', 'cp850', 'ascii', 'utf-8']:
            errors_strategy = 'replace' if encoding == 'ascii' else 'strict'
            for msg in [msg_ok, msg_empty, msg_final]:
                try:
                    encoded = msg.encode(encoding, errors=errors_strategy)
                    self.assertIsInstance(encoded, bytes)
                except UnicodeEncodeError as e:
                    self.fail(f"Mensagem falhou ao encodificar para {encoding}: {e}")

    def test_stream_reconfigure_behavior(self):
        """Testa se o comportamento de reconfigure de stream com errors='replace' previne exceções."""
        buf = io.BytesIO()
        text_stream = io.TextIOWrapper(buf, encoding='cp1252', errors='replace')
        # Mesmo com caractere especial unicode não suportado, não deve levantar UnicodeEncodeError
        try:
            text_stream.write("Teste com símbolo especial: \u2713 e seta \u2192\n")
            text_stream.flush()
        except UnicodeEncodeError as e:
            self.fail(f"Stream com errors='replace' levantou UnicodeEncodeError: {e}")

        output = buf.getvalue().decode('cp1252')
        self.assertIn("Teste com símbolo especial: ? e seta ?", output)


if __name__ == "__main__":
    unittest.main()
