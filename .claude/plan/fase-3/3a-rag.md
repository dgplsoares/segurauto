# Fase 3a — RAG (fundação)

Meta: pipeline de recuperação reusável pelos agentes, **dual-mode** (determinístico no CI, semântico no real).

## Entregáveis
- `ai/providers/embeddings.py` — `EmbeddingsPort`: `StubEmbedder` (default, determinístico) | `OpenAIEmbedder` (opt-in).
- `ai/rag/vector_store.py` — acesso a `ai.documents`/`ai.embeddings`:
  - **modo real:** busca semântica pgvector (cosine, `k`, `similarity_threshold`).
  - **modo stub:** fallback por **keyword** (`ILIKE` sobre `ai.documents`) — sem rede, determinístico.
- `ai/rag/rag_service.py` — `Embed → Search → Rerank(RerankPort) → Context Validation(sufficiency) → contexto`.
  Respeita `AgentConfig.rag_mode=rag_preferred` (se insuficiente → sinaliza recusa/handoff, não inventa).
- `ai/rag/ingestion.py` — `IngestionService.ingest(doc)`: chunk → embed → grava (`documents`+`embeddings`).
  **Mesma função** que o upload do painel admin chamará na V2 (seam DEC-ORB-020).
- `ai/rag/knowledge_base.md` (seed) — conteúdo SegurAuto (coberturas, FAQ, políticas) para o RAG.
- Script/CLI de seed que roda o `IngestionService` (V1: escrita direta no banco).

## Testes
- **unit:** chunking, montagem de contexto, sufficiency, `StubEmbedder` determinístico, keyword-retrieval.
- **integração (pgvector real):** ingest do seed → retrieve retorna trechos relevantes; `real/` opt-in valida embedder real.

## Reanálise pré-fase (a fazer ao iniciar)
Reler o seed e o contrato de `RerankPort`/`EmbeddingsPort`; decidir formato de chunk e a estratégia exata
do fallback keyword; confirmar que o modo stub não depende de rede. Registrar no diário.

## Gaps já antecipados
- Embeddings fake não dão similaridade semântica → o **modo stub usa keyword + rerank heurístico** (o
  rerank é exercitado de verdade); pgvector só no modo real.
- Não embutir artefato específico do lead (cotação/PDF) no vector store (isolamento — ver `isolamento-leads.md`).
