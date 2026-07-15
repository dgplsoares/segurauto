"""Acesso ao Postgres (async). Engine preguiçoso para não acoplar o boot da app ao banco
(o `/health` de liveness responde mesmo com o banco fora — DEC-ORB-016).
"""
from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.shared.config import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        # echo=False não loga SQL; hide_parameters=True impede que os parâmetros (PII) apareçam em
        # mensagens de exceção/repr (ex.: IntegrityError) — DEC-ORB-036.
        _engine = create_async_engine(
            get_settings().database_url, pool_pre_ping=True, future=True, echo=False, hide_parameters=True
        )
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(get_engine(), expire_on_commit=False, class_=AsyncSession)
    return _sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        yield session


# Pool ISOLADO do chat (DEC-ORB-040): o turno de chat pode segurar a conexão durante o LLM; num pool
# próprio, isso nunca esgota o pool principal (captura/auth). `lock_timeout`/`statement_timeout` fazem
# um turno concorrente na mesma sessão falhar rápido (→ 409) em vez de prender a conexão.
_chat_engine: AsyncEngine | None = None
_chat_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_chat_engine() -> AsyncEngine:
    global _chat_engine
    if _chat_engine is None:
        s = get_settings()
        _chat_engine = create_async_engine(
            s.database_url,
            echo=False,
            hide_parameters=True,  # parâmetros (PII) fora das mensagens de exceção — DEC-ORB-036
            future=True,
            pool_pre_ping=True,
            pool_size=s.chat_pool_size,
            max_overflow=s.chat_pool_max_overflow,
            connect_args={
                "server_settings": {
                    "lock_timeout": str(s.chat_lock_timeout_ms),
                    "statement_timeout": str(s.chat_statement_timeout_ms),
                }
            },
        )
    return _chat_engine


def get_chat_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _chat_sessionmaker
    if _chat_sessionmaker is None:
        _chat_sessionmaker = async_sessionmaker(get_chat_engine(), expire_on_commit=False, class_=AsyncSession)
    return _chat_sessionmaker


async def get_chat_session() -> AsyncIterator[AsyncSession]:
    async with get_chat_sessionmaker()() as session:
        yield session


async def ping() -> bool:
    """Readiness: o banco responde? (SELECT 1)."""
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
