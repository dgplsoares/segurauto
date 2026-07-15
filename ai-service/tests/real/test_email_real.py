"""Teste de e-mail REAL (DEC-ORB-047) — **opt-in**, NÃO roda no CI.

Pulado a menos que `USE_FAKE_NOTIFICATIONS=0` + `SMTP_HOST` + um destinatário de teste `MAIL_TEST_TO`
estejam no ambiente. Envia por SMTP de verdade (usa a cota do provider) — verifique a inbox. Ex.:

    USE_FAKE_NOTIFICATIONS=0 SMTP_HOST=... SMTP_USER=... SMTP_PASSWORD=... \\
    MAIL_FROM='SegurAuto <noreply@seu-dominio>' MAIL_TEST_TO=voce@exemplo pytest ai-service/tests/real -q
"""
import os

import pytest

from app.business.adapters.notification import SmtpNotification
from app.shared.config import get_settings


def _target() -> str | None:
    s = get_settings()
    to = os.getenv("MAIL_TEST_TO")
    if not s.use_fake_notifications and s.smtp_host and to:
        return to
    return None


@pytest.mark.skipif(_target() is None, reason="opt-in: exige USE_FAKE_NOTIFICATIONS=0 + SMTP_* + MAIL_TEST_TO")
async def test_real_smtp_delivers():
    to = _target()
    # notify(email) LEVANTA em falha → o smoke falha alto se o SMTP estiver mal configurado.
    mid = await SmtpNotification().notify(
        channel="email", to=to, template="quote_confirmation", context={"vehicle": "Teste SegurAuto"}
    )
    assert isinstance(mid, str) and mid
