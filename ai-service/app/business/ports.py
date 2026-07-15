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

    async def price_quote(self, *, vehicle: str, zipcode: str, broker_code: str | None = None) -> dict: ...


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


@runtime_checkable
class NotificationPort(Protocol):
    """Envio de notificações (OTP na V1; email/WhatsApp/SMS na F6). Fake default / real pós-V1."""

    async def send_otp(self, *, email: str, code: str) -> None: ...
