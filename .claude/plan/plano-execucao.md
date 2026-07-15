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

> Reescopo do roadmap (E2E chat-first) aprovado — DEC-ORB-033. **V1 = F0→F4** (núcleo + 1º contato com a
> IA autenticado); **V1.5 = F5/F6** (cotação conversacional + ações); **F7 = CI/entrega**. RBAC/painel
> admin/marketplace multi-seguradora = **V2**.

## Fase 3.5 — Hardening (LEAK-1 + observabilidade)  ·  concluída
Meta: fechar os bugs reais da auditoria adversarial antes do chat.

- [x] **LEAK-1** (DEC-ORB-035): `LeadResponse` sem `score`/`band`; dedup compara e-mail (dono→200 mínimo, colisão de key→**409 neutro**); log de conflito só com `key_sha`. Sem `UNIQUE(email)` (DEC-ORB-037).
- [x] **Observabilidade** (DEC-ORB-036): `RequestIdMiddleware` **pure-ASGI**; `X-Request-Id` só de origem confiável e **nunca ecoado**; **masking central de PII** seguro (sem corromper UUID); `echo=off`.
- [x] Auth/OTP **desenhado e aprovado** via pentest adversarial (DEC-ORB-037) → implementa na F4.
- **Verificado:** `ruff` + `pytest` **42/42**; docker (409 no LEAK-1, X-Request-Id não-ecoado, PII mascarada). ✅

## Fase 4 — Auth + Suporte + LP  (refatiada em 4a/4b/4c)
**Plano-mestre e subfases em [`fase-4/`](fase-4/README.md).** Primeiro contato do lead com a IA — autenticado e isolado.

- [x] **4a — Auth/OTP** ([`fase-4/4a-auth-otp.md`](fase-4/4a-auth-otp.md)) (DEC-ORB-037): tabelas `auth_sessions`/`otp_codes` (migration 0003), `AuthService`, `NotificationPort` fake, `/auth/request-otp` + `/auth/verify-otp` + `/auth/logout`, **`require_session`** (token→lead_id); sessão **só pós-OTP**, e-mail=identidade sem UNIQUE, OTP **cooldown-não-burn** + rate-limit, sliding+absoluto. *Verificado:* `ruff` + `pytest` 52/52 (anti-lockout, expiração, reuso); docker (auto-migrate 0003, 202/401, OTP nunca logado). ✅
- [x] **4b — support_agent single-turn** ([`fase-4/4b-support-agent.md`](fase-4/4b-support-agent.md)): grafo LangGraph `guard_in→retrieve→[cond]→generate|refuse`; `AiPort.support(query,session)` + `POST /ai/support` + `POST /support/chat` **autenticado** (`require_session`); `rag_mode=rag_preferred`. *Verificado:* `ruff` + `pytest` 58/58; docker — `/support/chat` **401 sem token**, `/ai/support` in-domain sufficient / out-domain recusa+handoff. ✅
- [x] **4c — LP conectada** ([`fase-4/4c-lp-conectada.md`](fase-4/4c-lp-conectada.md)): Next.js (Figma Make) — `LeadForm`→`/api/lead` (BFF)→`/leads`; **modal de OTP** (botão "Já tem cadastro? Entre", 5 campos, timer 30s); `SupportChat`→`/api/support`; consent LGPD. **Entregue junto da F5c** (porte da LP completa + BFF fino + máquina de estados `LeadFlowProvider`). *Verificado:* `next build` + smoke E2E do fluxo prompt→cadastro→OTP→chat. ✅

> **Protocolo:** reanálise pré-fase dedicada ao iniciar cada subfase.

## Fase 5 — Conversa de cotação (multi-turn)  ·  V1.5  ·  concluída
**Refatiada em 5a / 5b / 5c** — reanálises, subfases e revisões adversariais em `diario-de-fases.md`;
decisões em DEC-ORB-038..044. Meta: o happy path chat-first (prompt no hero → coleta multi-turn → cotação
no CRM → card/PDF).

- [x] **5a — Persistência + agente** (DEC-ORB-038/039/040/041): `chat_sessions`/`chat_messages` escopados
  (`UNIQUE(session_id,seq)`, `FOR UPDATE`=lock+anti-IDOR), pool isolado + timeouts, `canonical_lead_id`,
  `ConverseAgent` (LangGraph stateless) + extração **determinística** de slots no business (nunca no LLM).
- [x] Entrada **prompt-first no hero** + extração de slots (DEC-ORB-027) — sensível ao contexto (`expected_slot`).
- [x] **5b — Cotação** (DEC-ORB-043): `quote_tool` **orquestrado pelo business** (número do CRM fake, não do
  LLM), `broker_code` autorizado server-side, cotação em centavos escopada à sessão; `pdf_ref` = marcador.
- [x] **5c — LP + card + UTM**: chat multi-turn no frontend (`QuoteCard`), serviço **fake de UTM** (4 campanhas
  2 Meta + 2 Google, **sorteio por submissão**), reconciliação com a LP portada.
- **Verificado:** `ruff` + `pytest` **96** (56 unit + 40 integração) + `next build`; 3 revisões adversariais
  (5a.2/5b/5c) + smoke real multi-turn (slots → **card R$ 1.200,00**; isolamento de sessão; guardrail nas tools). ✅

## Fase 6 — Personalização + Ações + Click_ID  ·  V1.5
Meta: personalizar a cotação e disparar ações via outbox.

- [ ] Personalização/re-cotação (seleção de coberturas) — marketplace multi-seguradora = V2
- [ ] Ações **write-through-outbox**: `crm_update` / `notify` (email/WhatsApp/SMS via `NotificationPort` fake) / `conversion` — só após **confirmação explícita**, idempotentes por `event_id=(session,tipo,turno)`
- [x] **Audit de integração** (habilita a jornada da DEC-ORB-042) — **antecipado na F5b** (DEC-ORB-044):
  tabela append-only `integration_events` (`lead_id`/`session_id`/tipo/payloads) já grava o request/response
  real de `crm_sync`/`ads_conversion`/`crm_price_quote`/`notify_otp` (o OTP nunca registra o código).
- [ ] **Handoff humano**: detectar + flag ortogonal + mensagem honesta + intent na outbox (handler fake)
- [ ] Atribuição por **Click_ID**: capturar gclid/fbclid na LP → persistir no lead → enviar na conversão
- **Verificar:** ação 2× → efeito 1×; conversão com `click_id` deduplicada.

## Fase 7 — CI + verificação Docker + entrega
Meta: gate automatizado e stack reprodutível do zero.

- [ ] `.github/workflows/ci.yml`: job **ai-service** (pytest mock + ruff), job **frontend** (build + test), job **docker build**
- [ ] `/metrics` completo + **README de entrega** (stack, fake vs real, decisões, observabilidade, próximos passos)
- [x] **Endpoint de jornada do lead para avaliação** (DEC-ORB-042, **gated demo-only**) — **concluído
  (antecipado)**: módulo `app/eval/` (read-only). `GET /eval/leads/journey?email=` (JSON **agregado por
  e-mail**: cadastro + mensagens + outbox + cotações + `integration_events`; resolve pela identidade
  canônica, *fallback* lead mais recente) + `GET /eval/leads` (descoberta) + **seed de demo** (`python -m
  app.eval.seed` dirige o fluxo real) + `?format=html` (timeline escapada anti-XSS). **Fail-closed** fora de
  `local` (montagem + rota). *Verificado:* +9 testes (7 integração + 2 unit render) e revisão adversarial
  (0 defeitos de produção; 4 fixes de qualidade de teste). ✅
- [ ] Reconciliar `diario-de-fases.md` + `mem_session_summary`
- **Verificar:** CI verde no push (só mock, sem segredos); `docker compose up --build` do zero: LP sobe, POST persiste + (worker) sincroniza fakes, `/health` OK.

## Fora do V1
Painel admin / RBAC / contas completas (V2 — `roadmap-v2.md`), marketplace multi-seguradora, notificações
**reais** (email/WhatsApp/SMS), cache semântico de LLM (DEC-ORB-029), embedder real leve.
