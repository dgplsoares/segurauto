"""Fase 5a.1 (revisão adversarial) — timeouts do pool do chat mapeados para status retryable (DEC-ORB-040).

Regressão do furo confirmado: asyncpg embrulha lock/statement_timeout como `DBAPIError` base (não
`OperationalError`), então o handler ramifica pelo `sqlstate`. Erro inesperado propaga (não é mascarado).
"""
from types import SimpleNamespace

from app.business.api.chat import concurrency_http_error


def _err(sqlstate):
    return SimpleNamespace(orig=SimpleNamespace(sqlstate=sqlstate))


def test_lock_timeout_maps_to_409_session_busy():
    mapped = concurrency_http_error(_err("55P03"))
    assert mapped is not None and mapped.status_code == 409 and mapped.detail == "session_busy"


def test_statement_timeout_maps_to_503():
    mapped = concurrency_http_error(_err("57014"))
    assert mapped is not None and mapped.status_code == 503


def test_unexpected_sqlstate_propagates():
    assert concurrency_http_error(_err("23505")) is None  # unique_violation → propaga (500), não mascara
    assert concurrency_http_error(SimpleNamespace(orig=None)) is None
