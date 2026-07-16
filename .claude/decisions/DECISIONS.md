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

---

## Hardening / Auth (Fase 3.5)

### DEC-ORB-034 — RETIRADA
`funnel_status` foi descartado: a aplicação **não é um CRM** e não gerencia o funil de vendas (isso é do
CRM). Mantemos só o `status` de **processamento interno**. Ver `docs/isolamento-leads.md` e o diário.

### DEC-ORB-035 — Correção do LEAK-1 (captura não vaza qualificação de outro lead)
- **Contexto:** verificação adversarial achou que o dedup do `POST /leads` retornava `id`+`score`+`band`
  de outro lead se a `Idempotency-Key` colidisse (a key é client-controlled).
- **Escolha:** `LeadResponse` **não** expõe `score`/`band`; no dedup, compara-se o **e-mail normalizado**:
  dono legítimo (mesmo e-mail) → 200 `{id, status, deduped}`; colisão de key com outra identidade → **409
  neutro** (sem `id`/`status`/`score`/`band`/e-mail). Log de conflito com `sha256` da key (sem PII).
- **Trade-off:** +1 comparação e um 409 que revela apenas "esta key é de outra identidade" (keys são UUID,
  colisão negligível), em troca de eliminar a impersonação.

### DEC-ORB-036 — Endurecimento de observabilidade (correlação ≠ autorização; PII)
- **Escolha:** `X-Request-Id` **só de origem confiável** (assinado pelo BFF via `trusted_proxy_secret`),
  **nunca ecoando** valor do cliente; middleware de correlação vira **pure-ASGI** (sobrevive ao streaming
  do chat da F4); **masking central de PII** seguro (e-mail + CPF formatado + placa maiúscula — **sem**
  regex genérico que corromperia UUID/quebraria a correlação) + `echo=off` explícito na engine.
- **Trade-off:** exige segredo compartilhado BFF↔ai-service (sem ele, correlação cai para server-side,
  seguro por default) e custo de regex por linha; fecha spoofing de correlação e vazamento de PII.

### DEC-ORB-037 — Auth por token + OTP (desenho aprovado; **implementar no início da F4**)
- **Escolha:** sessão = **token opaco server-side** (`secrets`, guardado como `sha256`) → `lead_id`, via
  dependency `require_session` (base do anti-IDOR do chat); **sessão só nasce pós-OTP** (prova de posse do
  inbox — fecha email-squat); **sliding ~30min + TTL absoluto**; **identidade = e-mail verificado, sem
  `UNIQUE(email)`** (permite múltiplos leads/pessoa; tabela `identities` = V2); **OTP 5 dígitos** hasheado
  (HMAC+pepper), **não consumido em tentativa errada** (cooldown/backoff por `email[,IP]`), rate-limit,
  uso único, TTL ~10min; **enumeração aceita + rate-limit** (IP/captcha = V2); `NotificationPort` fake (real pós-V1).
- **Trade-off:** +tabelas e um passo de OTP antes do chat, em troca de auth real desacoplada de campo
  client-controlled. Reconcilia os furos do pentest (workspace/10). **Implementação no início da F4** (junto do chat que a consome).

### DEC-ORB-038 — F5a: persistência de conversa + isolamento + lock + idempotência de turno
- **Contexto:** o chat multi-turn precisa persistir a conversa sem vazar entre leads nem corromper sob
  concorrência (invariantes de `isolamento-leads.md`); a reanálise adversarial da F5a achou 8 furos.
- **Escolha:** tabelas `business.chat_sessions`/`chat_messages` (nada em `ai.*`; o `ai` só ganha
  `AiPort.converse` + `/ai/converse` **stateless**); `lead_id` **NU sem FK** (convenção `outbox`/`auth`);
  FK+CASCADE só **dentro** de `business`; `UNIQUE(session_id, seq)`. Lock por sessão via `SELECT FOR UPDATE`
  que faz **lock + anti-IDOR** num round-trip; **gate de posse compartilhado** (`load_owned_session_or_404`)
  em **toda** leitura (fecha E1: `chat_messages` não tem `lead_id`); alocador de `seq` **auto-curável**
  (`COALESCE(MAX(seq),0)+1` sob o lock — E4); **idempotência de turno** por `client_turn_id`
  `UNIQUE(session_id, client_turn_id)` + replay (E2); `session_id` do path como `str` → **404 neutro** em
  todos os verbos/motivos, nunca 403 (E1-LOW).
- **Trade-off:** +2 tabelas e um token de turno no client, em troca de isolamento e não-duplicação verificados.

### DEC-ORB-039 — F5a: agente multi-turn stateless + slots determinísticos + guardrails
- **Contexto:** input do usuário = dado não-confiável; o pentest mostrou `guard_in` no-op (transcrito
  reinjeta a msg crua) e **slot poisoning** (whitelist só de chave deixa valor virar arg de tool na F5b).
- **Escolha:** `ConverseAgent` LangGraph **stateless** (`RagService` no state; sem checkpointer; nós
  disjuntos das state keys), esqueleto do 4b. **Extração de slots determinística** (regex/regras) + **schema
  de VALOR** por slot antes de persistir/alimentar; `broker_code` **resolvido/autorizado server-side**
  (nunca cru). Transcrito tratado como não-confiável: **sanitizar/delimitar cada linha** na montagem e passar
  `safe_message` como turno corrente (E5). `strip_injection` = **best-effort, nunca fronteira** (E7). Masking
  estendido (CEP/telefone/placa case-insensitive + neutralizar CRLF) + `max_length` na mensagem + **janela de
  transcrito** (E8). **Escopo:** F5a só sinaliza `ready_to_quote`; cotação = F5b (reconcilia DEC-ORB-027).
- **Trade-off:** extração determinística é menos "esperta" com texto bagunçado (pergunta de novo), em troca
  de superfície de injeção fechada e CI-determinística.

### DEC-ORB-040 — F5a: boundary transacional do turno (commit único + timeouts + pool isolado)
- **Contexto:** segurar o `FOR UPDATE` + a conexão do pool durante a chamada do LLM (~46s no pior caso)
  podia **inanir a captura** (`/leads`) — exatamente o acoplamento que a DEC-ORB-025 separou.
- **Escolha:** manter **commit único** no boundary (DEC-ORB-012), mas impor `lock_timeout` +
  `statement_timeout` + cap de transcrito e dar ao chat um **pool de conexões dedicado/limitado**, separado
  de auth/captura. Turno lento falha rápido (429/409) e nunca prende `/leads`. (Alternativa "dois-commits"
  considerada e preterida por complexidade/atomicidade.)
- **Trade-off:** um pool a mais e turnos lentos que falham rápido, em troca de liveness da captura.

### DEC-ORB-041 — `canonical_lead_id` / tabela `identities` antecipada para F5a (refina DEC-ORB-037)
- **Contexto:** o gate anti-IDOR chaveia `lead_id`, mas o token resolvia "lead mais recente por e-mail" (sem
  `UNIQUE(email)`) → sessão órfã na re-auth e a tentação de relaxar o gate para e-mail (reabriria cross-lead).
- **Escolha:** antecipar a tabela `business.identities(email_normalized UNIQUE, canonical_lead_id)` (era V2
  na 037). `verify_otp` resolve o `canonical_lead_id` (upsert) e minta a sessão com ele. O gate segue
  **estrito em `lead_id`** (nunca e-mail), agora **estável por identidade** → continuidade + isolamento.
- **Trade-off:** +1 tabela e um upsert no `verify_otp`, em troca de continuidade de sessão sem afrouxar o gate.

### DEC-ORB-042 — Endpoint de "jornada do lead" para avaliação (agregado, **gated demo-only**)
- **Contexto:** o avaliador precisa inspecionar o resultado do teste de forma **agregada** (cadastro +
  conversa + CRM/Ads/e-mail + cotações) sem encadear várias chamadas nem consultar o banco na mão.
- **Escolha:** `GET /eval/leads/journey?email=` (tag **`eval`** no Swagger) devolve um JSON estruturado com a
  jornada do lead resolvido pela **identidade canônica** (DEC-ORB-041; *fallback*: lead mais recente por
  e-mail): dados cadastrais, **todas as mensagens** das sessões, eventos de `outbox` (intents CRM/Ads/e-mail
  + status) e **cotações** (F5b). **GATED**: habilitado só em `ENVIRONMENT=local` (ou flag `enable_eval_api`),
  **fail-closed** fora disso — senão desfaz o hardening (LEAK-1/anti-IDOR/enumeração). Complementos de baixo
  atrito: `GET /eval/leads` (lista e-mails/identidades recentes p/ **descoberta**) e um **seed de demo** (um
  comando gera uma jornada completa). Opcional `?format=html` (timeline renderizado, zero-fricção; o JSON
  segue disponível para LLM/máquina). **Read-only** e cross-context de leitura — vive num módulo `eval`
  separado, sem lógica de domínio; NÃO é CRM/funil (só uma projeção de leitura para avaliação).
- **Dependência:** para exibir os **payloads reais** de/para CRM/Ads/e-mail (não só os intents), é preciso
  um **audit de integração** — estender o `outbox` com `result`/`response` ou uma tabela append-only
  `integration_events` — introduzido junto das ações da **F6**. Antes disso, a jornada mostra intents+status.
- **Trade-off:** expõe PII agregada, por isso **estritamente demo/local (fail-closed)**; em troca dá ao
  avaliador (e a uma LLM) uma visão única e renderizável da jornada do lead.
- **Implementado:** módulo `app/eval/` (read-only, sem lógica de domínio). `GET /eval/leads/journey?email=`
  **agrega por e-mail** (todas as linhas de lead do e-mail ∪ a âncora canônica) → leads, sessões+mensagens,
  cotações, outbox e `integration_events` (DEC-ORB-044, já com os payloads reais). `GET /eval/leads`
  (descoberta). `?format=html` = timeline cronológica com **escaping anti-XSS** (o conteúdo de chat é input
  livre). Gate `enable_eval_api|environment==local` **no `main` (montagem) + na rota (defesa em
  profundidade)**. Seed `python -m app.eval.seed` dirige o fluxo REAL (captura→worker→OTP→cotação) e gera
  uma jornada completa. 7 testes de integração (agregação, canônica, 404, descoberta, escaping, gate off).

### DEC-ORB-043 — F5b: cotação (`quote_tool`/`pdf_tool`) orquestrada pelo business, número do CRM
- **Contexto:** a conversa multi-turn completa os slots (`ready_to_quote` da F5a); falta gerar a cotação.
- **Escolha:** `quote_tool` **orquestrado pelo business** (não pelo LLM), disparado **automaticamente** quando
  os slots completam. O prêmio vem de `CrmPort.price_quote` (fake determinístico) — **número/decisão fora do
  LLM** (reconcilia DEC-ORB-027, como a extração de slots da F5a.2). `broker_code` é **autorizado server-side
  no CRM fake** (fecha o E6). Cotação persistida em `business.quotes` (prêmio em **centavos**), **escopada à
  sessão** (gate de posse anti-IDOR), **uma por sessão** (re-cota = F6). PDF = **marcador** (`pdf_ref`), sem
  bytes nem endpoint de download. GET `/support/sessions/{id}/quote` autenticado.
- **Trade-off:** cotação automática + PDF só marcador (mais simples/demonstrável no card), deixando a
  confirmação explícita e a geração real de PDF para evoluções.

### DEC-ORB-044 — F5b: `integration_events` (audit que habilita a jornada)
- **Contexto:** o `outbox` guarda intent+status, mas não os **payloads reais** de/para CRM/Ads/e-mail; a
  jornada (DEC-ORB-042) precisa deles.
- **Escolha:** tabela **append-only** `business.integration_events` (`lead_id`/`session_id`/tipo/`request`/
  `response`/`status`/`request_id`/`created_at`). Escrita pelos **callers** (worker: `crm_sync`/`ads_*`;
  `quote_tool`: `crm_price_quote`; OTP: `notify_otp`) logo após o fake — sem acoplar os adapters ao banco.
  Cobre também `price_quote`/OTP (fora do outbox). PII mascarada; o **OTP nunca registra o código**.
- **Trade-off:** +1 tabela e uma escrita por troca, em troca de uma jornada completa e auditável.

### DEC-ORB-045 — F6: confirmação explícita → ações write-through-outbox
- **Contexto:** com a cotação no card (F5b), falta o lado **"write"**: o lead confirma a intenção e a app
  dispara ações externas (conversão, notificação, sinal ao CRM) + handoff, além da atribuição por Click_ID.
- **Escolha:** **confirmação explícita por botão no card** (`POST /support/sessions/{id}/confirm`
  `action=contract|handoff`) — nunca inferida de mensagem ambígua. `contract` enfileira **NOTIFY + CONVERSION
  + CRM_UPDATE**; `handoff` enfileira **HANDOFF**. Tudo **write-through-outbox** (mesmo padrão da fatia
  vertical): o worker roda os fakes at-least-once e grava em `integration_events`. **Idempotência** por uma
  marca na sessão (`contract_requested_at`/`handoff_requested_at`) sob `FOR UPDATE` (lock + anti-IDOR) → 2ª
  confirmação = replay (`already_requested`), **efeito 1×**; a conversão de ação usa `action_event_id`
  (por sessão, distinto do `conversion_event_id` de qualify → não deduplicam entre si). `contract` **exige
  cotação** (409 `quote_required`). **Canais:** email + WhatsApp + SMS (fakes via `NotificationPort.notify`;
  destino nunca logado cru, audit **sem PII** — só canais + ids fake). **Click_ID:** gclid/fbclid capturado
  na URL da LP → **sanitizado** (charset seguro) → `leads.click_id` → enviado na conversão de contrato.
  **Fronteira "não é CRM" (DEC-ORB-034):** `crm_update` é só um **sinal** ao CRM; o funil é do CRM.
- **Escopo:** **núcleo focado** — re-cotação/seleção de coberturas fica para depois (mais perto do
  marketplace = V2). O handoff reusa a flag ortogonal existente + intent na outbox (handler fake).
- **Trade-off:** confirmação por botão (explícita/testável) em vez de NLU; ações fakes idempotentes que
  espelham o contrato real (o adapter real entra por `.env`, sem tocar no domínio).

### DEC-ORB-046 — F8a: provider LLM real (OpenAI + Anthropic) + fallback resiliente
- **Contexto:** habilitar um provider real por `.env` (mantendo o stub como default/CI) e decidir o
  comportamento quando o real falha (incidente ou saldo de tokens esgotado).
- **Escolha:** `get_llm()` vira factory de **3 vias** (`stub | openai | anthropic`), modelo por ENV
  (`ANTHROPIC_MODEL` default `claude-opus-4-8`; recomenda-se `claude-haiku-4-5` p/ custo). Os adapters
  (SDK **lazy**, opt-in no `requirements`) normalizam falhas em **`LLMError(retryable, reason)`**; o
  `ModelOrchestrator` **classifica**: `401`/`insufficient_quota`/billing = **não-retryable → abre o
  circuit-breaker e NÃO retenta** (retry só queimaria tempo/saldo); `429`/`5xx`/`timeout` retentam com
  backoff e **degradam** ao esgotar. **Circuit-breaker por provider** (protege latência **e** saldo numa
  incidência) + métricas `llm_error_total{reason}` / `llm_fallback_total{agent}`. A degradação é o
  **comportamento DETERMINÍSTICO já existente** (cotação/handoff seguem funcionando) — **nunca** o eco do
  stub (`"[stub] ..."` vazaria), **nunca** erro cru. Os 2 checks literais `"openai"` viraram `!= "stub"`
  (Anthropic passa a dirigir converse + qualification).
- **Trade-off:** confirmação de que a degradação determinística > fallback-para-stub/erro-cru; +2 SDKs no
  requirements (opt-in) e um breaker/classificador, em troca de resiliência real a incidente/saldo zerado.

### DEC-ORB-047 — F8e: e-mail real via adapter SMTP genérico (independente de provider)
- **Contexto:** o homolog "funciona como prod" precisa **entregar o OTP** no inbox do avaliador (habilita o
  fluxo de chat completo, não só o seed bypass) e ter o canal de e-mail pronto para os disparos do outbox
  (V2). Restrição do usuário: o provider de e-mail é **infra trocável — a app NÃO pode depender dele**.
- **Escolha:** um **adapter SMTP genérico** (`SmtpNotification`, `aiosmtplib` async, **import lazy**) atrás
  do `NotificationPort` existente; `get_notification()` ramifica em `use_fake_notifications` (default `True`
  → fake/dev-echo em local/CI; homolog seta `0`). **SMTP e não a REST API do fornecedor de propósito**: SMTP
  é o denominador comum (todo provider fala) → trocar de fornecedor = mudar `.env`, **zero código**. Efeito
  duplo: repo **neutro** (nenhum fornecedor citado — só valores em `.env`/Secrets) **e** provider-agnóstico.
  Config em `.env`: `SMTP_HOST/PORT/SSL/USER/PASSWORD`, `MAIL_FROM`, `MAIL_BCC`. **Semântica de falha
  deliberada:** `send_otp` **engole** falha de entrega (loga ERROR) → preserva o **202 neutro** do
  `request_otp` (não vaza existência de e-mail, não dá 500); `notify(channel="email")` **levanta** → a
  outbox **retenta** (at-least-once); `notify(whatsapp|sms)` = **no-op fake** (pronto p/ V2). Templates HTML
  inline (branding SegurAuto neutro), cabeçalhos **saneados** (sem CRLF do destinatário → anti header-inject).
- **Trade-off:** +1 dep runtime (`aiosmtplib`, lazy) e um adapter, em troca de OTP real no homolog + canal de
  e-mail pronto para o outbox — **sem** acoplar o domínio a nenhum fornecedor (troca por `.env`). A verificação
  de domínio (DKIM/SPF) do remetente é **operacional** (fora do repo); o código roda no fake sem ela.

### DEC-ORB-048 — v1.6: persistência de sessão + UI refletindo auth
- **Contexto:** o token de sessão vivia só em memória (React state) → perdido em hard reload / fechar a aba.
  A UI (header, links) não refletia o estado de autenticação.
- **Escolha:** token persistido em **`localStorage`** (não `sessionStorage` — precisa sobreviver ao fechar/
  reabrir a aba). Rehidratado no **mount** (SSR-safe, não no initializer → sem mismatch de hidratação),
  **validado** contra `GET /auth/session` (novo endpoint) antes de mostrar a UI autenticada; teto **absoluto
  de 12h** checado no cliente; **clear-on-401** + **logout** que revoga no servidor (`/auth/logout`).
  `validateSession` é **3-estados** (`valid|invalid|unknown`): um 5xx/blip de rede (ex.: ai-service
  reiniciando num deploy) **NÃO** apaga o token — só um **401 definitivo**. UI: header **Entrar↔Sair**;
  links **"Já tem cadastro? Entre"↔"Abrir a conversa"** (resume puro, sem novo prompt) nas **2** seções de
  prompt; `authReady` evita o flash de rótulo; o `ChatPanel` reseta a sessão local ao perder o token.
- **Trade-off:** `localStorage` é exfiltrável por XSS (mitigado: token curto/30min-idle/12h-absoluto,
  revogável server-side, clear-on-401, logout real). Cookie `httpOnly` seria mais seguro mas exigiria
  reformar o BFF (setar/ler cookie + anexar bearer) + CSRF — desproporcional para o V1.

### DEC-ORB-049 — CI/CD: dev local → `main` → prod remoto (deploy automático)
- **Contexto:** automatizar o deploy. O subdomínio público **é produção** (sem homolog separado; conteúdo
  fictício → não indexado).
- **Escolha:** `deploy.yml` disparado por **`workflow_run`** após o workflow **`CI`** concluir com sucesso num
  push na **`main`** → **só commit verde deploya**, cobrindo merge de PR **e** push direto. **Runner
  self-hosted** no servidor (precisa do daemon Docker local: build + `up` + `network connect`; conexão só de
  saída, não expõe SSH), **isolado** do runner do vizinho (repo/conta/usuário/serviço/dir distintos). `.env`
  do servidor gerado de **UM secret `ENV_FILE`** (Environment `production`, escrito 600) — `POSTGRES_PASSWORD`
  e `AUTH_PEPPER` são **estáveis** (o CI **nunca** regenera; o volume do banco depende deles; guard fail-fast
  no workflow). Nome do container do gateway via **variable** (repo neutro). `name: segurauto` fixa o projeto
  (deploy manual e via runner atingem o **mesmo** stack). Frontend de produção = **`node:20-slim`** (glibc):
  alpine/musl quebra o binário SWC do `next build`.
- **Trade-off:** um agente persistente no servidor (usuário no grupo docker ≈ root), mitigado por o deploy
  disparar **só** em push na `main` (nunca em PR) + CI gated. Build na box compartilhada (carga) em troca de
  simplicidade (sem registry).
