# Fase 3b — qualification_agent (LangGraph) + orquestrador

Meta: substituir o placeholder por qualificação real, **estruturada e determinística** com stub.

## Entregáveis
- `ai/agents/config.py` — `AgentConfig` (modelo, provider, temperatura, `max_tokens`, `k`,
  `similarity_threshold`, `use_rerank`, `rag_mode`, `sufficiency_threshold`, `system_prompt`). V1: de env/hardcoded.
- `ai/providers/orchestrator.py` — `ModelOrchestrator.select(task)` → (provider/modelo/params) do `AgentConfig`;
  chamada com **timeout + retry/backoff** (DEC-ORB-018); captura tokens/latência → `log_agent_turn`.
- `ai/agents/state.py` — `TypedDict` do estado do grafo.
- `ai/agents/qualification_agent.py` — LangGraph:
  `rubric_node` (score determinístico) → `retrieve_node` (RAG de critérios) → **[cond]** → `assess_node`
  (LLM refina motivo/faixa dentro de limites) → `combine_node` (score determinístico + explicação).
  **Aresta condicional:** `provider=stub` ou erro de LLM → pula `assess` → **CI determinístico**.
- `ai/api/` — `POST /ai/qualify` (contrato stateless: recebe atributos do lead → `QualificationResult`).
- `business/ai_port.py` — `InProcessAiAdapter.qualify` passa a **delegar ao grafo** (antes usava só a rubrica).

## Invariantes
- O **número/score** tem backbone **determinístico** (rubrica); o LLM só **explica/ajusta com limites**.
- A IA é **stateless** e não lê tabelas de negócio (recebe os atributos por parâmetro).

## Testes
- **unit:** nós puros (rubric, combine, sufficiency), `ModelOrchestrator.select`.
- **integração (LLM stub):** `/ai/qualify` e `AiPort.qualify` retornam `QualificationResult` estruturado e
  **determinístico**; RAG recupera do seed. `real/` opt-in valida OpenAI.

## Reanálise pré-fase (a fazer ao iniciar)
Reler o contrato de `QualificationResult`, a rubrica e o `AgentConfig`; decidir o esquema de saída
estruturada com o LLM (function-calling/structured output) e como o stub o satisfaz deterministicamente.
