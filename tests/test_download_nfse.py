import unittest
import base64
import gzip

from download_nfse import extract_xml

class TestExtractXML(unittest.TestCase):
    def setUp(self):
        self.plain_xml = "<?xml version='1.0'?><nota>123</nota>"
        self.b64_xml = base64.b64encode(self.plain_xml.encode('utf-8')).decode('utf-8')

        # Create gzipped xml
        compressed = gzip.compress(self.plain_xml.encode('utf-8'))
        self.gzipped_b64_xml = base64.b64encode(compressed).decode('utf-8')

    def test_non_dict_input(self):
        """Should return None if input is not a dictionary"""
        self.assertIsNone(extract_xml(None))
        self.assertIsNone(extract_xml([]))
        self.assertIsNone(extract_xml("string"))
        self.assertIsNone(extract_xml(123))

    def test_empty_dict(self):
        """Should return None for empty dictionary"""
        self.assertIsNone(extract_xml({}))

    def test_plain_xml_standard_key(self):
        """Should find plain XML in standard keys like 'xml', 'conteudo'"""
        data = {'xml': self.plain_xml}
        self.assertEqual(extract_xml(data), self.plain_xml)

        data = {'conteudo': self.plain_xml}
        self.assertEqual(extract_xml(data), self.plain_xml)

    def test_plain_xml_dynamic_key(self):
        """Should find plain XML in keys containing 'xml' or 'conteudo'"""
        data = {'meu_XML_aqui': self.plain_xml}
        self.assertEqual(extract_xml(data), self.plain_xml)

        data = {'algum_Conteudo_extra': self.plain_xml}
        self.assertEqual(extract_xml(data), self.plain_xml)

    def test_plain_xml_starts_with_angle_bracket(self):
        """Should find plain XML that starts with < but not <?xml"""
        xml = "<nota>123</nota>"
        data = {'xml': xml}
        self.assertEqual(extract_xml(data), xml)

    def test_base64_xml(self):
        """Should decode and return base64 encoded XML"""
        data = {'xmlB64': self.b64_xml}
        self.assertEqual(extract_xml(data), self.plain_xml)

    def test_gzipped_base64_xml(self):
        """Should decompress and decode gzipped base64 XML"""
        data = {'xmlNfse': self.gzipped_b64_xml}
        self.assertEqual(extract_xml(data), self.plain_xml)

    def test_invalid_values(self):
        """Should skip invalid values (None, integers, non-xml strings)"""
        data = {
            'xml': None,
            'conteudo': 123,
            'documento': "not an xml string",
            'xml_documento': ""
        }
        self.assertIsNone(extract_xml(data))

    def test_invalid_base64(self):
        """Should handle invalid base64 strings gracefully"""
        data = {
            'xmlB64': "invalid base64 string ###",
            'conteudo': self.plain_xml  # Fallback to next key
        }
        self.assertEqual(extract_xml(data), self.plain_xml)

    def test_invalid_gzip(self):
        """Should handle invalid gzip data gracefully"""
        # Create a payload that starts with gzip magic number but is invalid
        bad_gzip = b'\x1f\x8b\x08\x00' + b'bad data'
        bad_gzip_b64 = base64.b64encode(bad_gzip).decode('utf-8')

        data = {
            'xmlB64': bad_gzip_b64,
            'xml': self.plain_xml  # Fallback
        }
        self.assertEqual(extract_xml(data), self.plain_xml)

if __name__ == '__main__':
    unittest.main()
