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

**Reanálise (antes):** _(a preencher ao iniciar a Fase 1)_
