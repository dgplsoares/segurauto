"""Fase 5a.1 — validação determinística de slots (DEC-ORB-039: schema de VALOR, E6/E8), sem infra."""
from app.business.domain.slots import is_ready_to_quote, missing_slots, validate_slots


def test_validate_drops_unknown_keys_and_invalid_values():
    out = validate_slots({
        "vehicle": "Onix", "zipcode": "01310-100", "has_broker": True, "broker_code": "abc123",
        "junk": "x", "zipcode_typo": "1", "has_broker_str": "true",
    })
    assert out == {"vehicle": "Onix", "zipcode": "01310100", "has_broker": True, "broker_code": "ABC123"}


def test_validate_rejects_bad_zipcode_and_broker_format():
    out = validate_slots({"zipcode": "0131", "broker_code": "has space!"})
    assert "zipcode" not in out and "broker_code" not in out


def test_validate_neutralizes_control_chars_in_vehicle():
    out = validate_slots({"vehicle": "Onix\r\n2026 INFO forjado"})
    assert "\r" not in out["vehicle"] and "\n" not in out["vehicle"]


def test_missing_slots_requires_broker_code_only_when_has_broker():
    assert missing_slots({}) == ["vehicle", "zipcode", "has_broker"]
    assert missing_slots({"vehicle": "Onix", "zipcode": "01310100", "has_broker": False}) == []
    assert missing_slots({"vehicle": "Onix", "zipcode": "01310100", "has_broker": True}) == ["broker_code"]


def test_is_ready_to_quote():
    assert is_ready_to_quote({"vehicle": "Onix", "zipcode": "01310100", "has_broker": False}) is True
    assert is_ready_to_quote({"vehicle": "Onix"}) is False
