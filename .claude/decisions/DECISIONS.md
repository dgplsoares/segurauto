# Decisões de Arquitetura — SegurAuto (DEC-ORB)

> Registro rastreável das decisões não triviais. Formato: Contexto / Opções / Escolha / Trade-off.
> Alimenta a seção de decisões do README de entrega.

---

## Núcleo de arquitetura

### DEC-ORB-001 — Integrações externas atrás de Ports & Adapters
- **Contexto:** o produto depende de CRM, plataformas de anúncios, LLM e reranker — todos externos e,
  nesta entrega, fakes.
- **Escolha:** cada integração é uma **porta** (`Protocol`/ABC): `CrmPort`, `AdsPort`, `LLMPort`,
  `RerankPort`. Implementação **fake é o default**; **real é opt-in por `.env`**. O domínio depende só da interface.
- **Trade-off:** indireção extra, paga com testabilidade e troca fake↔real sem tocar no núcleo.

### DEC-ORB-002 — ai-service (FastAPI) é dono do ciclo de vida do lead; Next.js é BFF
- **Contexto:** a captura precisa persistir, qualificar e sincronizar; o front precisa falar com isso sem expor segredos.
- **Escolha:** o **ai-service** concentra domínio/persistência/qualificação/sync; o Next.js expõe
  route handlers (`/api/lead`, `/api/support`) como **BFF/proxy fino**.
- **Trade-off:** um hop de rede a mais; ganha CORS resolvido, segredo escondido e validação server-side.
- **Refino (DEC-ORB-021):** o processo hospeda o lifecycle, mas internamente o módulo `business` é a
  unidade dona/**extraível** e a IA fica atrás de uma porta (`AiPort`).

### DEC-ORB-003 — PostgreSQL + pgvector como banco único
- **Contexto:** há dados relacionais (leads) e vetoriais (embeddings do RAG).
- **Escolha:** um único Postgres com extensão **pgvector**.
- **Trade-off:** acoplar OLTP e vetor é aceitável nesta escala; separar fica como evolução.

### DEC-ORB-004 — Processo de desenvolvimento versionado em `.claude/`
- **Escolha:** protocolo, decisões, análise, plano e diário ficam versionados (SDD), tornando o método rastreável.
- **Trade-off:** docs de processo no repo; a transparência supera o custo.

### DEC-ORB-005 — Serviço de IA em camadas
- **Escolha:** `api → services → agents → providers/repositories/core`. Cada camada testável isolada.
- **Trade-off:** mais arquivos, em troca de fronteiras claras.

### DEC-ORB-006 — Split de testes (mock + real)
- **Escolha:** unit (domínio sem infra) + integração (adapters fake + LLM stub) como **gate de CI**;
  testes reais (OpenAI/CRM) **opt-in por `.env`**, sem mudar código.
- **Trade-off:** o CI não exercita rede real; mitigado por contrato tipado dos dois lados.

### DEC-ORB-007 — Agentes compartilham RAG e orquestrador
- **Escolha:** os dois agentes LangGraph (qualificação + suporte) compartilham um único `RagService` +
  `ModelOrchestrator`.
- **Trade-off:** acoplamento a um módulo comum, evita duplicar o pipeline RAG.

### DEC-ORB-008 — Qualificação como saída estruturada
- **Escolha:** `QualificationResult` é **saída estruturada** (score + faixa + motivo) combinando rubrica
  determinística + LLM, testável sem LLM real.
- **Trade-off:** menos "mágica" do LLM, mais previsibilidade e CI estável.

### DEC-ORB-009 — Fatia vertical antes de largura
- **Escolha:** fechar o caminho ponta a ponta (LP → captura → persist → qualifica → CRM+Ads fake) antes
  de features largas; suporte e polish depois.
- **Trade-off:** features iniciais finas, mas o caminho de ponta a ponta é provado cedo.

### DEC-ORB-010 — Monorepo + docker-compose + CI na raiz
- **Escolha:** um repositório com `frontend/ + ai-service/ + docker-compose.yml` e GitHub Actions
  com **um job por stack**.
- **Trade-off:** o repo cresce; a orquestração e a verificação únicas compensam.

---

## Idempotência, atomicidade e assincronismo

### DEC-ORB-011 — Idempotência da submissão de lead
- **Contexto:** double-click / retry de rede duplicaria o lead — e o produto é justamente captação.
- **Escolha:** `Idempotency-Key` (uuid gerado no client ao carregar o form) + coluna **UNIQUE**; reenvio
  com a mesma chave devolve o mesmo lead (no-op). Dedup de negócio adicional por (email/telefone) em janela.
- **Trade-off:** +1 coluna/índice; elimina leads duplicados sob retry.

### DEC-ORB-012 — Atomicidade por commit-boundary + outbox
- **Contexto:** não é possível colocar `persist + CRM + Ads` numa transação de banco (CRM/Ads são I/O externo).
- **Escolha:** o **domínio não commita**; o **endpoint é o boundary**. O lead e as **intents de efeito
  externo** (qualify, crm_sync, ads_meta, ads_google) são gravados como **outbox na mesma transação**.
- **Trade-off:** +1 tabela (outbox) e um worker; ganha atomicidade real do que o banco controla + zero efeito parcial.

### DEC-ORB-013 — Assincronismo request↔enriquecimento
- **Contexto:** qualificar (LLM) + CRM + Ads adicionam segundos; o usuário não pode esperar isso no submit.
- **Escolha:** `POST /leads` responde **após persistir**; qualificação + CRM + Ads são processados por um
  **worker** que consome a outbox (**at-least-once**). Fallback documentado: `BackgroundTasks` (a idempotência não muda).
- **Trade-off:** consistência eventual do enriquecimento; resposta rápida e resiliente a quedas de dependências.

### DEC-ORB-014 — Idempotência dos efeitos externos
- **Escolha:** `event_id` estável (lead + tipo) nas conversões (dedup nas plataformas de anúncios);
  **upsert** idempotente no CRM por chave do lead; cada handler do worker **re-checa estado terminal** antes de
  agir; **retry com backoff** em falha transitória. Os fakes refletem a dedup (senão o teste não prova nada).
- **Trade-off:** um pouco mais de código nos handlers; retries tornam-se seguros.

---

## Observabilidade e resiliência

### DEC-ORB-015 — Logs estruturados + correlação
- **Escolha:** módulo de observabilidade com `configure_logging()` idempotente; **correlação
  `request_id`/`lead_id`** via `contextvars`/middleware; eventos de ciclo de vida do lead; **log de turno
  do agente** (modelo, tokens, latência = custo visível).
- **Trade-off:** disciplina de log nos pontos de transição; rastro grep-able e custo de LLM visível desde o dia 1.

### DEC-ORB-016 — Endpoints de saúde e métricas
- **Escolha:** `/health` (liveness) + `/health/ready` (DB + migrations) + **`/metrics`** Prometheus com set
  mínimo (leads capturados, conversões por plataforma, distribuição de score, profundidade da outbox,
  tokens/latência de LLM).
- **Trade-off:** sem dashboards no time-box (só o endpoint pronto para scraping).

### DEC-ORB-017 — Resiliência de infra
- **Escolha:** Postgres com **volume nomeado** + **healthcheck** + `depends_on: service_healthy` +
  `restart: unless-stopped`; **migrations com alembic** desde o início.
- **Trade-off:** um pouco mais de setup no compose; dados sobrevivem a restart e o schema evolui sem perda.

### DEC-ORB-018 — Resiliência de integrações
- **Escolha:** **timeout** em toda chamada HTTP; **retry com backoff** em 5xx/erro de conexão (4xx não
  retenta); **dead-letter** na outbox após `max_retries`. **PII/LGPD:** dados pessoais mascarados nos logs.
- **Trade-off:** complexidade de retry/DLQ; evita retry infinito e vazamento de PII.

### DEC-ORB-019 — Observabilidade end-to-end em 5 planos
- **Escolha:** cobrir HTTP, ciclo de vida do lead (**incl. atualização**), worker/outbox, IA/RAG e
  integrações — com a **correlação sobrevivendo à fronteira assíncrona** (ids gravados na linha da outbox e
  re-hidratados no worker). Sinais de segurança/abuso (`rate_limit_hit`, `validation_rejected`, `guardrail_triggered`).
- **Trade-off:** +1 coluna de correlação na outbox e mais pontos de log; visibilidade de ponta a ponta dos dois fluxos.

---

## Escopo

### DEC-ORB-020 — Corte V1/V2 (painel admin é V2)
- **Contexto:** gestão de conteúdo/IA/RAG/leads/usuários idealmente tem UI, mas o time-box é curto.
- **Escolha:** **V1** gerencia tudo por **env vars / hardcoded / seed / escrita direta no banco** (ex.:
  vetorização de PDFs → chunks/embeddings/pgvector via script; leads persistidos + sync automático com CRM
  fake). O **painel admin** (CMS da LP, config de IA, upload/gestão de RAG, Kanban+lista de leads,
  usuários/permissões) é **V2**.
- **Trade-off:** sem UI de gestão agora; a V1 mantém os **seams** (`config`, content provider,
  `IngestionService`, `lead.status`, namespace `/admin`) para a V2 ser **aditiva**, não retrabalho.
  Ver `.claude/plan/roadmap-v2.md`.

---

## Evolução de topologia

### DEC-ORB-021 — Monólito modular extraível (preparado para separar backend de negócio na V2)
- **Contexto:** a V1 entrega **um** serviço Python (FastAPI). Numa evolução, a lógica de negócio
  (leads, eventos de conversão, conteúdo da LP, usuários/permissões) pode virar um **backend dedicado
  separado**, mantendo o Python/FastAPI como **infraestrutura de IA**. Sem preparo, essa separação vira
  rewrite tenso, split de banco doloroso e correlação perdida no novo hop.
- **Escolha:** desde a V1, tratar o serviço como **monólito modular extraível**, com dois bounded
  contexts e um boundary duro:
  - `business/` (leads, `status`/lifecycle, outbox, eventos de conversão, adapters CRM/Ads) — a **unidade
    de negócio** (futuro backend dedicado).
  - `ai/` (agentes LangGraph, RAG, orquestrador de modelos, embeddings, rerank) — a **infra de IA** (permanece FastAPI).
  - O `business` chama o `ai` **apenas por uma porta `AiPort`** (`qualify(lead)`, `support(query,ctx)`):
    adapter **in-process na V1** → **client HTTP na V2**, mesmo contrato.
  - **Contrato HTTP da IA** definido já (`POST /ai/qualify`, `POST /ai/support`), **stateless** (a IA
    recebe os dados que precisa e devolve o resultado; **não** acessa tabelas de negócio).
  - **Ownership de dados por schema**: `business.*` vs `ai.*`, **sem foreign key cruzada** (referência
    por ID opaco) → split de banco trivial depois.
  - **Correlação e auth transport-agnostic**: `X-Request-Id`/`traceparent` + seam de token/JWT interno,
    propagados por contextvars na V1 e por **header** na V2 (a observabilidade sobrevive ao novo hop).
- **Trade-off:** disciplina extra na V1 (uma porta, um contrato, dois schemas, correlação por header) —
  **zero** container novo agora; em troca, a separação futura é **aditiva e sem quebrar a aplicação**.
  Ver `.claude/plan/plano-execucao.md` (layout) e `.claude/plan/roadmap-v2.md`.

---

## Sistema de agents, isolamento e reescopo (Fase 3+)

### DEC-ORB-022 — AgentConfig parametrizado
- **Escolha:** o comportamento do agente (modelo, provider, temperatura, `k`, `similarity_threshold`,
  `use_rerank`, `rag_mode`, `sufficiency_threshold`, prompts) vem de **config**: V1 em env/hardcoded; V2 no painel admin.
- **Trade-off:** disciplina de config vs. literais espalhados; mesmo seam do corte V1/V2 (DEC-ORB-020).

### DEC-ORB-023 — RAG dual-mode + Context Validation + `ragMode=rag_preferred`
- **Escolha:** **stub** = retrieval por keyword (`ILIKE`) + rerank heurístico (determinístico, CI); **real**
  = pgvector semântico + rerank. Ambos com **Context Validation** (suficiência); `ragMode=rag_preferred`
  (se insuficiente → recusa/handoff, **não alucina**).
- **Trade-off:** dois caminhos de retrieval, em troca de CI sem rede e de não inventar cobertura/preço.

### DEC-ORB-024 — LangGraph com estado explícito + arestas condicionais
- **Escolha:** grafos com estado explícito e arestas condicionais (fallback stub / suficiência / handoff);
  mínimo na V1, extensível a multi-turno sem retrabalho.
- **Trade-off:** mais estrutura que uma chain linear, em troca de testabilidade e evolução.

### DEC-ORB-025 — Worker como processo separado
- **Escolha:** serviço `worker` no compose (mesma imagem, `python -m app.business.worker`). Claim por
  `SELECT ... FOR UPDATE SKIP LOCKED` + backoff persistente (`next_attempt_at`) + dead-letter. Hedge: loop
  callable rodável in-process sob flag (dev/testes).
- **Trade-off:** +1 processo, em troca de **isolamento de runtime** (LLM lento não derruba a captura) e
  congruência com a V2. `SKIP LOCKED` ≠ exactly-once → **handlers idempotentes obrigatórios** (DEC-ORB-014).

### DEC-ORB-026 — Guardrails do agente
- **Escolha:** entrada do usuário e documentos recuperados são **dados não-confiáveis** →
  **prompt-injection scope-and-strip** (responde o legítimo, recusa o off-topic); PII mascarada.
- **Trade-off:** um passo de guardrail por turno, em troca de resistência a injeção e vazamento.

### DEC-ORB-027 — Agente conversacional ÚNICO com tools (não action-agent via handoff)
- **Escolha:** um agente conversacional com **tool-calling** (quote/pdf/kb/crm_update/notify/conversion/
  handoff); **handoff reservado a HUMANO**. O determinismo da cotação vive no `quote_tool(CRM)`. Único split:
  `qualification_agent` (headless, no worker) vs. conversacional (chat), separados por contexto de execução
  e comunicando-se pela **outbox**. Regra: **read-inline** (quote/pdf/kb) vs **write-through-outbox**
  (crm_update/notify/conversion/handoff, só após confirmação explícita).
- **Trade-off:** um agente com mais tools, em troca de menos superfície, sem round-trip de handoff e
  mantendo a IA stateless/extraível.

### DEC-ORB-028 — Handoff V1 = detectar + flag + mensagem + intent (fake)
- **Escolha:** detectar (keyword+intent) + **flag ortogonal ao status** (`Lead.handoff_requested_at`/`reason`) +
  mensagem honesta + `IntentType.HANDOFF` na outbox (handler **fake** via `NotificationPort`); ação real
  (notificar corretor/roteamento) = 1ª task **pós-V1**, trocando fake→real no MESMO seam.
- **Trade-off:** um handler no-op na V1, em troca de exercitar o cano inteiro sem efeito real e sem retrabalho.

### DEC-ORB-029 — Cache de saídas de LLM (seam na V1)
- **Escolha:** `CachePort` + `NullCache` default (no-op, CI determinístico). Só cachear conteúdo
  **genérico/sem-PII/independente de lead** (FAQ do suporte) em `ai.llm_cache` (relacional, chave
  `sha256(scope|model|prompt_version|corpus_version|prompt)`); camada semântica pgvector **pós-V1**.
  **NUNCA** cachear qualificação (determinística) nem cotações (lead-específicas).
- **Trade-off:** +1 seam/tabela, em troca de custo/latência menores no modo real, sem vazar entre leads.

### DEC-ORB-030 — Isolamento & Auth (pré-requisito das Fases 4+)
- **Escolha:** **primitivo de auth** (token opaco server-side → `lead_id`); **desacoplar Idempotency-Key de
  identidade** (correção do **LEAK-1**: dedup não expõe `id/score/band` de outro lead → `{deduped:true}` ou
  409); `X-Request-Id` só de origem confiável (nunca ecoar); **history business-owned** (`chat_sessions`/
  `chat_messages`, `UNIQUE(session_id,seq)`), IA recebe o transcrito montado; **lock por sessão**;
  **masking central de PII** (filtro no logging, inclui placa); artefatos por endpoint autenticado; artefato
  do lead fora do vector store. Inclui **ciclo de vida da sessão + login OTP** (ver `docs/isolamento-leads.md`).
- **Trade-off:** trabalho de auth/isolamento antes do chat, em troca de fechar IDOR/vazamento de PII.

### DEC-ORB-031 — Extensões backward-compatible de portas
- **Escolha:** `CrmPort.upsert_lead(..., stage=None)`, `AdsPort.send_conversion(..., click_id=None)`,
  `IntentType += HANDOFF/NOTIFY`; novos `PdfPort` e `NotificationPort` (fake default / real opt-in).
- **Trade-off:** assinaturas crescem levemente, sem quebrar callers/fakes/testes atuais.

### DEC-ORB-032 — Atribuição por UTM / Click_ID
- **Escolha:** capturar `utm_*`/`click_id` (gclid/fbclid) na LP → persistir no lead → enviar na conversão
  (dedup segue por `event_id`). V1: **serviço fake de UTM no frontend** (4 campanhas: 2 Meta + 2 Google,
  sorteio por submissão). Exige consent de tracking (LGPD).
- **Trade-off:** +colunas e propagação ponta-a-ponta, em troca de fechar a atribuição de conversão.

### DEC-ORB-033 — Roadmap reescopado (V1 chat-first)
- **Escolha:** F3 (background: RAG+qualify+worker) · **F3.5 Hardening/Auth** (pré-F4) · F4 (suporte
  single-turn) · **F5** (conversa de cotação: hero-prompt → chat multi-turn → `quote_tool` → PDF) · **F6**
  (personalização + ações email/WhatsApp/SMS via outbox + Click_ID) · F7 (CI+entrega). Auth completa (RBAC)
  e marketplace multi-seguradora = **V2**.
- **Trade-off:** roadmap maior que o corte vertical original, protegendo o V1 que fecha e empurrando o
  conversacional para V1.5.
