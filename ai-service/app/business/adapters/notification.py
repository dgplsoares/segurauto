"""Notificações (DEC-ORB-037/045/047).

Dois adapters do `NotificationPort`, escolhidos por `use_fake_notifications`:
- `FakeNotification` (default local/CI) — não envia; loga o destino **mascarado**. O código do OTP só é
  ecoado no log em `ENVIRONMENT=local` (dev "mail catcher"); fora de local, nunca.
- `SmtpNotification` (real, opt-in `USE_FAKE_NOTIFICATIONS=0`) — envia por **SMTP genérico** (`aiosmtplib`,
  import lazy). O provider é **infra trocável por `.env`**: o código só fala SMTP, nunca conhece o fornecedor.

Semântica de falha deliberada: `send_otp` **engole** a falha de entrega (preserva o 202 neutro do
`request_otp` — não vaza existência de e-mail, não dá 500); `notify(email)` **levanta** (a outbox retenta
at-least-once); `notify(whatsapp|sms)` = no-op fake (pronto p/ V2). Cabeçalhos são **saneados** (sem CRLF
vindo do destinatário → anti header-injection); PII nunca é logada crua.
"""
import html
import logging
import secrets
from email.message import EmailMessage
from email.utils import parseaddr
from functools import lru_cache

from app.business.ports import NotificationPort
from app.shared.config import get_settings

logger = logging.getLogger("segurauto.business")


def _mask(to: str) -> str:
    """Mascara e-mail OU telefone (nunca logar destino cru — inv.10)."""
    if not to:
        return "-"
    return (to[:2] + "***") if "@" in to else ("***" + to[-4:])


def _no_crlf(value: str) -> str:
    """Remove CR/LF de valores que viram cabeçalho de e-mail (anti header-injection): um cabeçalho não pode
    conter quebras de linha vindas de dado externo (ex.: destinatário/assunto)."""
    return value.replace("\r", " ").replace("\n", " ").strip()


# --- Templates (HTML inline, branding SegurAuto neutro; nenhuma dependência de provider) ------------------

_BRAND = "#1e5aa8"


def _wrap_html(title: str, body_html: str) -> str:
    """Moldura HTML comum (header/rodapé SegurAuto). `title`/`body_html` são conteúdo controlado por nós."""
    return f"""\
<!doctype html>
<html lang="pt-BR"><body style="margin:0;background:#f4f6f8;font-family:Arial,Helvetica,sans-serif;color:#1a2b3c">
  <div style="max-width:520px;margin:0 auto;padding:24px">
    <div style="background:#fff;border-radius:12px;padding:32px;border:1px solid #e5e9ef">
      <div style="font-size:20px;font-weight:700;color:{_BRAND};margin-bottom:16px">SegurAuto</div>
      <h1 style="font-size:18px;margin:0 0 12px">{title}</h1>
      {body_html}
    </div>
    <p style="font-size:12px;color:#8a97a8;text-align:center;margin-top:16px">
      Este e-mail foi enviado automaticamente. Por favor, não responda.
    </p>
  </div>
</body></html>"""


def _otp_email(code: str, ttl_minutes: int) -> tuple[str, str, str]:
    subject = "Seu código de acesso — SegurAuto"
    text = (
        f"Seu código de acesso SegurAuto é {code}.\n"
        f"Ele expira em {ttl_minutes} minutos.\n\n"
        "Se você não solicitou este código, ignore este e-mail."
    )
    body = (
        '<p>Use o código abaixo para acessar sua cotação:</p>'
        f'<div style="font-size:32px;font-weight:700;letter-spacing:6px;text-align:center;background:#f4f6f8;'
        f'border-radius:8px;padding:16px;margin:16px 0;color:{_BRAND}">{html.escape(code)}</div>'
        f'<p style="color:#5a6b7c;font-size:14px">Ele expira em {ttl_minutes} minutos. '
        "Se você não solicitou, ignore este e-mail.</p>"
    )
    return subject, text, _wrap_html("Seu código de acesso", body)


def _quote_confirmation_email(context: dict) -> tuple[str, str, str]:
    vehicle = str((context or {}).get("vehicle") or "seu veículo")
    subject = "Recebemos seu interesse — SegurAuto"
    text = (
        f"Recebemos seu interesse em contratar o seguro para {vehicle}.\n"
        "Um especialista dará sequência ao seu atendimento em breve."
    )
    body = (
        f"<p>Recebemos seu interesse em contratar o seguro para <strong>{html.escape(vehicle)}</strong>.</p>"
        '<p style="color:#5a6b7c;font-size:14px">Um especialista dará sequência ao seu atendimento em breve. '
        "Obrigado por escolher a SegurAuto.</p>"
    )
    return subject, text, _wrap_html("Recebemos seu interesse", body)


def _render(template: str, context: dict | None) -> tuple[str, str, str]:
    """Renderiza (assunto, texto, html) por nome de template. Fallback genérico não quebra o worker."""
    if template == "quote_confirmation":
        return _quote_confirmation_email(context or {})
    return "Atualização — SegurAuto", "Você tem uma atualização na sua cotação SegurAuto.", _wrap_html(
        "Atualização", "<p>Você tem uma atualização na sua cotação SegurAuto.</p>"
    )


# --- Adapters ---------------------------------------------------------------------------------------------


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
        """Envia uma notificação fake por `channel` (email/whatsapp/sms). Sem efeito real; `to` NUNCA é
        logado cru. O `message_id` é ALEATÓRIO (não derivado do destinatário) — evita que o audit, que o
        persiste, permita recuperar o telefone/e-mail por brute-force."""
        self.sent.append({"channel": channel, "template": template})
        message_id = f"{channel}_{secrets.token_hex(8)}"
        logger.info("notify_sent channel=%s to=%s template=%s", channel, _mask(to), template)
        return message_id


class SmtpNotification:
    """Implementa `NotificationPort` via **SMTP genérico** (`aiosmtplib`, import lazy). O provider é `.env`
    (o código não conhece o fornecedor). `send_otp` engole a falha (202 neutro); `notify(email)` levanta
    (a outbox retenta); canais não-email são no-op fake (prontos p/ V2)."""

    def __init__(self) -> None:
        s = get_settings()
        self.host = s.smtp_host
        self.port = s.smtp_port
        self.ssl = s.smtp_ssl
        self.user = s.smtp_user
        self.password = s.smtp_password
        self.timeout = s.smtp_timeout_s
        self.mail_from = s.mail_from
        self.bcc = s.mail_bcc
        self._sender_domain = parseaddr(self.mail_from)[1].split("@")[-1] or "segurauto"

    async def send_otp(self, *, email: str, code: str) -> None:
        ttl_minutes = max(1, get_settings().otp_ttl_s // 60)
        subject, text, html_body = _otp_email(code, ttl_minutes)
        try:
            await self._send(to=email, subject=subject, text=text, html=html_body)
            logger.info("otp_sent email=%s", _mask(email))
        except Exception as exc:
            # Engolir de propósito: `request_otp` responde SEMPRE 202 neutro — uma falha de SMTP não pode
            # vazar existência de e-mail nem virar 500. Ops vê o ERROR; o usuário reenvia. (nunca o código)
            logger.error("otp_send_failed email=%s error=%s", _mask(email), exc.__class__.__name__)

    async def notify(self, *, channel: str, to: str, template: str, context: dict | None = None) -> str:
        if channel != "email":
            # Sem provider real de WhatsApp/SMS ainda — no-op (pronto p/ V2 plugar sem tocar o port).
            logger.info("notify_skipped channel=%s to=%s template=%s", channel, _mask(to), template)
            return f"{channel}_{secrets.token_hex(8)}"
        message_id = self._new_message_id()
        subject, text, html_body = _render(template, context)
        # Levanta em falha dura → a outbox (at-least-once) retenta o evento NOTIFY.
        await self._send(to=to, subject=subject, text=text, html=html_body, message_id=message_id)
        logger.info("notify_sent channel=email to=%s template=%s", _mask(to), template)
        return message_id  # ID próprio (não derivado do destinatário → audit não reversível)

    async def _send(
        self, *, to: str, subject: str, text: str, html: str, message_id: str | None = None
    ) -> None:
        import aiosmtplib  # lazy: o modo fake (local/CI) não precisa da dep

        msg = EmailMessage()
        msg["From"] = self.mail_from
        msg["To"] = _no_crlf(to)
        if self.bcc:
            msg["Bcc"] = _no_crlf(self.bcc)
        msg["Subject"] = _no_crlf(subject)
        msg["Message-ID"] = message_id or self._new_message_id()
        msg.set_content(text)
        msg.add_alternative(html, subtype="html")
        kwargs: dict = {
            "hostname": self.host,
            "port": self.port,
            "username": self.user or None,
            "password": self.password or None,
            "timeout": self.timeout,
        }
        # 465 = TLS implícito na conexão; 587 = STARTTLS (upgrade). Nunca os dois.
        if self.ssl:
            kwargs["use_tls"] = True
        else:
            kwargs["start_tls"] = True
        await aiosmtplib.send(msg, **kwargs)

    def _new_message_id(self) -> str:
        return f"<{secrets.token_hex(16)}@{self._sender_domain}>"


@lru_cache
def get_notification() -> NotificationPort:
    if get_settings().use_fake_notifications:
        return FakeNotification()  # local/CI: fake (singleton p/ observar envios nos testes)
    return SmtpNotification()  # deploy real: SMTP genérico, provider por .env (DEC-ORB-047)


def reset_notifications() -> None:
    get_notification.cache_clear()
