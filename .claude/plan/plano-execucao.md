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

- [x] `.claude/` completo (protocolo, DECISIONS, análise, plano, diário, arquitetura visual da LP, roadmap V2)
- [x] Árvore do monorepo (`frontend/`, `ai-service/`) + `docker-compose.yml` (postgres+pgvector, ai-service, frontend) + `.env.example`
- [x] Compose resiliente: **volume nomeado + healthcheck + `depends_on: service_healthy` + `restart: unless-stopped`**
- [x] `ai-service`: FastAPI mínimo com `/health` + `/health/ready`; `shared/config` (pydantic settings) escolhendo fake/real; esqueleto dos contextos `shared/`, `business/`, `ai/`
- [x] Observabilidade base: `configure_logging()` + middleware de `request_id` (contextvars)
- [x] Engram: decisões-semente salvas (DEC-ORB-001..021)
- **Verificado:** `docker compose up` — db `pgvector:pg16` **healthy** e `/health`→200 `{"status":"ok"}`, `/health/ready`→200 `{"db":true}`, header `X-Request-Id` presente. Local: `ruff` limpo + `pytest` 2/2. ✅

## Fase 1 — Contextos + ports/adapters + persistência + outbox  ·  ~0.8h
Meta: modelar o lead e os seams (incl. o `AiPort` entre `business` e `ai`); persistência resiliente; domínio testável sem infra.

- [x] Estrutura em contextos: `shared/`, `business/`, `ai/` (ver layout acima)
- [x] `business/domain/` puro: `Lead` (com `status`: received→qualifying→qualified→synced/failed), `QualificationResult`
- [x] Portas: `business/adapters` → `CrmPort`, `AdsPort` (fakes: `FakeCrm` com tabela de preços, `FakeMetaAds`/`FakeGoogleAds`); `ai/providers` → `LLMPort`, `RerankPort` (fakes: `StubLLM`, `HeuristicRerank`)
- [x] **`business/ai_port.py`** — `AiPort` (`qualify`, `support`); adapter **in-process** (na V1 chama `ai/`; na V2 vira HTTP client). Contrato definido já.
- [x] `LeadRepository` + `outbox` (`status` pending/done/dead, `retry_count`, **correlação `request_id`/`lead_id`**) + coluna **`idempotency_key` UNIQUE**
- [x] **alembic**: migration inicial com **schemas separados** — `business.*` para `leads`/`outbox`; `ai.*` para `documents`/`embeddings` + extensão **pgvector**. **Sem FK cruzada.**
- [x] `shared/config` (pydantic settings) liga fake/real por env
- **Verificado:** `ruff` limpo + `pytest` **20/20** (domínio, contrato dos adapters, `AiPort`, providers) SEM infra. Integração: `alembic upgrade head` criou schemas `business`/`ai` + `vector(1536)` + UNIQUE `idempotency_key`; **FK cruzada business↔ai = 0**. ✅

## Fase 2 — API de captura (fatia vertical, sem IA ainda)  ·  ~0.7h
Meta: fechar `LP → persist + outbox` de forma atômica e idempotente, antes de plugar o worker/IA.

- [x] `POST /leads`: valida (consent LGPD, e-mail) → **dedup por `Idempotency-Key`** → persiste lead + grava intent `QUALIFY` na **outbox** (mesma tx, commit no endpoint) → 201; sob corrida, `IntegrityError`→dedup
- [x] `LeadService.capture` (sem qualificação ainda; enfileira QUALIFY p/ o worker)
- [x] Eventos de ciclo de vida (`lead_received`/`lead_deduped`, PII mascarada) + métrica `leads_captured_total{result}` + `/metrics`
- [x] Auto-migrate no startup (entrypoint `alembic upgrade head`) — container self-sufficient
- **Verificado:** `ruff` + `pytest` **24/24** (unit + integração). Docker stack: entrypoint migrou, `POST` 201→**200** (mesmo id, dedup), concorrente → **1 lead**, consent 422, `/metrics` com `leads_captured_total`, outbox `qualify\|pending\|1`. ✅

## Fase 3 — Enriquecimento assíncrono (RAG + qualificação + worker)  ·  ~1.6h
**Refatiada em 3a / 3b / 3c** — plano-mestre e subfases em [`fase-3/`](fase-3/README.md). Entrega o
enriquecimento de **background** do lead (qualificar + sincronizar CRM/Ads), **invisível no chat**.

- [x] **3a — RAG** ([`fase-3/3a-rag.md`](fase-3/3a-rag.md)): `RagService` + `vector_store` (pgvector + fallback keyword) + `EmbeddingsPort` + `IngestionService` + seed. *Verificado:* `ruff` + `pytest` 30/30; seed CLI idempotente; `vector(1536)` no pgvector. ✅
- [x] **3b — qualification_agent** ([`fase-3/3b-qualification-agent.md`](fase-3/3b-qualification-agent.md)): LangGraph (`score→[cond]→assess→combine`, sem RAG) + `ModelOrchestrator` + `AgentConfig` + `AiPort.qualify` + `POST /ai/qualify`. *Verificado:* `ruff` + `pytest` 34/34; docker `/ai/qualify` (100/hot, 20/cold). ✅
- [x] **3c — Worker** ([`fase-3/3c-worker.md`](fase-3/3c-worker.md)): **processo separado**, outbox `SKIP LOCKED` + `next_attempt_at` + dead-letter; qualify → encadeia CRM/Ads idempotentes. *Verificado:* `pytest` 37/37 (worker 2×→efeitos 1×, dead-letter); **e2e Docker** — worker separado → lead `synced` (100/hot), **correlação preservada** na fronteira async. ✅ **Fatia vertical fechada.**

> **Protocolo:** reanálise pré-fase dedicada ao iniciar cada subfase (contexto fresco → antecipar gaps).

## Roadmap reescopado (aprovado)
A análise do fluxo E2E (chat-first de cotação) mostrou que o happy path é maior que o roadmap original:
- **Fase 3** (3a/3b/3c) — enriquecimento de background (RAG + qualificação + worker). *(3c inclui o
  **plumbing de Click_ID/UTM**: colunas `utm_*`/`click_id` no lead via migration aditiva + a conversão
  carregando o `click_id`.)*
- **Fase 3.5 — Hardening / Auth** (pré-requisito das Fases 4+): correção do **LEAK-1** + invariantes de
  isolamento + **primitivo de auth (token server-side → lead_id)** + **login OTP e ciclo de vida da sessão**
  (ver [`../docs/isolamento-leads.md`](../docs/isolamento-leads.md)). *Design dedicado no início desta fase.*
- **Fase 4** — suporte single-turn + LP conectada.
- **Fase 5** — conversa de cotação (prompt no hero → chat multi-turn → `quote_tool`(CRM) → PDF). *(Inclui o
  **serviço fake de UTM no frontend**: coleção de 4 campanhas fake — 2 Meta Ads + 2 Google Ads — sorteando
  uma por submissão de lead.)*
- **Fase 6** — personalização + ações (email/WhatsApp/SMS via outbox) + atribuição por Click_ID.
- **Fase 7** — CI + entrega.

Auth/conta completa (RBAC) e marketplace multi-seguradora = **V2**.

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
