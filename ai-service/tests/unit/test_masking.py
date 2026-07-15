"""Fase 5a.2 — masking de PII estendido (E8): CEP/telefone/placa case-insensitive SEM corromper UUID/ids,
redação de tracebacks e anti log-forging (achados da revisão adversarial)."""
import logging
import sys
import uuid

from app.shared.observability import PiiRedactingFilter, redact_pii


def test_masks_cep_phone_and_lowercase_plate():
    assert redact_pii("cep 01310-100") == "cep [cep]"
    assert redact_pii("telefone (11) 98765-4321") == "telefone [telefone]"
    assert redact_pii("placa abc1d23") == "placa [placa]"  # minúscula (E8)
    assert redact_pii("placa ABC1D23") == "placa [placa]"


def test_masks_email_and_cpf():
    assert redact_pii("contato ana@example.com") == "contato [email]"
    assert redact_pii("cpf 123.456.789-00") == "cpf [cpf]"


def test_does_not_corrupt_uuid_or_request_id():
    # DEC-ORB-036: a correlação (lead_id com hífens, request_id = hex sem hífen) não pode ser redigida.
    samples = [
        "550e8400-e29b-41d4-a716-446655440000",
        "12345678-1234-1234-1234-123456789012",  # segmentos só de dígitos
        "00000000-0000-0000-0000-000000000000",
        uuid.uuid4().hex,
    ]
    for token in samples:
        assert redact_pii(f"rid={token} ok") == f"rid={token} ok", token


def test_filter_redacts_pii_in_traceback():
    try:
        raise ValueError("falha com ana@example.com e cep 01310-100")
    except ValueError:
        rec = logging.LogRecord("n", logging.ERROR, __file__, 1, "erro", None, sys.exc_info())
    PiiRedactingFilter().filter(rec)
    assert rec.exc_text and "[email]" in rec.exc_text and "[cep]" in rec.exc_text
    assert "ana@example.com" not in rec.exc_text


def test_filter_collapses_crlf_in_message():
    rec = logging.LogRecord("n", logging.INFO, __file__, 1, "linha1\r\nFAKE LOG forjado", None, None)
    PiiRedactingFilter().filter(rec)
    assert "\n" not in rec.msg and "\r" not in rec.msg
