# Plano de Execução — SegurAuto

> Fases com checklist. Marcar `[x]` ao concluir. Reanálise pré-fase e descobertas em
> `diario-de-fases.md`. Decisões em `DECISIONS.md` (DEC-ORB-*).

**Fatia vertical primeiro:** LP → captura → persist+outbox → worker (qualifica/CRM/Ads). Suporte e
polish depois. Time-box total ~4,5–5h.

**Layout extraível (DEC-ORB-021):** o `ai-service/app/` é dividido em dois bounded contexts —
`business/` (leads, outbox, adapters CRM/Ads, lifecycle) e `ai/` (agentes, RAG, orquestrador,
embeddings) — mais `shared/` (config, database, observabilidade). O `business` chama o `ai` **só via
`AiPort`** (in-process agora; HTTP na V2). Schemas de banco separados: `business.*` e `ai.*`, sem FK cruzada.

```
ai-service/app/
├── shared/     config · database · observability (correlação, auth-seam)
├── business/   domain · api (/leads) · service · repository (+ outbox, schema business.*) · worker · adapters (crm/ads) · ai_port.py
└── ai/         api (/ai/qualify, /ai/support) · agents (LangGraph) · rag (embeddings/rerank/vector_store, schema ai.*) · providers (orchestrator/llm)
```

---

## Fase 0 — Scaffold + protocolo + infra base  ·  ~0.6h
Meta: repo navegável, processo versionado, infra de pé e observabilidade base.

- [ ] `.claude/` completo (protocolo, DECISIONS, análise, plano, diário, arquitetura visual da LP, roadmap V2)
- [ ] Árvore do monorepo (`frontend/`, `ai-service/`) + `docker-compose.yml` (postgres+pgvector, ai-service, frontend) + `.env.example`
- [ ] Compose resiliente: **volume nomeado + healthcheck + `depends_on: service_healthy` + `restart: unless-stopped`**
- [ ] `ai-service`: FastAPI mínimo com `/health` + `/health/ready`; `shared/config` (pydantic settings) escolhendo fake/real; esqueleto dos contextos `shared/`, `business/`, `ai/`
- [ ] Observabilidade base: `configure_logging()` + middleware de `request_id` (contextvars)
- [ ] Engram: `mem_session_start` + save das decisões-semente
- **Verificar:** `docker compose up` sobe Postgres+pgvector e `/health` responde 200. Sem lógica ainda.

## Fase 1 — Contextos + ports/adapters + persistência + outbox  ·  ~0.8h
Meta: modelar o lead e os seams (incl. o `AiPort` entre `business` e `ai`); persistência resiliente; domínio testável sem infra.

- [ ] Estrutura em contextos: `shared/`, `business/`, `ai/` (ver layout acima)
- [ ] `business/domain/` puro: `Lead` (com `status`: received→qualifying→qualified→synced/failed), `QualificationResult`
- [ ] Portas: `business/adapters` → `CrmPort`, `AdsPort` (fakes: `FakeCrm` com tabela de preços, `FakeMetaAds`/`FakeGoogleAds`); `ai/providers` → `LLMPort`, `RerankPort` (fakes: `StubLLM`, `HeuristicRerank`)
- [ ] **`business/ai_port.py`** — `AiPort` (`qualify`, `support`); adapter **in-process** (na V1 chama `ai/`; na V2 vira HTTP client). Contrato definido já.
- [ ] `LeadRepository` + `outbox` (`status` pending/done/dead, `retry_count`, **correlação `request_id`/`lead_id`**) + coluna **`idempotency_key` UNIQUE**
- [ ] **alembic**: migration inicial com **schemas separados** — `business.*` (extensão n/a) para `leads`/`outbox`; `ai.*` para `embeddings`/`documents` + extensão **pgvector**. **Sem FK cruzada.**
- [ ] `shared/config` (pydantic settings) liga fake/real por env
- **Verificar:** unit do domínio SEM infra (regras de Lead/score) + teste de contrato dos adapters fake + `AiPort` mockável. Verde em CI sem rede.

## Fase 2 — API de captura (fatia vertical, sem IA ainda)  ·  ~0.7h
Meta: fechar `LP → persist + outbox` de forma atômica e idempotente, antes de plugar o worker/IA.

- [ ] `POST /leads`: valida → **dedup por `Idempotency-Key`** → persiste lead + grava intents na **outbox** (mesma tx, commit no endpoint) → responde 201
- [ ] `LeadService.capture` (sem qualificação ainda; score placeholder)
- [ ] Eventos de ciclo de vida (`lead_received`, `lead_deduped`) + métrica `leads_captured_total`
- **Verificar:** integração com fakes — **duplo POST com a mesma chave → 1 lead**; outbox com N intents; resposta tipada.

## Fase 3 — Worker + agente de qualificação + RAG  ·  ~0.9h
Meta: worker consome a outbox e substitui o placeholder por qualificação real (RAG + LangGraph); efeitos idempotentes.

- [ ] `ai/api`: **contrato HTTP público** `POST /ai/qualify` e `POST /ai/support` (stateless); o `AiPort` in-process chama esses handlers (na V2, o mesmo contrato vira chamada HTTP)
- [ ] **Worker** (em `business/`, loop async) consome a outbox at-least-once, com **retry/backoff** e **dead-letter**; re-hidrata `request_id`/`lead_id`; chama a IA **via `AiPort`**
- [ ] `ai/rag` `RagService` (embedding → pgvector search → `RerankPort` → context → generate) + **seed** da knowledge_base
- [ ] `ai/agents` `qualification_agent` (LangGraph) → `QualificationResult` estruturado (score + faixa + motivo)
- [ ] `ai/providers` `ModelOrchestrator` + `LLMPort` (StubLLM determinístico p/ teste; OpenAI opt-in)
- [ ] Handlers idempotentes (no `business`): `CrmPort.upsert` + `AdsPort.send_conversion` (event_id estável) + re-check terminal
- [ ] Observabilidade IA: `log_agent_turn` (tokens) + eventos `rag_*` + métricas de LLM/outbox
- **Verificar:** integração com LLM stub — qualificação determinística e estruturada; RAG recupera do seed; **rodar o worker 2x → efeitos 1x**; teste de concorrência (`asyncio.gather` de POSTs com a mesma chave → 1 lead). `real/` opt-in valida OpenAI.

## Fase 4 — Agente de suporte + LP conectada  ·  ~0.7h
Meta: suporte via RAG e a Landing Page real consumindo a API pelo BFF.

- [ ] `POST /support/chat` → `support_agent` (LangGraph, RAG single-turn) reusando `RagService`/orchestrator
- [ ] Frontend Next.js: `LeadForm` → `/api/lead` (BFF) → `/leads`; `SupportChat` → `/api/support`
- [ ] Validação client + server; `Idempotency-Key` gerada no client
- **Verificar:** teste do BFF/form (mock do ai-service) + smoke E2E: enviar lead pela LP persiste e (via worker) sincroniza; chat responde do RAG.

## Fase 5 — CI + verificação Docker + entrega  ·  ~0.6h
Meta: gate automatizado e stack reprodutível do zero.

- [ ] `.github/workflows/ci.yml`: job **ai-service** (pytest mock + ruff), job **frontend** (build + test), job **docker build**
- [ ] `/metrics` completo + README de entrega (stack, fake vs real, decisões, observabilidade, próximos passos)
- [ ] Reconciliar `diario-de-fases.md` + `mem_session_summary`
- **Verificar:** CI verde no push (só mock, sem segredos); `docker compose up --build` do zero: LP sobe, POST de lead persiste + (worker) sincroniza fakes, `/health` OK.
