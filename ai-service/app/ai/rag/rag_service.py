"""`RagService` (DEC-ORB-023): `Embed → Search → Rerank → Context Validation`.

Modo escolhido pelo embedder (`is_semantic`): keyword (stub) vs pgvector (real). Sempre reordena por
`RerankPort` para um score uniforme. `sufficient=False` → o agente aplica `rag_mode=rag_preferred`
(recusa/handoff em vez de alucinar).
"""
from dataclasses import dataclass, replace

from app.ai.providers.embeddings import EmbeddingsPort
from app.ai.providers.rerank import HeuristicRerank
from app.ai.rag.vector_store import Chunk


@dataclass
class RagResult:
    chunks: list[Chunk]
    context: str
    sufficient: bool


class RagService:
    def __init__(
        self,
        store,
        embedder: EmbeddingsPort,
        reranker=None,
        *,
        k: int = 5,
        similarity_threshold: float = 0.0,
        min_score: float = 0.05,
        min_chunks: int = 1,
    ) -> None:
        self.store = store
        self.embedder = embedder
        self.reranker = reranker or HeuristicRerank()
        self.k = k
        self.similarity_threshold = similarity_threshold
        self.min_score = min_score
        self.min_chunks = min_chunks

    async def retrieve(self, query: str) -> RagResult:
        if self.embedder.is_semantic:
            embedding = await self.embedder.embed(query)
            candidates = await self.store.search_semantic(embedding, self.k, self.similarity_threshold)
        else:
            candidates = await self.store.search_keyword(query, self.k)

        if not candidates:
            return RagResult(chunks=[], context="", sufficient=False)

        ranked = self.reranker.rerank(query, [c.text for c in candidates], top_k=self.k)
        reordered = [replace(candidates[i], score=score) for i, score in ranked]
        context = "\n\n".join(c.text for c in reordered)
        top_score = reordered[0].score or 0.0
        sufficient = len(reordered) >= self.min_chunks and top_score >= self.min_score
        return RagResult(chunks=reordered, context=context, sufficient=sufficient)
