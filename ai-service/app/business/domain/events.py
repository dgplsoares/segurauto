"""Intents da outbox e derivação de `event_id` estável (DEC-ORB-012/014)."""
import hashlib
from enum import Enum


class IntentType(str, Enum):
    QUALIFY = "qualify"
    CRM_SYNC = "crm_sync"
    ADS_META = "ads_meta"
    ADS_GOOGLE = "ads_google"


def conversion_event_id(lead_id: str, platform: str) -> str:
    """`event_id` determinístico por (lead, plataforma) → dedup nas plataformas de anúncios.

    Duas tentativas de enviar a MESMA conversão geram o mesmo id → a plataforma (e o fake) deduplica.
    """
    digest = hashlib.sha256(f"{lead_id}:{platform}".encode()).hexdigest()
    return digest[:32]
