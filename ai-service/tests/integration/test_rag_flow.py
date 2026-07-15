"""Fase 3a — ingest → retrieve contra pgvector real (DEC-ORB-023)."""
import os

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.ai.providers.embeddings import StubEmbedder
from app.ai.rag.ingestion import IngestionService
from app.ai.rag.rag_service import RagService
from app.ai.rag.vector_store import VectorStore

DB_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://segurauto:segurauto@localhost:5432/segurauto")
KB = (
    "## Coberturas\n\nCobrimos roubo e furto do veículo pela tabela FIPE.\n\n"
    "## Assistência\n\nAssistência 24h com guincho e chaveiro.\n\n"
    "## Carro reserva\n\nCarro reserva por até 15 dias em caso de sinistro."
)


class SemanticStub(StubEmbedder):
    is_semantic = True


@pytest_asyncio.fixture
async def sm():
    engine = create_async_engine(DB_URL)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("TRUNCATE ai.embeddings, ai.documents CASCADE"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"DB de integração indisponível: {exc}")
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def test_ingest_then_keyword_retrieve(sm):
    async with sm() as session:
        await IngestionService(VectorStore(session), StubEmbedder()).ingest(title="KB", content=KB)
        await session.commit()
    async with sm() as session:
        res = await RagService(VectorStore(session), StubEmbedder()).retrieve("cobre roubo furto")
    assert res.sufficient is True
    assert "roubo" in res.context.lower()


async def test_semantic_search_plumbing(sm):
    # StubEmbedder não é semântico; SemanticStub força o caminho pgvector (<=>) — prova o plumbing.
    async with sm() as session:
        await IngestionService(VectorStore(session), StubEmbedder()).ingest(title="KB", content=KB)
        await session.commit()
    async with sm() as session:
        emb = await SemanticStub().embed("roubo")
        chunks = await VectorStore(session).search_semantic(emb, k=3, threshold=-1.0)
    assert len(chunks) >= 1  # a query vetorial pgvector executa e retorna
