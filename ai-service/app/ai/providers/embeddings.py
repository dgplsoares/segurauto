"""`EmbeddingsPort` + implementações (DEC-ORB-023).

`StubEmbedder` (default) é determinístico e **não-semântico** → o RAG usa retrieval por keyword no
modo stub. `OpenAIEmbedder` (opt-in) é semântico → retrieval por pgvector. Import de `openai` é lazy.
"""
import hashlib
import random
from typing import Protocol, runtime_checkable

from app.shared.config import get_settings

EMBED_DIM = 1536


@runtime_checkable
class EmbeddingsPort(Protocol):
    is_semantic: bool
    dim: int

    async def embed(self, text: str) -> list[float]: ...


class StubEmbedder:
    """Pseudo-embedding determinístico (semeado por hash). CI sem rede."""

    is_semantic = False
    dim = EMBED_DIM

    async def embed(self, text: str) -> list[float]:
        seed = int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "big")
        rng = random.Random(seed)
        vec = [rng.uniform(-1.0, 1.0) for _ in range(self.dim)]
        norm = sum(x * x for x in vec) ** 0.5 or 1.0
        return [x / norm for x in vec]


class OpenAIEmbedder:
    """Embedder real (opt-in). Import de `openai` só quando efetivamente usado."""

    is_semantic = True
    dim = EMBED_DIM

    def __init__(self, model: str = "text-embedding-3-small") -> None:
        self.model = model

    async def embed(self, text: str) -> list[float]:
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("OpenAIEmbedder requer o pacote `openai` (opt-in).") from exc
        client = AsyncOpenAI(api_key=get_settings().openai_api_key)
        resp = await client.embeddings.create(model=self.model, input=text)
        return list(resp.data[0].embedding)


def get_embedder() -> EmbeddingsPort:
    if get_settings().embeddings_provider.lower() == "openai":
        return OpenAIEmbedder()
    return StubEmbedder()
