import pytest
from download_nfse import get_nfse_number

def test_get_nfse_number_happy_path():
    """Test standard tags for nfse number without namespaces"""
    xml_numero = "<Root><numero>12345</numero></Root>"
    assert get_nfse_number(xml_numero) == "12345"

    xml_nnfse = "<Root><nnfse>67890</nnfse></Root>"
    assert get_nfse_number(xml_nnfse) == "67890"

    xml_numeronfse = "<Root><numeronfse>11111</numeronfse></Root>"
    assert get_nfse_number(xml_numeronfse) == "11111"

def test_get_nfse_number_case_insensitivity():
    """Test that tag names are case insensitive"""
    xml_mixed = "<Root><NuMeRo>99999</NuMeRo></Root>"
    assert get_nfse_number(xml_mixed) == "99999"

    xml_upper = "<Root><NUMERONFSE>88888</NUMERONFSE></Root>"
    assert get_nfse_number(xml_upper) == "88888"

def test_get_nfse_number_with_namespaces():
    """Test tags with namespaces"""
    xml_ns = '<ns1:Root xmlns:ns1="http://example.com/ns1"><ns1:numero>12345</ns1:numero></ns1:Root>'
    assert get_nfse_number(xml_ns) == "12345"

    xml_default_ns = '<Root xmlns="http://example.com/default"><nnfse>54321</nnfse></Root>'
    assert get_nfse_number(xml_default_ns) == "54321"

def test_get_nfse_number_strip_whitespace():
    """Test that whitespace is stripped from the extracted number"""
    xml_space = "<Root><numero>  12345 \n </numero></Root>"
    assert get_nfse_number(xml_space) == "12345"

def test_get_nfse_number_missing_tag():
    """Test when the expected tags are not present"""
    xml_missing = "<Root><other_tag>12345</other_tag></Root>"
    assert get_nfse_number(xml_missing) is None

def test_get_nfse_number_empty_tag():
    """Test when the expected tag exists but is empty"""
    xml_empty = "<Root><numero></numero></Root>"
    assert get_nfse_number(xml_empty) is None

    xml_whitespace = "<Root><numero>   </numero></Root>"
    assert get_nfse_number(xml_whitespace) is None

def test_get_nfse_number_malformed_xml():
    """Test behavior with malformed or invalid XML strings"""
    xml_malformed = "<Root><numero>12345</Root>"
    assert get_nfse_number(xml_malformed) is None

    assert get_nfse_number("") is None
    assert get_nfse_number(None) is None
