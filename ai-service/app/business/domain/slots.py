"""Slots da conversa de cotação (DEC-ORB-039): validação **determinística** de VALOR.

O valor de cada slot é validado por schema **antes** de persistir/alimentar tools (fecha o slot poisoning —
E6). Texto do usuário é dado não-confiável: valor fora do schema é **descartado**. `broker_code` é validado
só quanto ao **formato** aqui — a autorização (existência/posse no CRM) é da F5b.
"""
import re

SLOT_KEYS = ("vehicle", "zipcode", "has_broker", "broker_code")

_ZIP_RE = re.compile(r"^\d{5}-?\d{3}$")
_BROKER_RE = re.compile(r"^[A-Za-z0-9]{1,20}$")
# vehicle = placa ou marca/modelo: alfanumérico + espaço/./-/ (rejeita pontuação/injeção tipo ;<>{}), cap 80.
_VEHICLE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ./-]{0,79}$")
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")  # CR/LF/controle — anti log-forging (E8)
_VEHICLE_MAX = 80

# Extração determinística (E6): reconhece valores no texto por padrão — NUNCA por LLM.
_PLATE_TEXT_RE = re.compile(r"\b([A-Za-z]{3}-?\d[A-Za-z0-9]\d{2})\b")
_CEP_TEXT_RE = re.compile(r"\b(\d{5}-?\d{3})\b")
_NO_BROKER_RE = re.compile(r"(?i)\b(n[ãa]o\s+tenho|sem|nenhum)\s+corretor")
_HAS_BROKER_RE = re.compile(r"(?i)\b(tenho|com|meu|j[áa]\s+tenho)\s+corretor")
# tolera "é/:/=" entre "código" e o valor; lookahead negativo evita falsos-positivos ("código postal" = CEP).
_BROKER_CODE_RE = re.compile(
    r"(?i)c[óo]digo(?!\s+postal|\s+de\s+barras|\s+de\s+[áa]rea)[^A-Za-z0-9]{0,4}([A-Za-z0-9]{3,20})"
)
# Resposta CURTA (sim/não) — só interpretada quando a pergunta do corretor acabou de ser feita (contexto).
_YES_RE = re.compile(r"(?i)^\s*(sim|tenho|claro|com certeza|possuo|positivo|afirmativo)\b")
_NO_RE = re.compile(r"(?i)^\s*(n[ãa]o|nao|nunca|negativo|sem)\b")


def _clean(value: str, maxlen: int) -> str:
    return _CONTROL_RE.sub(" ", value).strip()[:maxlen]


def validate_slots(raw: dict) -> dict:
    """Mantém só chaves conhecidas com VALOR válido (descarta o resto). Nunca confia no valor cru."""
    out: dict = {}
    if not isinstance(raw, dict):
        return out
    if isinstance(raw.get("vehicle"), str):
        vehicle = _clean(raw["vehicle"], _VEHICLE_MAX)
        if vehicle and _VEHICLE_RE.match(vehicle):  # schema de VALOR (E6): descarta pontuação/injeção
            out["vehicle"] = vehicle
    zipcode = raw.get("zipcode")
    if isinstance(zipcode, str) and _ZIP_RE.match(zipcode.strip()):
        out["zipcode"] = re.sub(r"\D", "", zipcode)  # 8 dígitos
    if isinstance(raw.get("has_broker"), bool):
        out["has_broker"] = raw["has_broker"]
    broker = raw.get("broker_code")
    if isinstance(broker, str) and _BROKER_RE.match(broker.strip()):
        out["broker_code"] = broker.strip().upper()
    # Invariante cross-field: broker_code só existe quando has_broker é True (senão descarta código stale).
    if out.get("has_broker") is not True:
        out.pop("broker_code", None)
    return out


def missing_slots(slots: dict) -> list[str]:
    """Slots ainda necessários para 'pronto para cotar'. `broker_code` só se `has_broker` é True."""
    missing = [k for k in ("vehicle", "zipcode", "has_broker") if k not in slots]
    if slots.get("has_broker") is True and "broker_code" not in slots:
        missing.append("broker_code")
    return missing


def is_ready_to_quote(slots: dict) -> bool:
    return not missing_slots(slots)


def extract_slots_from_text(text: str, expected_slot: str | None = None) -> dict:
    """Extração DETERMINÍSTICA (E6) dos slots presentes no texto — nunca por LLM. Retorna só o que
    reconhece, já validado por `validate_slots`. `broker_code` fica só no formato (autorização = F5b).
    `expected_slot` = slot que o agente acabou de perguntar; permite entender um "sim/não" curto no
    contexto certo (ex.: resposta à pergunta do corretor)."""
    found: dict = {}
    plate = _PLATE_TEXT_RE.search(text)
    if plate:
        found["vehicle"] = plate.group(1)
    cep = _CEP_TEXT_RE.search(text)
    if cep:
        found["zipcode"] = cep.group(1)
    if _NO_BROKER_RE.search(text):
        found["has_broker"] = False
    elif _HAS_BROKER_RE.search(text):
        found["has_broker"] = True
    elif expected_slot == "has_broker":
        # A pergunta do corretor foi feita agora → aceita resposta curta "sim/não".
        if _NO_RE.match(text):
            found["has_broker"] = False
        elif _YES_RE.match(text):
            found["has_broker"] = True
    code = _BROKER_CODE_RE.search(text)
    if code:
        found["broker_code"] = code.group(1)
    return validate_slots(found)
