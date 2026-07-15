"""Notificações (DEC-ORB-037): fake default — loga o e-mail **mascarado**, **nunca** o código. Real = pós-V1."""
import logging
from functools import lru_cache

logger = logging.getLogger("segurauto.business")


def _mask(email: str) -> str:
    return (email[:2] + "***") if email else "-"


class FakeNotification:
    """Implementa `NotificationPort`. Registra envios (só o e-mail) para teste; jamais guarda/loga o código."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_otp(self, *, email: str, code: str) -> None:  # noqa: ARG002 — code recebido, nunca persistido
        self.sent.append({"email": email})
        logger.info("otp_sent email=%s", _mask(email))


@lru_cache
def get_notification() -> FakeNotification:
    return FakeNotification()  # V1: fake (singleton p/ observar envios nos testes)


def reset_notifications() -> None:
    get_notification.cache_clear()
