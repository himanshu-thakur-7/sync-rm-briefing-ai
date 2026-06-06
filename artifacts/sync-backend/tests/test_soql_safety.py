"""SOQL injection safety tests for the Salesforce adapter.

The _escape_id() helper must reject any ID that isn't 15 or 18 alphanumeric
characters. A malicious payload like "x' OR '1'='1" must raise ValueError
before it reaches any SOQL string.
"""
import pytest
from adapters.salesforce import _escape_id


VALID_IDS = [
    "003Dn00000ABCDE",       # 15-char SF ID
    "003Dn00000ABCDEfgh",    # 18-char SF ID
    "0012300001AbCdEfAA",    # mixed-case 18-char
]

MALICIOUS_INPUTS = [
    "x' OR '1'='1",
    "'; DROP TABLE Contact;--",
    "1 UNION SELECT Id FROM User",
    "",
    "a b c",
    "abc-def-ghi",
    "a" * 19,  # too long
    "a" * 14,  # too short
]


@pytest.mark.parametrize("valid_id", VALID_IDS)
def test_valid_sf_ids_pass(valid_id):
    assert _escape_id(valid_id) == valid_id


@pytest.mark.parametrize("bad_input", MALICIOUS_INPUTS)
def test_malicious_inputs_rejected(bad_input):
    with pytest.raises(ValueError, match="Invalid Salesforce ID"):
        _escape_id(bad_input)
