"""Contratos HTTP da captura de lead (DEC-ORB-011). Validação server-side no BFF→API."""
import re

from pydantic import BaseModel, EmailStr, Field, field_validator

_CLICK_ID_RE = re.compile(r"[^A-Za-z0-9._-]")  # gclid/fbclid vêm da URL → só charset seguro


class LeadCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    phone: str = Field(min_length=3, max_length=40)
    vehicle: str = Field(min_length=1, max_length=200)
    zipcode: str = Field(min_length=3, max_length=20)
    consent: bool
    source: str | None = Field(default=None, max_length=80)
    # Atribuição de campanha: gclid/fbclid capturado na LP (F6). Input da URL → sanitizado.
    click_id: str | None = Field(default=None, max_length=200)
    # Fallback caso o header Idempotency-Key não venha (o client da LP gera no load do form).
    idempotency_key: str | None = Field(default=None, max_length=64)

    @field_validator("consent")
    @classmethod
    def _consent_required(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("consentimento é obrigatório (LGPD)")
        return v

    @field_validator("click_id")
    @classmethod
    def _sanitize_click_id(cls, v: str | None) -> str | None:
        """Remove qualquer caractere fora do charset seguro e limita a 120 — nunca confiar na URL."""
        if v is None:
            return None
        cleaned = _CLICK_ID_RE.sub("", v)[:120]
        return cleaned or None


class LeadResponse(BaseModel):
    # NÃO expõe score/band (qualificação): dado de CRM calculado async — vazaria no dedup (LEAK-1/DEC-ORB-035).
    id: str
    status: str
    deduped: bool
