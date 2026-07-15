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
