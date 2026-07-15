"""CRM fake da seguradora: tabela de preços + upsert idempotente por `lead_id` (DEC-ORB-014).

O contrato (upsert idempotente) espelha o que o CRM real fará; o adapter real substitui este por
`.env` sem tocar no domínio.
"""
from functools import lru_cache

from app.business.ports import CrmSyncResult

# FAKE da V1: autorização = pertença a este set. O adapter REAL vincula o broker_code a um corretor
# autenticado/por-lead e aplica rate-limit (aqui é só um stub determinístico — DEC-ORB-043).
_AUTHORIZED_BROKERS = frozenset({"COR001", "COR002", "ABC123"})  # E6: broker_code autorizado server-side


class FakeCrm:
    """Implementa `CrmPort`. Estado em memória; `calls` para asserts de teste."""

    def __init__(self) -> None:
        self._store: dict[str, dict] = {}
        self.calls = 0

    async def upsert_lead(
        self,
        *,
        lead_id: str,
        name: str,
        email: str,
        phone: str,
        vehicle: str,
        zipcode: str,
        score: int | None,
        band: str | None,
    ) -> CrmSyncResult:
        self.calls += 1
        existed = lead_id in self._store
        self._store[lead_id] = {
            "lead_id": lead_id,
            "name": name,
            "email": email,
            "phone": phone,
            "vehicle": vehicle,
            "zipcode": zipcode,
            "score": score,
            "band": band,
        }
        return CrmSyncResult(external_id=f"crm_{lead_id[:8]}", created=not existed)

    async def update_signal(self, *, lead_id: str, signal: str) -> dict:
        """Envia um SINAL ao CRM (ex.: 'contract_requested') — o funil é do CRM, não nosso (DEC-ORB-034).
        Fake determinístico: registra e devolve o external_id + status."""
        self.calls += 1
        entry = self._store.setdefault(lead_id, {"lead_id": lead_id})
        entry["signal"] = signal
        return {"external_id": f"crm_{lead_id[:8]}", "status": "updated", "signal": signal}

    async def price_quote(self, *, vehicle: str, zipcode: str, broker_code: str | None = None) -> dict:
        """Tabela de preços fake, determinística por região (1º dígito do CEP). Desconto de 10% só para
        corretor **autorizado** (autorização server-side do `broker_code` — fecha o E6)."""
        base = 1200.0
        region_digit = int(zipcode[:1]) if zipcode[:1].isdigit() else 0
        factor = 1.0 + (region_digit % 5) * 0.1
        premium = base * factor
        broker_applied = bool(broker_code and broker_code.upper() in _AUTHORIZED_BROKERS)
        if broker_applied:
            premium *= 0.9
        return {
            "annual_premium": round(premium, 2), "currency": "BRL", "vehicle": vehicle,
            "zipcode": zipcode, "broker_applied": broker_applied,
        }


@lru_cache
def get_crm() -> FakeCrm:
    return FakeCrm()  # V1: fake sempre (real opt-in pós-V1)
