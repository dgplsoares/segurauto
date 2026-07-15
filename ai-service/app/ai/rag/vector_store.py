"""Acesso ao schema `ai` (documents/embeddings). Busca **semântica** (pgvector `<=>` cosine) e
**keyword** (`LIKE`) — o `RagService` escolhe conforme o embedder (DEC-ORB-023)."""
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class Chunk:
    id: str
    document_id: str
    text: str
    score: float | None = None


def _vector_literal(embedding: list[float]) -> str:
    return "[" + ",".join(f"{x:.7f}" for x in embedding) + "]"


def _tokens(query: str) -> list[str]:
    return [t for t in query.lower().split() if len(t) > 2]


class VectorStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_document(self, *, doc_id: str, title: str, content: str) -> None:
        await self.session.execute(
            text("INSERT INTO ai.documents (id, title, content) VALUES (:id, :t, :c)"),
            {"id": doc_id, "t": title, "c": content},
        )

    async def add_chunk(self, *, chunk_id: str, document_id: str, chunk: str, embedding: list[float]) -> None:
        await self.session.execute(
            text(
                "INSERT INTO ai.embeddings (id, document_id, chunk, embedding) "
                "VALUES (:id, :d, :c, CAST(:e AS vector))"
            ),
            {"id": chunk_id, "d": document_id, "c": chunk, "e": _vector_literal(embedding)},
        )

    async def count_chunks(self) -> int:
        result = await self.session.execute(text("SELECT count(*) FROM ai.embeddings"))
        return int(result.scalar_one())

    async def search_semantic(self, embedding: list[float], k: int, threshold: float = 0.0) -> list[Chunk]:
        result = await self.session.execute(
            text(
                "SELECT id, document_id, chunk, (embedding <=> CAST(:e AS vector)) AS distance "
                "FROM ai.embeddings WHERE embedding IS NOT NULL "
                "ORDER BY embedding <=> CAST(:e AS vector) LIMIT :k"
            ),
            {"e": _vector_literal(embedding), "k": k},
        )
        out: list[Chunk] = []
        for row in result:
            similarity = 1.0 - float(row.distance)
            if similarity >= threshold:
                out.append(Chunk(id=row.id, document_id=row.document_id, text=row.chunk, score=similarity))
        return out

    async def search_keyword(self, query: str, k: int) -> list[Chunk]:
        terms = _tokens(query)
        if not terms:
            return []
        conds = " OR ".join(f"lower(chunk) LIKE :p{i}" for i in range(len(terms)))
        params: dict = {f"p{i}": f"%{t}%" for i, t in enumerate(terms)}
        params["k"] = k
        result = await self.session.execute(
            text(f"SELECT id, document_id, chunk FROM ai.embeddings WHERE {conds} LIMIT :k"), params
        )
        return [Chunk(id=row.id, document_id=row.document_id, text=row.chunk) for row in result]
