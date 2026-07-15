"""Slots da conversa de cotação (DEC-ORB-039): validação **determinística** de VALOR.

O valor de cada slot é validado por schema **antes** de persistir/alimentar tools (fecha o slot poisoning —
E6). Texto do usuário é dado não-confiável: valor fora do schema é **descartado**. `broker_code` é validado
só quanto ao **formato** aqui — a autorização (existência/posse no CRM) é da F5b.
"""
import re

SLOT_KEYS = ("vehicle", "zipcode", "has_broker", "broker_code")

_ZIP_RE = re.compile(r"^\d{5}-?\d{3}$")
_BROKER_RE = re.compile(r"^[A-Za-z0-9]{1,20}$")
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")  # CR/LF/controle — anti log-forging (E8)
_VEHICLE_MAX = 80


def _clean(value: str, maxlen: int) -> str:
    return _CONTROL_RE.sub(" ", value).strip()[:maxlen]


def validate_slots(raw: dict) -> dict:
    """Mantém só chaves conhecidas com VALOR válido (descarta o resto). Nunca confia no valor cru."""
    out: dict = {}
    if not isinstance(raw, dict):
        return out
    if isinstance(raw.get("vehicle"), str):
        vehicle = _clean(raw["vehicle"], _VEHICLE_MAX)
        if vehicle:
            out["vehicle"] = vehicle
    zipcode = raw.get("zipcode")
    if isinstance(zipcode, str) and _ZIP_RE.match(zipcode.strip()):
        out["zipcode"] = re.sub(r"\D", "", zipcode)  # 8 dígitos
    if isinstance(raw.get("has_broker"), bool):
        out["has_broker"] = raw["has_broker"]
    broker = raw.get("broker_code")
    if isinstance(broker, str) and _BROKER_RE.match(broker.strip()):
        out["broker_code"] = broker.strip().upper()
    return out


def missing_slots(slots: dict) -> list[str]:
    """Slots ainda necessários para 'pronto para cotar'. `broker_code` só se `has_broker` é True."""
    missing = [k for k in ("vehicle", "zipcode", "has_broker") if k not in slots]
    if slots.get("has_broker") is True and "broker_code" not in slots:
        missing.append("broker_code")
    return missing


def is_ready_to_quote(slots: dict) -> bool:
    return not missing_slots(slots)
