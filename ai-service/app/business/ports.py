"""Portas de integração externa do contexto `business` (DEC-ORB-001/014).

Fake é o default; real é opt-in por `.env`. O domínio depende só destas interfaces.
"""
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class CrmSyncResult:
    external_id: str
    created: bool  # False => já existia (upsert idempotente)


@runtime_checkable
class CrmPort(Protocol):
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
    ) -> CrmSyncResult: ...

    async def price_quote(self, *, vehicle: str, zipcode: str) -> dict: ...


@dataclass(frozen=True)
class ConversionResult:
    event_id: str
    deduped: bool  # True => já enviado antes (idempotente)


@runtime_checkable
class AdsPort(Protocol):
    platform: str

    async def send_conversion(
        self, *, event_id: str, lead_id: str, value: float | None = None
    ) -> ConversionResult: ...
