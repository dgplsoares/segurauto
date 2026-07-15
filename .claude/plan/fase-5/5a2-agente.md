# Fase 5a.2 — ConverseAgent (o agente multi-turn) · ponto de partida

> **Retomar aqui.** A F5a.1 (persistência + endpoints) está concluída, revisada e no GitHub (`738b91d`).
> Esta fatia troca o **stub** por um agente real. O design já está decidido — ver DEC-ORB-039 e a reanálise
> em [`5a-persistencia-conversa.md`](5a-persistencia-conversa.md) (seção "Design escolhido", ponto 5 do grafo,
> e emendas E5/E6/E7/E8). Este doc é só o "por onde começar".

## O que já existe (da 5a.1) — o terreno

- Tabelas `business.chat_sessions` / `chat_messages` / `identities` (migração `0004`).
- Endpoints `POST /support/sessions`, `POST /support/sessions/{id}/messages` (turno), `GET .../messages`.
- Gate de posse compartilhado + 404 neutro (E1); idempotência de turno via `client_turn_id` (E2); `seq`
  auto-curável (E4); `canonical_lead_id` (DEC-ORB-041); pool isolado + timeouts (E3, com o fix `738b91d`
  que garante 409 na contenção).
- `domain/slots.py`: validação **determinística de VALOR** (`validate_slots`, `missing_slots`,
  `is_ready_to_quote`) — já pronta para a extração.
- **O seam a plugar:** `ChatService._generate(message, slots) -> (reply, new_slots, handoff)` em
  [`app/business/service/chat_service.py`](../../../ai-service/app/business/service/chat_service.py) —
  hoje devolve um ack estático e **não** extrai slots. A 5a.2 substitui o corpo por uma chamada ao agente.

## Objetivo da 5a.2

Turno real: extrair slots (determinístico), responder grounded (RAG `rag_preferred`), sinalizar
`ready_to_quote` quando os slots estão completos — via `AiPort.converse` → `/ai/converse` **stateless**.

## Plano de implementação (arquivos)

1. **`app/ai/agents/converse_agent.py`** (novo) — `ConverseAgent` LangGraph, esqueleto do 4b:
   `guard_in → extract → retrieve → [cond] → respond | refuse | signal`. Nós **disjuntos** das state keys
   (gotcha `score`×`rubric`). `RagService` **no state** (sem engine global). **Sem checkpointer**
   (reentrância pura); se um dia usar, `thread_id === session_id`. `get_converse_agent()` `@lru_cache`.
   `converse(*, transcript, slots, user_message, rag) -> dict {reply, slots, missing, ready_to_quote, handoff_suggested}`.
2. **`app/ai/agents/config.py`** — `get_converse_config()` (frozen `AgentConfig`: provider/model/prompts/
   thresholds/`rag_k`/`rag_min_score`/`rag_mode`); StubLLM default (CI-determinístico).
3. **`app/ai/api/converse.py`** (novo, montar sob `/ai`) — `POST /ai/converse` **stateless**: recebe só
   `{transcript, slots, user_message}` (+ RAG injetado in-process). ⚠️ **Sem `session_id`/`lead_id` no
   contrato** (furo IDOR-LOW da reanálise — não dar ao contexto `ai` uma chave para query cross-lead).
4. **`app/business/ai_port.py`** — `AiPort.converse(...)` + `InProcessAiAdapter` (monta `RagService` com a
   sessão do request; V2 vira client HTTP, mesmo contrato).
5. **`app/business/service/chat_service.py`** — `_generate` → monta o **transcrito** (`list_messages` +
   **janela** `chat_transcript_max_turns` + **sanitização por linha**) e chama `AiPort.converse`; mescla os
   slots retornados com `validate_slots` (E6) e persiste; `ready_to_quote` deriva de slots **validados**.
6. **Guardrails do transcrito (E5/E7):** o transcrito é **dado não-confiável** → sanitizar/**delimitar cada
   linha** na montagem e passar `safe_message` como turno corrente (não reler a linha crua recém-gravada).
   `strip_injection` = **best-effort**. ⚠️ **DEC-ORB-021**: `business` não importa de `ai` — mover
   `strip_injection` para um `app/shared/guards.py` (reuso `business`+`ai`) **ou** sanitizar no lado `ai`.
   Preferir a sanitização **na montagem** (business) → `shared/guards.py`.
7. **Extração determinística de slots (E6):** `domain/slots.py` ganha `extract_slots_from_text(text) -> dict`
   (regex/regras: placa/veículo, CEP, "tem corretor?"/código). `broker_code` só **formato** aqui
   (autorização no CRM = F5b). NÃO por LLM.
8. **Masking estendido (E8):** `shared/observability.py` `redact_pii` — adicionar **CEP** (`\d{5}-?\d{3}`),
   **telefone BR**, **placa case-insensitive**; **neutralizar CR/LF**. NUNCA logar `chat_messages.content`
   nem `slots` crus.

## Verificação prevista (inclui adversarial)

- Unit: extração determinística de slots; masking de CEP/telefone/placa/CRLF; grafo (nós × state keys).
- Integração: turno in-domain responde + extrai slots + `missing_slots` encolhe; out-domain **recusa**
  (`rag_preferred`); **injeção plantada no turno 1 não re-executa no turno N** (E5); slots completos →
  `ready_to_quote=true` + `quote_ready_at` gravado; `/ai/converse` sem `session_id` no contrato.
- `ruff` + suite verde; smoke HTTP na stack real; grep-clean; commit + push.

## Gotchas a lembrar

- Colisão **nome-de-nó × chave-de-estado** no LangGraph (renomear, como `score`×`rubric` fez).
- **Engine global** preso ao event loop → sempre `RagService` no state com a sessão do request.
- **asyncpg × `OperationalError`**: timeouts do Postgres vêm como `DBAPIError` base — o LLM agora roda sob o
  `FOR UPDATE`, então a contenção é real; o mapeamento por `sqlstate` (`concurrency_http_error`, fix
  `738b91d`) é o que garante 409/503 em vez de 500.
- Commit **SEM** trailer `Co-Authored-By`; **grep-clean** (nenhuma referência a projetos/empresas externos —
  o padrão de busca fica só no scratchpad/comando, nunca no repo) vazio antes de cada commit; Engram sempre
  `project="orbitus"`.
