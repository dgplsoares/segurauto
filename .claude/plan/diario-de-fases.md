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

## Fase 3 — Enriquecimento assíncrono (refatiada em 3a/3b/3c)

Plano-mestre em `fase-3/`. Decisões DEC-ORB-022..033 formalizadas. Reanálise dedicada por subfase.

### Fase 3a — RAG

**Reanálise (antes):**
- **Chunking simples** do `knowledge_base.md`: agrupar parágrafos (`\n\n`) até ~600 chars.
- **`EmbeddingsPort`:** `StubEmbedder` determinístico (vetor 1536 semeado por hash do texto,
  `is_semantic=False` → retrieval por **keyword**); `OpenAIEmbedder` lazy/opt-in (`is_semantic=True`).
- **`VectorStore`:** `search_keyword` (`ILIKE` sobre `ai.embeddings.chunk`) e `search_semantic`
  (pgvector `<=>` cosine, vetor passado como literal `CAST(:q AS vector)`). Ingestão sempre grava
  `documents` + `embeddings` (com o pseudo-vetor do stub, para o modo real funcionar sem migração extra).
- **`RagService`:** escolhe modo por `embedder.is_semantic`; **sempre aplica `HeuristicRerank`** para um
  score uniforme; **Context Validation** (min chunks + min score) → `rag_mode=rag_preferred` marca
  `sufficient=False` (o agente decide recusa/handoff, na 3b/4).
- **Testes:** unit (chunking, stub determinístico, `RagService` com `FakeVectorStore` — keyword,
  suficiente vs. insuficiente) sem infra; integração (ingest do seed → keyword recupera trecho relevante +
  plumbing do `search_semantic` determinístico com pgvector).
- **Riscos:** passar vetor 1536 como literal p/ pgvector; garantir CI sem rede (stub + keyword); a base é
  genérica (sem escopo de lead — isolamento não se aplica à 3a).

**Descobertas (depois):**
- **RAG dual-mode implementado e verificado** com pgvector real: modo stub = keyword
  (`is_semantic=False`), modo real = pgvector `<=>` cosine. Ingest do seed → keyword recupera o trecho
  relevante; o *plumbing* semântico executa (embedding armazenado como **`vector(1536)`**).
- **`StubEmbedder`** determinístico (`random.Random` semeado por hash), normalizado, dim 1536 — gravado
  como literal `CAST(:e AS vector)`.
- **Seed CLI idempotente** (`python -m app.ai.rag.seed`): 1ª vez ingere 4 chunks; 2ª vez faz *skip*.
- **Decisão de impl:** `search_keyword` usa `OR` de `LIKE` (não `ANY(:array)`) para evitar incerteza de
  binding de array; **sufficiency** = min_chunks + min_score, com `HeuristicRerank` dando score uniforme.
- **Sem mudança de escopo.** Próxima: **3b** (qualification_agent LangGraph + ModelOrchestrator + `/ai/qualify`).

**Verificado (3a):** `ruff` limpo + `pytest` **30/30** (unit + integração); seed CLI + idempotência; `vector_dims=1536`. ✅

### Fase 3b — qualification_agent (LangGraph) + orquestrador

**Reanálise (antes):**
- **Descoberta que ajusta o plano:** a **qualificação NÃO precisa de RAG** — ela pontua os *atributos do
  lead* (rubrica) + explicação opcional do LLM. O `retrieve_node` **sai** do grafo de qualificação (RAG
  fica para o **support agent**, F4). Isso mantém `AiPort.qualify` **stateless** (sem sessão/DB).
- **Grafo (LangGraph):** `rubric → [cond] → assess → combine`. A **aresta condicional** usa
  `AgentConfig.use_llm_assess` (default **False** = rubrica-only determinístico; **True** em `provider=openai`).
- **StubLLM no assess** quando `use_llm_assess=True` → caminho do LLM exercitado de forma determinística no CI.
- **`ModelOrchestrator`:** `complete` com **timeout + retry/backoff** + `log_agent_turn`; degrada p/ `None`
  em erro → o `combine` usa o `reason` da rubrica (nunca falha o grafo).
- **`AgentConfig`** (dataclass + factory de `settings`) — seam da V2 (DEC-ORB-022).
- **`/ai/qualify`** é **stateless** (sem DB) → testável em CI sem infra; `AiPort.qualify` delega ao grafo.
- **Deps:** adicionar `langgraph`. **Riscos:** resolução de versão do langgraph; nós sync+async no mesmo grafo.

**Descobertas (depois):**
- **Gotcha do LangGraph (pego na verificação):** nome de nó **não pode colidir com chave de estado** —
  o nó `rubric` colidia com a chave `rubric` do `QualState` → `ValueError` no `add_node`. **Fix:** nó
  renomeado para `score`. (langgraph **0.3.34**, faixa `>=0.2.20,<0.4`.)
- **Ajuste do plano confirmado:** qualificação **sem RAG** (nó `retrieve` removido) → `AiPort.qualify`
  **stateless**. RAG fica para o support agent (F4).
- **Grafo:** `score → [cond use_llm_assess] → assess(StubLLM) → combine`. Default rubrica-only
  determinístico; `assess` exercitado com stub; **degrada** (LLM erro → `None` → combine usa rubric.reason).
- **`/ai/qualify`** stateless verificado em CI e na stack Docker (100/hot e 20/cold).
- **Sem outra mudança de escopo.** Próxima: **3c** (worker: processo separado, outbox `SKIP LOCKED` +
  dead-letter; qualify → encadeia CRM/Ads idempotentes; contrato do CRM `status`/`source`).

**Verificado (3b):** `ruff` limpo + `pytest` **34/34**; docker `POST /ai/qualify` (100/hot, 20/cold). ✅

### Fase 3c — Worker (processo separado)

**Reanálise (antes):**
- **Ajuste de escopo:** **UTM/Click_ID adiado para F5/F6** — sem o frontend não há dado para popular
  (o serviço fake de UTM é F5). A 3c foca no **worker** e adiciona só a coluna que ele precisa
  (`next_attempt_at`). Isso mantém a 3c enxuta e verificável.
- **Worker = processo separado** (compose `worker`, `python -m app.business.worker`). Loop callable
  `run_worker_loop(stop_event, poll)` + `drain_once` (testável) + `process_one` (1 intent por transação).
- **Claim:** `select(OutboxRow).with_for_update(skip_locked=True)` WHERE `pending` AND
  `next_attempt_at<=now` ORDER BY `created_at` LIMIT 1.
- **Handlers:** `qualify` → `AiPort.qualify` → aplica score/band/reason + `status=qualified` → **encadeia**
  `crm_sync`/`ads_meta`/`ads_google` (mesma tx, `request_id` p/ correlação); `crm_sync` → `CrmPort.upsert`
  (`status=synced`; contrato CRM: `source=landing_page`, `status=qualified`); `ads_*` → `send_conversion(event_id)` dedup.
- **Idempotência:** `status=done` não é re-pego (efeitos 1×); handlers idempotentes (event_id/upsert) para
  at-least-once. Erro → rollback → `retry_count++`/`next_attempt_at` backoff; `≥MAX` → `dead`.
- **Fakes singletons** (`lru_cache`) para o estado de dedup persistir in-process + `reset_adapters()` nos testes.
- **Riscos:** `FOR UPDATE` segura lock durante I/O (ok com fake/1 intent); retry em tx separada pós-rollback; re-hidratar `request_id`.

**Descobertas (depois):**
- **Fatia vertical fechada e2e com o worker SEPARADO:** `POST /leads` (received) → o worker (container
  próprio) enriquece sozinho → `qualified` → `crm_synced` → 2 conversões → lead **`synced` (100/hot)**;
  outbox tudo `done`.
- **Correlação sobrevive à fronteira assíncrona (verificado):** os logs do worker saem com o **mesmo
  `request_id`** do POST original (re-hidratado da outbox) — `grep rid=X` cobre form→worker→IA→CRM→Ads.
- **Idempotência:** worker 2× → efeitos 1× (`status=done` não re-pego); no reprocesso forçado, o handler
  **deduplica** por `event_id`. Dead-letter após `MAX_RETRIES`.
- **UTM/Click_ID adiado para F5/F6** (sem frontend não há dado) — a 3c só adicionou `next_attempt_at`.
- **Design testável:** `process_one`/`drain_once` (testes) vs `run_worker_loop` (processo). `SKIP LOCKED`
  + backoff persistente + retry em tx separada pós-rollback.
- **Sem outra mudança de escopo. Fase 3 COMPLETA (3a+3b+3c).** Próximo: **Fase 3.5 — Hardening/Auth**
  (pré-F4), começando pela correção do LEAK-1 e o design do auth/OTP.

**Verificado (3c):** `ruff` limpo + `pytest` **37/37**; e2e Docker (worker separado → lead `synced`, correlação preservada). ✅

---

## Fase 3.5 — Hardening / Auth

**Reanálise (antes) — dedicada + pentest adversarial (deu `holds=false`, 7 furos):**
- **Método:** workflow de 3 desenhistas (escopo+LEAK-1, auth/OTP, isolamento) + pentest adversarial. O
  pentest achou 7 furos, vários por **contradição entre as trilhas** (ex.: `UNIQUE(email)` vs "2 leads
  legítimos"). Detalhe: `workspace/10`.
- **Decisões do usuário:** (D1) **hardening rápido agora na 3.5; auth/OTP no início da F4**; (D2) **e-mail =
  identidade, SEM `UNIQUE(email)`** (permite 2º veículo/re-cotação); (D3) **sessão só pós-OTP**. Isso fecha
  os furos B1/B3/B4/B5 do pentest.
- **Escopo da 3.5 (agora):** (a) **correção do LEAK-1** — `LeadResponse` perde `score`/`band`; no dedup
  compara e-mail normalizado → dono (mesmo e-mail) 200 `{id,status,deduped}`, colisão de key → **409
  neutro**; sem `UNIQUE(email)`, capturas concorrentes mesmo-email/chave-dif geram leads distintos (sem
  500). (b) **endurecimento de observabilidade** — `X-Request-Id` só de origem confiável e **nunca
  ecoado**; middleware **pure-ASGI** (pré-streaming); **masking de PII** central seguro (e-mail + CPF
  formatado + placa maiúscula; **sem** regex genérico que corrompe UUID) + `echo=off`.
- **Auth/OTP (design aprovado, implementar na F4):** token opaco server-side → `lead_id` via
  `require_session`; sessão **só pós-OTP** (sliding ~30min + TTL absoluto); OTP 5 díg. hasheado, **não
  consome código em tentativa errada** (cooldown/backoff por email[,IP]); rate-limit; identidade=e-mail
  verificado sem UNIQUE; enumeração aceita+rate-limit (IP/captcha V2); `NotificationPort` fake.
- **Riscos:** masking por regex pode corromper UUID (mitigado: e-mail/CPF-formatado/placa-maiúscula,
  testado contra UUID); pure-ASGI pode regredir correlação (teste de concorrência).

**Descobertas (depois):**
- **LEAK-1 corrigido e verificado:** POST com key de outra identidade → **409 neutro** (`{"detail":
  "idempotency_key_conflict"}`), sem `id`/`score`/`band`/e-mail; resposta de captura **sem `score`/`band`**.
- **Obs endurecida (verificado):** `X-Request-Id` forjado **não é ecoado** (resposta traz rid server-side);
  middleware **pure-ASGI**; **masking central** redige e-mail/CPF-formatado/placa **sem corromper UUID**
  (testado); e-mail cru **ausente** dos logs; conflito logado só com `key_sha`.
- **Sem `UNIQUE(email)`** (D2): capturas concorrentes mesmo-email/chave-diferente geram leads distintos —
  **não** há o 500 que o pentest apontou (B5) nem enumeração via 409 no cadastro (B1).
- **Auth/OTP:** desenho reconciliado e **aprovado (DEC-ORB-037)**; implementação no **início da F4** (junto do chat).
- **Sem outra mudança de escopo. Fase 3.5 concluída.** Próximo: **F4** — auth/OTP + support single-turn + LP.

**Verificado (3.5):** `ruff` limpo + `pytest` **42/42**; docker (409 no LEAK-1, X-Request-Id não-ecoado, PII mascarada). ✅

---

## Fase 4 — Auth + Suporte + LP (refatiada em 4a/4b/4c)

Plano-mestre em `fase-4/`. Reanálise dedicada por subfase (contexto fresco → antecipar gaps).

**Reanálise-mestre (antes):**
- **4a — Auth/OTP** (DEC-ORB-037, já desenhado + verificado por pentest): tabelas `auth_sessions`/`otp_codes`
  (migration 0003), `AuthService`/`OtpService`, `NotificationPort` fake, `/auth/request-otp` +
  `/auth/verify-otp`, dependency **`require_session`** (token→lead_id), **sessão só pós-OTP**, e-mail =
  identidade **sem UNIQUE**, OTP **cooldown-não-burn** + rate-limit, sliding+absoluto. É o **pré-requisito**.
- **4b — support_agent single-turn** (RAG): grafo LangGraph `guardrail_in → retrieve → validate → generate
  → guardrail_out → handoff`; `AiPort.support` real + `POST /ai/support` (stateless); `POST /support/chat`
  no `business` **autenticado por `require_session`** (anti-IDOR). **Single-turn = stateless** → histórico
  persistente (`chat_sessions`/`chat_messages`) só na **F5** (multi-turn). RAG genérico compartilhado (sem
  dado de lead no vector store). Guardrail de prompt-injection (scope-and-strip).
- **4c — LP conectada** (Next.js do Figma Make): `LeadForm` → `/api/lead` (BFF) → `/leads`; **modal de OTP**
  (botão "Já tem cadastro? Entre", 5 campos, timer 30s); `SupportChat` → `/api/support`. Validação
  client+server; consent LGPD no modal.
- **Riscos:** 4a é o mais crítico (implementar exatamente o desenho reconciliado do pentest — cooldown-não-burn,
  fail-closed do pepper); integração do export do Figma Make (deps próprias) na 4c; manter support stateless.

**Descobertas (depois):** _(por subfase)_

### Fase 4a — Auth / OTP

**Reanálise (antes):**
- Implementar o **desenho já reconciliado por pentest** (DEC-ORB-037 / `fase-4/4a-auth-otp.md`). Pontos de
  atenção que o pentest cravou: **(a) cooldown-não-burn** — tentativa errada de OTP incrementa `attempts` +
  `last_attempt_at` e aplica backoff, mas **NÃO consome** o código (senão um terceiro tranca a vítima — B2);
  **(b) pepper fail-closed** fora de `environment=local`; **(c) e-mail = identidade sem UNIQUE** → resolve o
  lead **mais recente** por e-mail; **(d) resposta 202 neutra** no request-otp (envia só se houver lead);
  **(e)** token guardado como `sha256` (nunca cru); sessão **sliding + absoluto**.
- Tabelas: migration 0003 (`auth_sessions`, `otp_codes` com `attempts`/`last_attempt_at`/`consumed_at`).
- `require_session` (Bearer → `validate_session` → `lead_id`) — base do anti-IDOR da 4b; comita o *slide*.
- Testes: OTP válido→token; errado→401 **sem consumir**; expirado/reuso→401; **anti-lockout** (erros de 3º
  não impedem o dono); sessão expira (idle+absoluto); `require_session` bloqueia sem token.
- **Riscos:** corrida no verify (`FOR UPDATE`); relógio consistente; não logar o código nunca.

**Descobertas (depois):**
- **Auth/OTP implementado** (desenho reconciliado do pentest). **Cooldown-não-burn verificado:** palpite
  errado incrementa `attempts`+`last_attempt_at` e aplica backoff (`2^attempts`, cap 60s) mas **não
  consome** → após o cooldown, o código legítimo ainda funciona (anti-lockout B2). Reuso/expiração/absoluto ok.
- **OTP nunca logado** (só `email` mascarado; grep por `code=[0-9]{5}` = vazio); token guardado como `sha256`.
- **`require_session`** pronto (Bearer→lead_id, comita o *slide*) — usado na 4b. `request-otp` **202 neutro**;
  envia só se há lead.
- **Decisão de teste:** seed de OTP conhecido + avanço do cooldown via SQL (`last_attempt_at = now()-90s`)
  para não depender do relógio.
- **Sem mudança de escopo. 4a concluída.** Próximo: **4b** (support_agent single-turn + `/support/chat` autenticado).

**Verificado (4a):** `ruff` limpo + `pytest` **52/52** (security + auth flow); docker (auto-migrate 0003, 202/401, OTP não vaza código). ✅
