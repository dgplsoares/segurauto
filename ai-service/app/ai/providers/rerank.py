"""Rerank heurístico local (DEC-ORB): overlap de tokens query↔doc. Cumpre "rank & re-rank" de
forma visível e testável, sem custo/latência de API. O reranker real (cross-encoder) é opt-in.
"""


class HeuristicRerank:
    """Implementa `RerankPort`. Score = fração de tokens da query presentes no doc."""

    def rerank(self, query: str, docs: list[str], top_k: int = 3) -> list[tuple[int, float]]:
        q = {t for t in query.lower().split() if t}
        scored: list[tuple[int, float]] = []
        for i, doc in enumerate(docs):
            dt = {t for t in doc.lower().split() if t}
            overlap = len(q & dt) / (len(q) or 1)
            scored.append((i, overlap))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:top_k]
