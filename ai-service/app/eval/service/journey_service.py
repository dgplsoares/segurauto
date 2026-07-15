"""Jornada agregada do lead (DEC-ORB-042).

Resolve um e-mail → conjunto de `lead_id`s (todas as linhas do e-mail ∪ a âncora canônica da identidade,
DEC-ORB-041) e coleta, por esses ids, tudo que os outros contextos já persistiram: linhas de lead,
sessões de chat + mensagens, cotações, intents da outbox e `integration_events` (DEC-ORB-044).

Read-only e sem lógica de domínio: apenas lê as tabelas de `business` e projeta dicts serializáveis.
Não é CRM/funil — a atribuição de estágio de venda vive no CRM (DEC-ORB-034).
"""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.business.repository.models import (
    ChatMessageRow,
    ChatSessionRow,
    IdentityRow,
    IntegrationEventRow,
    LeadRow,
    OutboxRow,
    QuoteRow,
)


def _lead_dict(r: LeadRow) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "email": r.email,
        "phone": r.phone,
        "vehicle": r.vehicle,
        "zipcode": r.zipcode,
        "consent": r.consent,
        "source": r.source,
        "status": r.status,
        "score": r.score,
        "band": r.band,
        "reason": r.reason,
        "created_at": r.created_at,
    }


def _session_dict(s: ChatSessionRow, messages: list[dict]) -> dict:
    return {
        "session_id": s.id,
        "lead_id": s.lead_id,
        "status": s.status,
        "slots": s.slots,
        "quote_ready_at": s.quote_ready_at,
        "handoff_requested_at": s.handoff_requested_at,
        "created_at": s.created_at,
        "last_turn_at": s.last_turn_at,
        "messages": messages,
    }


def _quote_dict(q: QuoteRow) -> dict:
    return {
        "quote_id": q.id,
        "session_id": q.session_id,
        "lead_id": q.lead_id,
        "premium_cents": q.premium_cents,
        "currency": q.currency,
        "coverages": q.coverages,
        "broker_applied": q.broker_applied,
        "pdf_ref": q.pdf_ref,
        "slots": q.slots,
        "created_at": q.created_at,
    }


class JourneyService:
    """Agrega a jornada do lead por e-mail. `session` é uma AsyncSession de leitura (pool principal)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def recent_leads(self, limit: int = 50) -> list[dict]:
        """Descoberta: leads mais recentes (o avaliador escolhe um e-mail para consultar a jornada)."""
        rows = (
            await self.session.execute(select(LeadRow).order_by(LeadRow.created_at.desc()).limit(limit))
        ).scalars().all()
        return [
            {
                "id": r.id,
                "name": r.name,
                "email": r.email,
                "status": r.status,
                "band": r.band,
                "source": r.source,
                "created_at": r.created_at,
            }
            for r in rows
        ]

    async def journey(self, email: str) -> dict | None:
        """Jornada completa do e-mail (case-insensitive). `None` se não houver lead algum."""
        norm = email.strip().lower()
        leads = (
            await self.session.execute(
                select(LeadRow).where(func.lower(LeadRow.email) == norm).order_by(LeadRow.created_at)
            )
        ).scalars().all()
        if not leads:
            return None

        ident = (
            await self.session.execute(select(IdentityRow).where(IdentityRow.email_normalized == norm))
        ).scalar_one_or_none()
        # Âncora canônica (DEC-ORB-041) quando há identidade verificada; senão, o lead mais recente.
        canonical = ident.canonical_lead_id if ident is not None else leads[-1].id
        lead_ids = list({lead.id for lead in leads} | {canonical})

        sessions = (
            await self.session.execute(
                select(ChatSessionRow)
                .where(ChatSessionRow.lead_id.in_(lead_ids))
                .order_by(ChatSessionRow.created_at)
            )
        ).scalars().all()
        session_ids = [s.id for s in sessions]

        by_session: dict[str, list[dict]] = {}
        if session_ids:
            msgs = (
                await self.session.execute(
                    select(ChatMessageRow)
                    .where(ChatMessageRow.session_id.in_(session_ids))
                    .order_by(ChatMessageRow.session_id, ChatMessageRow.seq)
                )
            ).scalars().all()
            for m in msgs:
                by_session.setdefault(m.session_id, []).append(
                    {"seq": m.seq, "role": m.role, "content": m.content, "created_at": m.created_at}
                )

        quotes = (
            await self.session.execute(
                select(QuoteRow).where(QuoteRow.lead_id.in_(lead_ids)).order_by(QuoteRow.created_at)
            )
        ).scalars().all()
        outbox = (
            await self.session.execute(
                select(OutboxRow).where(OutboxRow.lead_id.in_(lead_ids)).order_by(OutboxRow.created_at)
            )
        ).scalars().all()
        events = (
            await self.session.execute(
                select(IntegrationEventRow)
                .where(IntegrationEventRow.lead_id.in_(lead_ids))
                .order_by(IntegrationEventRow.created_at)
            )
        ).scalars().all()

        return {
            "email": norm,
            "resolved_lead_id": canonical,
            "canonical_identity": ident is not None,
            "lead_ids": lead_ids,
            "leads": [_lead_dict(lead) for lead in leads],
            "chat_sessions": [_session_dict(s, by_session.get(s.id, [])) for s in sessions],
            "quotes": [_quote_dict(q) for q in quotes],
            "outbox": [
                {
                    "intent_type": o.intent_type,
                    "status": o.status,
                    "retry_count": o.retry_count,
                    "request_id": o.request_id,
                    "created_at": o.created_at,
                }
                for o in outbox
            ],
            "integration_events": [
                {
                    "event_type": e.event_type,
                    "status": e.status,
                    "request": e.request,
                    "response": e.response,
                    "session_id": e.session_id,
                    "request_id": e.request_id,
                    "created_at": e.created_at,
                }
                for e in events
            ],
        }
