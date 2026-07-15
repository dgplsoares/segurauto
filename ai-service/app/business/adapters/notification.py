"""Notificações (DEC-ORB-037): fake default — loga o e-mail **mascarado**. O código só é ecoado no log em
`ENVIRONMENT=local` (dev affordance p/ smoke visual — "dev mail catcher"); fora de local, nunca. Real = pós-V1."""
import logging
from functools import lru_cache

from app.shared.config import get_settings

logger = logging.getLogger("segurauto.business")


def _mask(email: str) -> str:
    return (email[:2] + "***") if email else "-"


class FakeNotification:
    """Implementa `NotificationPort`. Registra envios (só o e-mail); o código só vai ao log em local (dev)."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_otp(self, *, email: str, code: str) -> None:
        self.sent.append({"email": email})
        logger.info("otp_sent email=%s", _mask(email))
        # Dev affordance SÓ em local (nunca em prod): ecoa o código para permitir o smoke visual do fluxo.
        if get_settings().environment == "local":
            logger.warning("otp_dev_echo email=%s code=%s", _mask(email), code)


@lru_cache
def get_notification() -> FakeNotification:
    return FakeNotification()  # V1: fake (singleton p/ observar envios nos testes)


def reset_notifications() -> None:
    get_notification.cache_clear()
