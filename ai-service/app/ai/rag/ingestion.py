"""Ingestão do RAG: `chunk → embed → grava`. **Mesma função** que o upload do painel admin chamará
na V2 (seam DEC-ORB-020); na V1 é acionada pelo seed."""
import uuid

from app.ai.providers.embeddings import EmbeddingsPort
from app.ai.rag.vector_store import VectorStore


def chunk_text(content: str, *, max_chars: int = 600) -> list[str]:
    """Agrupa parágrafos (`\\n\\n`) até ~max_chars."""
    paras = [p.strip() for p in content.split("\n\n") if p.strip()]
    chunks: list[str] = []
    buf = ""
    for para in paras:
        if buf and len(buf) + len(para) + 2 > max_chars:
            chunks.append(buf)
            buf = para
        else:
            buf = f"{buf}\n\n{para}" if buf else para
    if buf:
        chunks.append(buf)
    return chunks


class IngestionService:
    def __init__(self, store: VectorStore, embedder: EmbeddingsPort) -> None:
        self.store = store
        self.embedder = embedder

    async def ingest(self, *, title: str, content: str) -> str:
        doc_id = str(uuid.uuid4())
        await self.store.add_document(doc_id=doc_id, title=title, content=content)
        for piece in chunk_text(content):
            embedding = await self.embedder.embed(piece)
            await self.store.add_chunk(
                chunk_id=str(uuid.uuid4()), document_id=doc_id, chunk=piece, embedding=embedding
            )
        return doc_id
