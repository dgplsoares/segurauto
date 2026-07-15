# Fase 3 — Enriquecimento assíncrono do lead (plano-mestre)

> Refatiada em **3a / 3b / 3c**. A Fase 3 entrega o **enriquecimento de background** do lead —
> invisível no chat: o lead é capturado (Fase 2) e, de forma assíncrona, **qualificado** e
> **sincronizado** (CRM + eventos de conversão). A espinha conversacional (chat de cotação) é Fase 4+.
>
> **Protocolo:** ao iniciar cada subfase, fazer a **reanálise pré-fase dedicada** (com o contexto
> fresco da anterior concatenado ao que a próxima exige) no `diario-de-fases.md`, antecipando gaps e
> otimizando o código. Registrar decisões em `DECISIONS.md` e descobertas no diário; atualizar a memória.

## Subfases

| Sub | Entrega | Verificação-chave |
|---|---|---|
| **3a — RAG** | `RagService` (embedding → busca → rerank → validação de suficiência → contexto), `vector_store` (pgvector + fallback keyword), `EmbeddingsPort` (stub/real), `IngestionService`, seed da base de conhecimento | ingest → retrieve (stub determinístico; real opt-in) |
| **3b — qualification_agent** | LangGraph (`rubric → retrieve → assess → combine`) + `ModelOrchestrator` + `AgentConfig` + `AiPort.qualify` real + `POST /ai/qualify` | resultado estruturado e **determinístico** com stub |
| **3c — Worker** | processo separado consumindo a outbox (`SKIP LOCKED`, backoff persistente, dead-letter); `qualify` → aplica score → **encadeia** `crm_sync`+`ads_meta`+`ads_google` idempotentes | **rodar worker 2× → efeitos 1×**; dead-letter após N |

## Decisões que fundamentam a Fase 3 (a formalizar no `DECISIONS.md`)

- **AgentConfig parametrizado** — comportamento do agente (modelo, temperatura, prompts, `k`,
  `similarity_threshold`, `use_rerank`, `ragMode`, `sufficiency_threshold`, thresholds) vem de **config**:
  V1 em env/hardcoded; V2 no painel admin (mesmo seam do corte V1/V2).
- **RAG dual-mode** — **stub**: retrieval por keyword (`ILIKE`) + rerank heurístico (determinístico, CI
  sem rede); **real**: pgvector semântico (cosine, `k`, `similarity_threshold`) + rerank. Ambos passam por
  **Context Validation** (suficiência) e respeitam o **`ragMode=rag_preferred`** (não alucina; recusa/handoff se insuficiente).
- **LangGraph com estado explícito + arestas condicionais** — grafo mínimo na V1, extensível a
  multi-turno sem retrabalho; aresta condicional garante fallback determinístico no modo stub.
- **Worker como processo separado** — isola o runtime (um LLM lento não derruba a captura);
  `SELECT ... FOR UPDATE SKIP LOCKED` para claim concorrente; **handlers idempotentes obrigatórios**
  (at-least-once). Hedge: loop callable também rodável in-process (flag, dev/testes). Detalhe em `3c-worker.md`.
- **Guardrails** — a IA trata entrada e documentos recuperados como **dados não-confiáveis**
  (scope-and-strip); PII mascarada.

## Contrato HTTP da IA (DEC-ORB-021)
`ai/api` expõe `POST /ai/qualify` (3b) e, depois, `POST /ai/support` (Fase 4) — **stateless**. O
`business` chama via `AiPort` (in-process na V1 → HTTP na V2). A IA **nunca** lê tabelas de negócio.

## Fora da Fase 3 (espinha conversacional — reescopo proposto, em revisão)
Chat multi-turn de cotação (slot-filling), cotação em chat + PDF, personalização, canais de notificação,
Click_ID e o **hardening de isolamento/auth** (ver `workspace/09` e `isolamento-leads.md`) entram nas
Fases 4-7 propostas. A Fase 3 apenas **prepara as fundações** (RAG reusável, portas CRM/Ads, worker).
