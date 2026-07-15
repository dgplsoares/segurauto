# Fase 3c — Worker (processo separado) consumindo a outbox

Meta: processar o enriquecimento fora do request, **at-least-once**, idempotente e resiliente.

## Decisão de topologia — processo SEPARADO
Serviço `worker` no `docker-compose` (**mesma imagem**, comando `python -m app.business.worker`, sem
portas, `depends_on: db healthy`, `restart: unless-stopped`).
**Por quê:** in-process, um LLM lento/crash divide event loop + pool + CPU com `POST /leads` e derruba a
captura — o que a outbox existe para evitar. A outbox isola no plano de **dados**; o processo separado
isola no plano de **runtime**. É também a topologia-alvo da V2 (backend + worker + serviço de IA).
**Hedge:** o loop é uma função callable `run_worker_loop(session_factory, *, stop_event, poll_interval,
batch_size)`; modo in-process sob flag `WORKER_IN_PROCESS=0` (default) só para dev/testes.

## Claim da outbox (concorrência sem duplicar)
```sql
SELECT * FROM business.outbox
 WHERE status='pending' AND (next_attempt_at IS NULL OR next_attempt_at <= now())
 ORDER BY created_at
 FOR UPDATE SKIP LOCKED
 LIMIT :n;      -- n pequeno (1..10)
```
- `SKIP LOCKED` garante 1 intent por worker sob concorrência — **não** é exactly-once: crash pós-processo/
  pré-commit reprocessa → **handlers idempotentes são obrigatórios** (event_id estável, upsert, re-check terminal).
- **Backoff persistente:** coluna aditiva `next_attempt_at` (migration alembic). Falha transitória:
  `retry_count++`, `next_attempt_at = now()+backoff`, mantém `pending`. `retry_count >= max` → `status='dead'` (**dead-letter**).
- **Polling:** drain-then-poll; sleep ~1-2s com **jitter** quando vazio. `LISTEN/NOTIFY` fica pós-V1.

## Unidade de trabalho (1 transação curta)
`claim → processa → (se QUALIFY: enfileira crm_sync/ads_meta/ads_google na MESMA tx) → marca done → commit`.
- `qualify` → `AiPort.qualify` → aplica score/faixa/status no lead → **encadeia** as intents downstream.
- `crm_sync` → `CrmPort.upsert_lead` (idempotente). `ads_*` → `AdsPort.send_conversion(event_id)` (dedup).

## Observabilidade
`log_agent_turn` (tokens) no qualify; eventos `outbox_picked/done/retry/deadletter`; métricas de outbox
(profundidade/lag como gauge derivado de query no `/metrics` do ai-service, que tem DB) e de LLM.

## Testes
- **integração:** POST → worker processa → lead qualificado + CRM sync + 2 conversões (asserts nos fakes).
  **Rodar o worker 2× → efeitos externos 1×** (idempotência). Dead-letter após N falhas.

## Reanálise pré-fase (a fazer ao iniciar)
Confirmar a migration `next_attempt_at`; validar o `SKIP LOCKED` com 2 workers; garantir timeout estrito
nas chamadas externas; graceful shutdown (SIGTERM → `stop_event`).
