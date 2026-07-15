"""Fase 8e (DEC-ORB-047) — adapter SMTP genérico atrás do `NotificationPort`. Sem rede: injeta um módulo
`aiosmtplib` fake em `sys.modules` (o unit nem precisa do pacote instalado). Cobre: factory por flag;
`EmailMessage` bem-formado (multipart texto+html, código presente); semântica de falha (`send_otp` engole,
`notify(email)` levanta); canais não-email são no-op fake; e a defesa contra header-injection (CRLF)."""
import sys
import types
from types import SimpleNamespace

import pytest

import app.business.adapters.notification as notif_mod
from app.business.adapters.notification import (
    FakeNotification,
    SmtpNotification,
    get_notification,
    reset_notifications,
)


def _settings(**over) -> SimpleNamespace:
    base = dict(
        use_fake_notifications=False,
        environment="production",
        smtp_host="smtp.mailhost.test",
        smtp_port=465,
        smtp_ssl=True,
        smtp_user="user",
        smtp_password="secret",
        smtp_timeout_s=15,
        mail_from="SegurAuto <noreply@segurauto.test>",
        mail_bcc=None,
        otp_ttl_s=600,
    )
    base.update(over)
    return SimpleNamespace(**base)


class _Capture:
    """Stand-in de `aiosmtplib.send`: guarda a mensagem + kwargs; opcionalmente levanta (simula falha)."""

    def __init__(self, *, raises: Exception | None = None) -> None:
        self.messages: list = []
        self.kwargs: list[dict] = []
        self.raises = raises

    async def __call__(self, message, **kwargs):
        self.messages.append(message)
        self.kwargs.append(kwargs)
        if self.raises is not None:
            raise self.raises
        return ({}, "250 OK")


def _install_fake_smtp(monkeypatch, *, raises: Exception | None = None) -> _Capture:
    cap = _Capture(raises=raises)
    fake = types.ModuleType("aiosmtplib")
    fake.send = cap
    monkeypatch.setitem(sys.modules, "aiosmtplib", fake)
    return cap


@pytest.fixture(autouse=True)
def _reset_cache():
    reset_notifications()
    yield
    reset_notifications()


def test_factory_selects_adapter_by_flag(monkeypatch):
    monkeypatch.setattr(notif_mod, "get_settings", lambda: _settings(use_fake_notifications=True))
    reset_notifications()
    assert isinstance(get_notification(), FakeNotification)
    monkeypatch.setattr(notif_mod, "get_settings", lambda: _settings(use_fake_notifications=False))
    reset_notifications()
    assert isinstance(get_notification(), SmtpNotification)


async def test_send_otp_builds_wellformed_email(monkeypatch):
    cap = _install_fake_smtp(monkeypatch)
    monkeypatch.setattr(notif_mod, "get_settings", lambda: _settings())
    await SmtpNotification().send_otp(email="user@x.test", code="12345")

    assert len(cap.messages) == 1
    msg = cap.messages[0]
    assert msg["To"] == "user@x.test"
    assert "SegurAuto" in msg["From"]
    assert "código" in msg["Subject"]
    text = msg.get_body(preferencelist=("plain",)).get_content()
    html = msg.get_body(preferencelist=("html",)).get_content()
    assert "12345" in text and "12345" in html  # código nos dois corpos
    # 465 = TLS implícito; NUNCA STARTTLS junto (mutuamente exclusivos)
    assert cap.kwargs[0]["use_tls"] is True and cap.kwargs[0]["port"] == 465
    assert "start_tls" not in cap.kwargs[0]


async def test_send_otp_swallows_delivery_failure(monkeypatch):
    _install_fake_smtp(monkeypatch, raises=RuntimeError("smtp down"))
    monkeypatch.setattr(notif_mod, "get_settings", lambda: _settings())
    # NÃO deve levantar — preserva o 202 neutro do request_otp mesmo com o SMTP fora do ar.
    await SmtpNotification().send_otp(email="user@x.test", code="12345")


async def test_notify_email_sends_and_returns_opaque_id(monkeypatch):
    cap = _install_fake_smtp(monkeypatch)
    monkeypatch.setattr(notif_mod, "get_settings", lambda: _settings())
    mid = await SmtpNotification().notify(
        channel="email", to="lead@x.test", template="quote_confirmation", context={"vehicle": "Onix 2020"}
    )
    assert len(cap.messages) == 1
    html = cap.messages[0].get_body(preferencelist=("html",)).get_content()
    assert "Onix 2020" in html
    assert isinstance(mid, str) and mid and "lead@x.test" not in mid  # id não derivado do destinatário


async def test_notify_whatsapp_is_noop_fake(monkeypatch):
    cap = _install_fake_smtp(monkeypatch)
    monkeypatch.setattr(notif_mod, "get_settings", lambda: _settings())
    mid = await SmtpNotification().notify(
        channel="whatsapp", to="+5511999999999", template="quote_confirmation", context={}
    )
    assert cap.messages == []  # nada enviado por SMTP (sem provider real de WhatsApp)
    assert mid.startswith("whatsapp_")  # id fake, pronto p/ V2


async def test_notify_email_raises_on_hard_failure(monkeypatch):
    _install_fake_smtp(monkeypatch, raises=RuntimeError("smtp down"))
    monkeypatch.setattr(notif_mod, "get_settings", lambda: _settings())
    # Levanta → a outbox (at-least-once) retenta o evento NOTIFY.
    with pytest.raises(RuntimeError):
        await SmtpNotification().notify(
            channel="email", to="lead@x.test", template="quote_confirmation", context={"vehicle": "Gol"}
        )


def test_no_crlf_strips_newlines():
    # defesa PURA contra header-injection (não-vacuosa): nenhuma quebra sobrevive; \r\n → dois espaços.
    assert notif_mod._no_crlf("a@x.test\r\nBcc: evil@x.test") == "a@x.test  Bcc: evil@x.test"
    assert "\n" not in notif_mod._no_crlf("x\ny") and "\r" not in notif_mod._no_crlf("x\ry")


async def test_recipient_crlf_does_not_inject_headers(monkeypatch):
    cap = _install_fake_smtp(monkeypatch)
    monkeypatch.setattr(notif_mod, "get_settings", lambda: _settings())
    await SmtpNotification().notify(
        channel="email", to="a@x.test\r\nBcc: evil@x.test", template="quote_confirmation", context={}
    )
    to_hdr = str(cap.messages[0]["To"])
    assert "\r" not in to_hdr and "\n" not in to_hdr  # To saneado no envio → sem injeção de header
    assert cap.messages[0]["Bcc"] is None  # o payload não virou um Bcc real


async def test_bcc_header_set_and_crlf_sanitized(monkeypatch):
    cap = _install_fake_smtp(monkeypatch)
    monkeypatch.setattr(notif_mod, "get_settings", lambda: _settings(mail_bcc="audit@x.test\r\nX-Evil: 1"))
    await SmtpNotification().notify(
        channel="email", to="lead@x.test", template="quote_confirmation", context={}
    )
    msg = cap.messages[0]
    assert msg["Bcc"] is not None and "audit@x.test" in msg["Bcc"]  # caminho do Bcc exercitado
    assert "\r" not in msg["Bcc"] and "\n" not in msg["Bcc"]  # CRLF saneado também no Bcc


async def test_starttls_path_uses_start_tls_not_use_tls(monkeypatch):
    cap = _install_fake_smtp(monkeypatch)
    monkeypatch.setattr(notif_mod, "get_settings", lambda: _settings(smtp_ssl=False, smtp_port=587))
    await SmtpNotification().send_otp(email="u@x.test", code="12345")
    kw = cap.kwargs[0]
    # 587 = STARTTLS; NUNCA TLS implícito junto (mutuamente exclusivos)
    assert kw["start_tls"] is True and "use_tls" not in kw and kw["port"] == 587


async def test_vehicle_is_html_escaped_in_body(monkeypatch):
    cap = _install_fake_smtp(monkeypatch)
    monkeypatch.setattr(notif_mod, "get_settings", lambda: _settings())
    await SmtpNotification().notify(
        channel="email", to="lead@x.test", template="quote_confirmation",
        context={"vehicle": "<script>alert(1)</script>"},
    )
    html = cap.messages[0].get_body(preferencelist=("html",)).get_content()
    assert "<script>alert(1)</script>" not in html  # conteúdo do lead não injeta HTML cru
    assert "&lt;script&gt;" in html  # escapado (html.escape do vehicle)
