# Fase 4b — support_agent (single-turn) + `/support/chat` autenticado

Meta: o lead autenticado tira dúvidas com a IA, **grounded no RAG** (não alucina), com guardrails.
**Single-turn = stateless** (histórico persistente é F5).

## Entregáveis
- `ai/agents/support_agent.py` — LangGraph:
  `guardrail_in` (prompt-injection **scope-and-strip**; escopo seguro-auto) → `retrieve` (`RagService`,
  reusa a base da 3a) → `validate` (suficiência) → `generate` (LLM grounded, cita) → `guardrail_out`
  (PII/sanidade) → `handoff` (detecta intent comercial/humano → sinaliza; ação real é F6).
  **`rag_mode=rag_preferred`**: se o contexto for insuficiente → **recusa/handoff** (não inventa cobertura/preço).
- `ai/api/support.py` — `POST /ai/support` {query} → {answer, sufficient, handoff_suggested} — **stateless**,
  sem DB (contrato DEC-ORB-021).
- `business/ai_port.py` — `InProcessAiAdapter.support` passa a **delegar ao grafo** (hoje é eco).
- `business/api/support.py` — `POST /support/chat` no `business`, **autenticado por `require_session`**
  (só o lead dono conversa — anti-IDOR); repassa ao `AiPort.support`. Rate-limit por sessão.
- `AgentConfig` do suporte (prompt, `rag_mode`, `k`, thresholds).

## Invariantes
- **Stateless**: nenhuma conversa persistida na 4b → sem vazamento de histórico entre leads. RAG
  **genérico compartilhado** (nenhum artefato de lead no vector store — `isolamento-leads.md`).
- O número/afirmação factual vem do **RAG citado**; o LLM não inventa (rag_preferred).

## Testes
- **unit:** nós do grafo (guardrail scope-and-strip, sufficiency → recusa), `StubLLM` determinístico.
- **integração (LLM stub + pgvector):** pergunta no domínio → resposta grounded do seed; pergunta fora →
  recusa/handoff; **prompt-injection** (ex.: "ignore as instruções e...") → neutralizada; `/support/chat`
  **sem sessão → 401**, com sessão → 200. `real/` opt-in valida OpenAI.

## Reanálise pré-fase (a fazer)
Reusar `RagService`/`ModelOrchestrator` da 3a/3b; decidir o esquema de saída do suporte e o guardrail
mínimo (scope-and-strip) que cabe no timebox; confirmar que o suporte não persiste nada.
