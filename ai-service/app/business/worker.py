"""Worker (DEC-ORB-025): processo SEPARADO consumindo a outbox at-least-once.

Executar como serviço: `python -m app.business.worker`. O loop é uma função callable, também rodável
in-process (dev/testes). Claim por `FOR UPDATE SKIP LOCKED` (não é exactly-once → handlers idempotentes);
retry/backoff persistente (`next_attempt_at`) + dead-letter.
"""
import asyncio
import logging
import random
import signal
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from sqlalchemy import func, or_, select

from app.business.adapters.ads import FakeGoogleAds, FakeMetaAds
from app.business.adapters.crm import FakeCrm
from app.business.ai_port import InProcessAiAdapter
from app.business.domain.events import IntentType, conversion_event_id
from app.business.repository.lead_repository import LeadRepository
from app.business.repository.models import LeadRow, OutboxRow
from app.shared.config import get_settings
from app.shared.database import get_sessionmaker
from app.shared.observability import configure_logging, request_id_ctx

logger = logging.getLogger("segurauto.worker")

MAX_RETRIES = 3
BACKOFF_BASE_S = 2.0

_ai = InProcessAiAdapter()


@lru_cache
def _crm() -> FakeCrm:
    return FakeCrm()  # V1: fake sempre (real opt-in pós-V1)


@lru_cache
def _ads_meta() -> FakeMetaAds:
    return FakeMetaAds()


@lru_cache
def _ads_google() -> FakeGoogleAds:
    return FakeGoogleAds()


def reset_adapters() -> None:
    """Zera os singletons fake (usado nos testes de integração)."""
    _crm.cache_clear()
    _ads_meta.cache_clear()
    _ads_google.cache_clear()


async def _claim_one(session) -> OutboxRow | None:
    stmt = (
        select(OutboxRow)
        .where(
            OutboxRow.status == "pending",
            or_(OutboxRow.next_attempt_at.is_(None), OutboxRow.next_attempt_at <= func.now()),
        )
        .order_by(OutboxRow.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def _get_lead(session, lead_id: str) -> LeadRow | None:
    return (await session.execute(select(LeadRow).where(LeadRow.id == lead_id))).scalar_one_or_none()


async def _handle(session, row: OutboxRow) -> None:
    lead = await _get_lead(session, row.lead_id)
    if lead is None:
        raise RuntimeError(f"lead {row.lead_id} inexistente")
    repo = LeadRepository(session)
    intent = row.intent_type

    if intent == IntentType.QUALIFY.value:
        result = await _ai.qualify(
            has_vehicle=bool(lead.vehicle), has_phone=bool(lead.phone),
            has_zipcode=bool(lead.zipcode), consent=lead.consent, source=lead.source,
        )
        lead.score = result.score
        lead.band = result.band.value
        lead.reason = result.reason
        lead.status = "qualified"
        for downstream in (IntentType.CRM_SYNC, IntentType.ADS_META, IntentType.ADS_GOOGLE):
            await repo.enqueue(lead_id=lead.id, intent_type=downstream, request_id=row.request_id)
        logger.info("lead_qualified lead_id=%s score=%s band=%s", lead.id, lead.score, lead.band)

    elif intent == IntentType.CRM_SYNC.value:
        # Contrato do CRM: source=landing_page, status=qualified (o funil é do CRM). O fake registra o lead.
        res = await _crm().upsert_lead(
            lead_id=lead.id, name=lead.name, email=lead.email, phone=lead.phone,
            vehicle=lead.vehicle, zipcode=lead.zipcode, score=lead.score, band=lead.band,
        )
        lead.status = "synced"
        logger.info("crm_synced lead_id=%s external_id=%s created=%s", lead.id, res.external_id, res.created)

    elif intent == IntentType.ADS_META.value:
        res = await _ads_meta().send_conversion(event_id=conversion_event_id(lead.id, "meta"), lead_id=lead.id)
        logger.info("ads_sent platform=meta lead_id=%s deduped=%s", lead.id, res.deduped)

    elif intent == IntentType.ADS_GOOGLE.value:
        res = await _ads_google().send_conversion(event_id=conversion_event_id(lead.id, "google"), lead_id=lead.id)
        logger.info("ads_sent platform=google lead_id=%s deduped=%s", lead.id, res.deduped)

    else:
        raise RuntimeError(f"intent desconhecido: {intent}")


async def process_one(session) -> bool:
    """Processa 1 intent (claim → handle → done) numa transação. False se não há pendências."""
    row = await _claim_one(session)
    if row is None:
        return False
    row_id, request_id = row.id, row.request_id
    token = request_id_ctx.set(request_id or "-")  # re-hidrata a correlação (DEC-ORB-019)
    try:
        await _handle(session, row)
        row.status = "done"
        await session.commit()
    except Exception:
        await session.rollback()  # descarta escrita parcial + libera o lock
        pending = await session.get(OutboxRow, row_id)
        if pending is not None and pending.status == "pending":
            pending.retry_count += 1
            if pending.retry_count >= MAX_RETRIES:
                pending.status = "dead"
                logger.warning("outbox_deadletter id=%s type=%s", row_id, pending.intent_type)
            else:
                delay = BACKOFF_BASE_S * (2**pending.retry_count)
                pending.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
                logger.warning("outbox_retry id=%s attempt=%s", row_id, pending.retry_count)
        await session.commit()
    finally:
        request_id_ctx.reset(token)
    return True


async def drain_once(sessionmaker) -> int:
    """Processa todas as intents disponíveis agora. Retorna quantas processou."""
    processed = 0
    while True:
        async with sessionmaker() as session:
            did = await process_one(session)
        if not did:
            break
        processed += 1
    return processed


async def run_worker_loop(sessionmaker, *, stop_event: asyncio.Event, poll_interval: float = 1.5) -> None:
    logger.info("worker iniciado")
    while not stop_event.is_set():
        n = await drain_once(sessionmaker)
        if n == 0:
            await asyncio.sleep(poll_interval + random.uniform(0.0, 0.5))  # jitter
    logger.info("worker encerrando")


async def _amain() -> None:
    configure_logging(get_settings().log_level)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    await run_worker_loop(get_sessionmaker(), stop_event=stop)


if __name__ == "__main__":
    asyncio.run(_amain())
