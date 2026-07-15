# Diário de Fases — SegurAuto

> Uma entrada curta por fase: reanálise pré-fase (mini-roadmap 3–5 itens) e descobertas pós-fase
> (o que mudou vs. o plano, gaps, decisões). Decisões formais vão para `DECISIONS.md`.

---

## Fase 0 — Scaffold + protocolo + infra base

**Reanálise (antes):**
- Planejamento consolidado com 20 decisões (DEC-ORB-001..020), arquitetura em monorepo e corte V1/V2 definido.
- Método: as verificações de rigor (idempotência/atomicidade/async, observabilidade/resiliência, cobertura
  em 5 planos, corte V1/V2) foram feitas na fase de planejamento, com pesquisa em subagentes paralelos.
- Riscos priorizados: fricção de pgvector no Docker (validar cedo) e não-determinismo do LLM no CI (stub default).

**Descobertas (depois):**
- **Engine de banco preguiçoso (lazy):** para o `/health` de liveness responder mesmo com o banco
  fora, a engine só é criada na primeira necessidade (readiness/queries). Alinha com DEC-ORB-016.
- **Verificação dupla:** venv local (`ruff` limpo + `pytest` 2/2, sem infra) **e** `docker compose up`
  real (db `pgvector:pg16` healthy; `/health`→200; `/health/ready`→200 `db:true`; header
  `X-Request-Id`). O `depends_on: service_healthy` segurou o ai-service corretamente.
- **Log de startup** sai com `rid=-` (sem contexto de request) — esperado; o `request_id` só existe
  dentro de uma requisição.
- **Nit inócuo:** `PendingDeprecationWarning` de `python-multipart` (via starlette). O multipart entra
  de fato na Fase 2 (formulário) — tratar o import então.
- **Sem mudança de escopo.** Fase 0 fechada; próxima é a Fase 1 (domínio + ports/adapters + outbox + AiPort).

---

## Fase 1 — Contextos + ports/adapters + persistência + outbox

**Reanálise (antes):**
- **Domínio puro sem SQLAlchemy** (Lead/status, QualificationResult/faixa, rubrica determinística,
  event_id/intents) → testável sem infra e independente da persistência (reforça a extração da V2).
- **Portas + fakes com contrato verificável:** CRM (upsert idempotente + tabela de preços), Ads
  (send_conversion dedup por `event_id`), LLM (stub determinístico), Rerank (heurístico). Os fakes
  precisam **refletir a dedup** (DEC-ORB-014), senão o teste não prova nada.
- **`AiPort`** (qualify/support) com adapter **in-process**; na Fase 1 usa a rubrica determinística
  (placeholder); na Fase 3 delega aos agentes; na V2 vira HTTP client.
- **Persistência resiliente:** `LeadRepository` + `outbox` (`idempotency_key` UNIQUE, correlação
  `request_id`, `retry_count`/`status`), commit-boundary fica no endpoint (Fase 2).
- **alembic** com schemas `business.*`/`ai.*` **sem FK cruzada** + extensão pgvector.
- **Riscos:** env async do alembic; extensão pgvector; manter o domínio livre de SQLAlchemy.

**Descobertas (depois):**
- **Domínio puro (dataclasses, sem SQLAlchemy)** entregou 18 unit tests verdes sem infra — o
  contexto `business` fica independente da persistência (reforça a extração da V2).
- **Separação de schemas provada no banco real:** `alembic upgrade head` criou `business.*` e `ai.*`,
  pgvector + `vector(1536)`, UNIQUE `idempotency_key`, e **FK cruzada business↔ai = 0** (DEC-ORB-021).
- **alembic async** (`env.py` com `run_sync`) funcionou contra asyncpg.
- **Decisão de impl:** `outbox.lead_id` **sem FK** (ref por id) para desacoplar o processamento; FK só
  DENTRO do schema `ai` (`embeddings → documents`).
- **Auto-migrate no startup** do container fica para a Fase 2 (quando `/leads` precisa das tabelas);
  hoje a migração roda via `alembic upgrade head`.
- **Nit persistente:** `PendingDeprecationWarning` de `python-multipart` (starlette) — trato na Fase 2.
- **Sem mudança de escopo.** Próxima: Fase 2 (API de captura `POST /leads` → persist + outbox, dedup por
  `Idempotency-Key`, commit-boundary no endpoint).

---

## Fase 2 — API de captura (fatia vertical, sem IA)

**Reanálise (antes):**
- `POST /leads`: schema validado — **consent obrigatório (LGPD)**, e-mail válido; `Idempotency-Key`
  via header (fallback body/uuid).
- `LeadService.capture`: dedup por chave; persiste `Lead` + enfileira **QUALIFY** na outbox (com
  correlação `request_id`); **não** chama CRM/Ads (isso é o worker da Fase 3).
- **Commit-boundary no endpoint**; sob corrida, `IntegrityError` (UNIQUE) → tratado como dedup →
  garante **1 lead** mesmo com POSTs concorrentes.
- Observabilidade: `lead_received`/`lead_deduped` (PII mascarada) + métrica `leads_captured_total{result}` + `/metrics`.
- **Auto-migrate no startup** (entrypoint `alembic upgrade head`) → o container fica self-sufficient.
- Testes de integração: double POST (sequencial + concorrente) → 1 lead; outbox com 1 intent `qualify`; consent ausente → 422.
- Riscos: `EmailStr` precisa `email-validator`; entrypoint precisa das migrations no image; race handling.

**Descobertas (depois):**
- **Bug pego na verificação (e corrigido):** o engine global do app (cache de módulo em
  `shared/database.py`) fica preso ao event loop do 1º teste; o pytest-asyncio cria um loop novo por
  teste → `RuntimeError: Event loop is closed`. **Fix:** os testes de integração dirigem o app via
  `dependency_overrides[get_session]` com o engine do teste (ligado ao loop corrente).
- **Auto-migrate no entrypoint validado** no stack real (`[entrypoint] alembic upgrade head` → uvicorn).
- **Idempotência ponta a ponta:** `POST` → 201; replay com a mesma chave → **200 e mesmo id**;
  concorrente (`asyncio.gather`) → **1 lead** (UNIQUE + `IntegrityError`→dedup).
- **outbox** com 1 intent `qualify|pending` por lead (CRM/Ads são encadeados pelo worker na Fase 3).
- **Nit multipart** persiste, mas é inócuo — a API é JSON (não usamos forms); deixado como está.
- **Sem mudança de escopo.** Próxima: Fase 3 (worker consome a outbox → qualification_agent+RAG →
  encadeia CRM/Ads idempotentes; at-least-once + dead-letter).

---

## Fase 3 — Worker + agente de qualificação + RAG

**Reanálise (antes):** _(a preencher ao iniciar a Fase 3)_
