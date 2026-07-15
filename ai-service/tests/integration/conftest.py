"""Fixtures de integração. Precisam de um Postgres migrado (DATABASE_URL). Se indisponível, os
testes são **pulados** (o gate de CI sem infra continua verde — DEC-ORB-006).

O app é dirigido via `dependency_overrides[get_session]` usando o engine do teste (ligado ao event
loop corrente), evitando o engine global preso a um loop já fechado.
"""
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import app
from app.shared.database import get_chat_session, get_session

DB_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://segurauto:segurauto@localhost:5432/segurauto")


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(DB_URL)
    try:
        async with engine.begin() as conn:
            await conn.execute(text(
                "TRUNCATE business.leads, business.outbox, business.chat_messages, business.chat_sessions, "
                "business.identities, business.auth_sessions, business.otp_codes"
            ))
    except Exception as exc:  # banco indisponível / não migrado
        await engine.dispose()
        pytest.skip(f"DB de integração indisponível: {exc}")
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_engine):
    sessionmaker = async_sessionmaker(db_engine, expire_on_commit=False)

    async def _override_get_session():
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session
    # Chat usa um pool isolado (DEC-ORB-040); nos testes, o mesmo engine do teste.
    app.dependency_overrides[get_chat_session] = _override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
