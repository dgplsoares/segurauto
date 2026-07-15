"""Seed do RAG (V1: escrita direta no banco). Idempotente: não re-ingere se já houver chunks.

Uso: `python -m app.ai.rag.seed`
"""
import asyncio
from pathlib import Path

from app.ai.providers.embeddings import get_embedder
from app.ai.rag.ingestion import IngestionService
from app.ai.rag.vector_store import VectorStore
from app.shared.database import get_sessionmaker

KB_PATH = Path(__file__).parent / "knowledge_base.md"


async def seed() -> None:
    async with get_sessionmaker()() as session:
        existing = await VectorStore(session).count_chunks()
        if existing > 0:
            print(f"seed skip: {existing} chunks já existem")
            return
        content = KB_PATH.read_text(encoding="utf-8")
        doc_id = await IngestionService(VectorStore(session), get_embedder()).ingest(
            title="SegurAuto — base de conhecimento", content=content
        )
        await session.commit()
        count = await VectorStore(session).count_chunks()
    print(f"seed ok: doc={doc_id} chunks={count}")


if __name__ == "__main__":
    asyncio.run(seed())
