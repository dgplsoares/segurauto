"""RAG sem infra: chunking, embedder stub determinístico, RagService (keyword + sufficiency)."""
from app.ai.providers.embeddings import StubEmbedder
from app.ai.rag.ingestion import chunk_text
from app.ai.rag.rag_service import RagService
from app.ai.rag.vector_store import Chunk

DOCS = [
    "Cobrimos roubo e furto do veículo pela tabela FIPE.",
    "Assistência 24h com guincho, chaveiro e socorro mecânico.",
    "Carro reserva por até 15 dias em caso de sinistro coberto.",
]


class FakeStore:
    def __init__(self, docs: list[str]) -> None:
        self._chunks = [Chunk(id=str(i), document_id="d", text=t) for i, t in enumerate(docs)]

    async def search_keyword(self, query: str, k: int) -> list[Chunk]:
        terms = [t for t in query.lower().split() if len(t) > 2]
        hits = [c for c in self._chunks if any(t in c.text.lower() for t in terms)]
        return hits[:k]

    async def search_semantic(self, embedding, k: int, threshold: float = 0.0) -> list[Chunk]:
        return self._chunks[:k]


async def test_stub_embedder_deterministic_and_normalized():
    e = StubEmbedder()
    a, b = await e.embed("seguro auto"), await e.embed("seguro auto")
    assert a == b
    assert len(a) == 1536
    assert abs(sum(x * x for x in a) - 1.0) < 1e-6  # unitário


def test_chunk_text_respects_max_and_keeps_small_whole():
    big = "\n\n".join(["p" * 300 for _ in range(4)])
    chunks = chunk_text(big, max_chars=600)
    assert all(len(c) <= 602 for c in chunks)
    assert chunk_text("um parágrafo curto") == ["um parágrafo curto"]


async def test_rag_sufficient_in_domain():
    rag = RagService(FakeStore(DOCS), StubEmbedder(), min_score=0.05)
    res = await rag.retrieve("cobre roubo")
    assert res.sufficient is True
    assert "roubo" in res.context.lower()


async def test_rag_insufficient_off_domain():
    rag = RagService(FakeStore(DOCS), StubEmbedder())
    res = await rag.retrieve("qual a capital da frança")
    assert res.sufficient is False
    assert res.chunks == []
