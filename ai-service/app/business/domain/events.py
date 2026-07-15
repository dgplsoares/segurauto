"""Intents da outbox e derivação de `event_id` estável (DEC-ORB-012/014)."""
import hashlib
from enum import Enum


class IntentType(str, Enum):
    QUALIFY = "qualify"
    CRM_SYNC = "crm_sync"
    ADS_META = "ads_meta"
    ADS_GOOGLE = "ads_google"
    # F6 — ações write-through-outbox disparadas pela confirmação explícita do lead (DEC-ORB-045):
    NOTIFY = "notify"          # confirmação ao lead (email/WhatsApp/SMS via NotificationPort fake)
    CONVERSION = "conversion"  # conversão de INTENÇÃO DE CONTRATO às plataformas de anúncio (mais forte)
    CRM_UPDATE = "crm_update"  # sinal ao CRM ("lead pediu contato") — não gerimos o funil aqui (DEC-ORB-034)
    HANDOFF = "handoff"        # transferência para corretor humano


def conversion_event_id(lead_id: str, platform: str) -> str:
    """`event_id` determinístico por (lead, plataforma) → dedup nas plataformas de anúncios.

    Duas tentativas de enviar a MESMA conversão geram o mesmo id → a plataforma (e o fake) deduplica.
    """
    digest = hashlib.sha256(f"{lead_id}:{platform}".encode()).hexdigest()
    return digest[:32]


def action_event_id(session_id: str, kind: str, platform: str) -> str:
    """`event_id` de ação por (sessão, tipo, plataforma) — DISTINTO da conversão de qualify (que usa
    `conversion_event_id` por lead), para não deduplicar uma contra a outra. Idempotente por sessão."""
    digest = hashlib.sha256(f"{session_id}:{kind}:{platform}".encode()).hexdigest()
    return digest[:32]
