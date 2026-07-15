"""Contratos HTTP da captura de lead (DEC-ORB-011). Validação server-side no BFF→API."""
from pydantic import BaseModel, EmailStr, Field, field_validator


class LeadCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    phone: str = Field(min_length=3, max_length=40)
    vehicle: str = Field(min_length=1, max_length=200)
    zipcode: str = Field(min_length=3, max_length=20)
    consent: bool
    source: str | None = Field(default=None, max_length=80)
    # Fallback caso o header Idempotency-Key não venha (o client da LP gera no load do form).
    idempotency_key: str | None = Field(default=None, max_length=64)

    @field_validator("consent")
    @classmethod
    def _consent_required(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("consentimento é obrigatório (LGPD)")
        return v


class LeadResponse(BaseModel):
    id: str
    status: str
    deduped: bool
    score: int | None = None
    band: str | None = None
