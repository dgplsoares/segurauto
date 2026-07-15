"""Seed de demo (DEC-ORB-042): um comando gera uma jornada COMPLETA de ponta a ponta.

Dirige o fluxo REAL (não fabrica linhas): captura o lead → worker (qualifica + CRM + Ads) → OTP (evento
`notify_otp`) → identidade canônica + sessão autenticada → conversa de cotação (slots → cotação + evento
`crm_price_quote`). Ao final imprime o e-mail e as URLs da jornada.

A verificação do OTP usa um ATALHO de dev: o código só é ecoado no log (em `local`), então em vez de
"digitar" o token, o seed insere a identidade canônica + a sessão diretamente. Todo o resto é o fluxo de
produção. Rodar:  docker compose exec ai-service python -m app.eval.seed
"""
import asyncio
import datetime as dt
import uuid

from app.business.adapters.notification import get_notification
from app.business.repository.auth_repository import AuthRepository
from app.business.repository.chat_repository import ChatRepository
from app.business.repository.lead_repository import LeadRepository
from app.business.service.auth_service import AuthService
from app.business.service.chat_service import ChatService
from app.business.service.lead_service import LeadService
from app.business.worker import drain_once
from app.shared.database import get_sessionmaker
from app.shared.security import new_session_token, token_pk

_TURNS = [
    "Olá! Gostaria de cotar um seguro para o meu carro.",
    "a placa é ABC1D23",
    "meu CEP é 01310-100",
    "não tenho corretor",
]


async def seed_demo() -> str:
    """Gera uma jornada completa e retorna o e-mail (único por execução)."""
    sm = get_sessionmaker()
    email = f"demo-{uuid.uuid4().hex[:8]}@segurauto.example"

    # 1) Captura o lead (enfileira QUALIFY na outbox, mesma transação).
    async with sm() as s:
        lead, _ = await LeadService(LeadRepository(s)).capture(
            idempotency_key=uuid.uuid4().hex,
            name="Cliente Demo",
            email=email,
            phone="11999990000",
            vehicle="Chevrolet Onix 2022",
            zipcode="01310-100",
            consent=True,
            source="meta",
        )
        await s.commit()
        lead_id = lead.id

    # 2) Worker: QUALIFY cascateia para CRM_SYNC + ADS (integration_events crm_sync/ads_conversion).
    await drain_once(sm)

    # 3) OTP: produz um evento `notify_otp` realista (exige o lead já existente; nunca grava o código).
    async with sm() as s:
        await AuthService(AuthRepository(s), get_notification()).request_otp(email)
        await s.commit()

    # 4) Identidade canônica (DEC-ORB-041) + sessão autenticada — atalho de dev (o gate real é o OTP).
    async with sm() as s:
        repo = AuthRepository(s)
        await repo.insert_identity(email_normalized=email, canonical_lead_id=lead_id)
        token = new_session_token()
        now = dt.datetime.now(dt.timezone.utc)
        await repo.insert_session(
            token_hash=token_pk(token),
            lead_id=lead_id,
            expires_at=now + dt.timedelta(hours=1),
            absolute_expires_at=now + dt.timedelta(hours=12),
        )
        await s.commit()

    # 5) Conversa de cotação: cria a sessão e roda os turnos (slots → cotação automática + crm_price_quote).
    async with sm() as s:
        sess = await ChatRepository(s).create_session(lead_id=lead_id, slots={})
        await s.commit()
        session_id = sess.id
    for msg in _TURNS:
        async with sm() as s:
            await ChatService(ChatRepository(s)).run_turn(
                session_id=session_id, lead_id=lead_id, message=msg, client_turn_id=uuid.uuid4().hex
            )
            await s.commit()

    return email


def main() -> None:
    email = asyncio.run(seed_demo())
    base = "http://localhost:8000/eval/leads/journey"
    print("\n✓ Jornada de demo criada.")
    print(f"  e-mail: {email}")
    print(f"  JSON : {base}?email={email}")
    print(f"  HTML : {base}?email={email}&format=html")
    print("  Lista: http://localhost:8000/eval/leads\n")


if __name__ == "__main__":
    main()
