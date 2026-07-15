"""Notificações (DEC-ORB-037/045): fake default — loga o destino **mascarado**. O código do OTP só é ecoado
no log em `ENVIRONMENT=local` (dev affordance p/ smoke visual — "dev mail catcher"); fora de local, nunca.
Na F6 ganha `notify` multi-canal (email/WhatsApp/SMS) para a confirmação de contrato. Real = pós-V1."""
import hashlib
import logging
from functools import lru_cache

from app.shared.config import get_settings

logger = logging.getLogger("segurauto.business")


def _mask(to: str) -> str:
    """Mascara e-mail OU telefone (nunca logar destino cru — inv.10)."""
    if not to:
        return "-"
    return (to[:2] + "***") if "@" in to else ("***" + to[-4:])


class FakeNotification:
    """Implementa `NotificationPort`. Registra envios (só canal+destino mascarado); o código do OTP só vai
    ao log em local (dev). `notify` (F6) devolve um `message_id` fake determinístico."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_otp(self, *, email: str, code: str) -> None:
        self.sent.append({"channel": "email", "email": email})
        logger.info("otp_sent email=%s", _mask(email))
        # Dev affordance SÓ em local (nunca em prod): ecoa o código para permitir o smoke visual do fluxo.
        if get_settings().environment == "local":
            logger.warning("otp_dev_echo email=%s code=%s", _mask(email), code)

    async def notify(self, *, channel: str, to: str, template: str, context: dict | None = None) -> str:
        """Envia uma notificação fake por `channel` (email/whatsapp/sms). Determinístico e sem efeito real;
        `to` NUNCA é logado cru. Retorna um `message_id` estável por (canal, destino, template)."""
        self.sent.append({"channel": channel, "template": template})
        message_id = f"{channel}_{hashlib.sha256(f'{channel}:{to}:{template}'.encode()).hexdigest()[:16]}"
        logger.info("notify_sent channel=%s to=%s template=%s", channel, _mask(to), template)
        return message_id


@lru_cache
def get_notification() -> FakeNotification:
    return FakeNotification()  # V1: fake (singleton p/ observar envios nos testes)


def reset_notifications() -> None:
    get_notification.cache_clear()
