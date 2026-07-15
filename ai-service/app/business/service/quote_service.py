"""Cotação (DEC-ORB-043): `quote_tool` orquestrado pelo **business**. O prêmio vem do CRM (fake
determinístico), NUNCA do LLM; `broker_code` é autorizado server-side no CRM (E6). Não commita (boundary no
endpoint). Idempotente: uma cotação por sessão (re-cota = F6)."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.business.adapters.crm import get_crm
from app.business.repository.integration_events import record_integration_event
from app.business.repository.models import QuoteRow
from app.shared.observability import request_id_ctx

_COVERAGES = ["roubo_furto", "colisao", "danos_a_terceiros", "assistencia_24h", "carro_reserva"]


def quote_public(row: QuoteRow) -> dict:
    """Projeção pública da cotação (card do turno / GET /quote)."""
    return {
        "quote_id": row.id,
        "premium_cents": row.premium_cents,
        "currency": row.currency,
        "coverages": list(row.coverages),
        "broker_applied": row.broker_applied,
        "pdf_ref": row.pdf_ref,
    }


class QuoteService:
    def __init__(self, session: AsyncSession, crm=None) -> None:
        self.session = session
        self.crm = crm or get_crm()

    async def for_session(self, session_id: str) -> QuoteRow | None:
        result = await self.session.execute(select(QuoteRow).where(QuoteRow.session_id == session_id))
        return result.scalar_one_or_none()

    async def create_for_session(self, *, session_id: str, lead_id: str, slots: dict) -> tuple[QuoteRow, dict]:
        """Cria a cotação a partir dos slots VALIDADOS. Devolve (row, resultado do CRM) — o resultado
        alimenta o `integration_event` (F5b.2). Idempotente: se já há cotação p/ a sessão, devolve-a."""
        existing = await self.for_session(session_id)
        if existing is not None:
            return existing, {}
        result = await self.crm.price_quote(
            vehicle=slots.get("vehicle", ""), zipcode=slots.get("zipcode", ""),
            broker_code=slots.get("broker_code"),
        )
        qid = str(uuid.uuid4())
        row = QuoteRow(
            id=qid, session_id=session_id, lead_id=lead_id,
            premium_cents=round(result["annual_premium"] * 100), currency=result["currency"],
            slots=dict(slots), coverages=_COVERAGES, broker_applied=result["broker_applied"],
            pdf_ref=f"cotacao-{qid[:8]}.pdf",
        )
        self.session.add(row)
        await self.session.flush()
        await record_integration_event(
            self.session, event_type="crm_price_quote", lead_id=lead_id, session_id=session_id,
            request={"vehicle": slots.get("vehicle"), "zipcode": slots.get("zipcode"),
                     "broker_code": slots.get("broker_code")},
            response=result, request_id=request_id_ctx.get(),
        )
        return row, result
