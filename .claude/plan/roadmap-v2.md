# Roadmap V2 — Painel Admin de gestão

> Escopo entregue **apenas na V2**. A V1 implementa cada capacidade por **env vars / hardcoded /
> escrita direta no banco**; a V2 troca isso por uma **interface de gestão**. Princípio: a V1 já
> expõe os **seams** para que a V2 seja **aditiva** (UI + CRUD + auth sobre serviços que já existem),
> não um redesenho.

## Fronteira V1 → V2

| Capacidade | V1 (agora) | V2 (painel admin) | Seam pronto na V1 |
|---|---|---|---|
| Conteúdo/estrutura da LP | Hardcoded | CMS visual (seções/textos/mídia/CTA/ordem) | LP lê de um **content provider** (estático → tabela) |
| Escolha de modelos (IA) | `.env` | Seletor de modelo/params por tarefa | `ModelOrchestrator` lê de `config` (env → tabela) |
| Prompts / rubrica / thresholds | Hardcoded/`.env` | Editor na UI | Params via `config`, não literais |
| Base de conhecimento (RAG) | Vetorização escrita **direto no banco** (script) | **Upload** de docs → ingestão → gestão | `IngestionService` isolado (seed → endpoint) |
| Pipeline de leads | Persistidos + **sync automático** com CRM | **Kanban + Lista**, mover estágios, re-sync | `lead.status` já modela os estágios |
| Usuários e permissões | Fora de escopo | Auth + **RBAC** | Endpoints sob namespace `/admin` |
| Integrações (CRM/Ads) | `.env` | Telas de configuração e chaves | Já atrás de Ports & Adapters |
| Observabilidade | `/metrics` + logs | Dashboards (leads/conversões/custo de LLM) | Métricas já expostas |

## Módulos da V2

1. **CMS da Landing Page** — seções, blocos, mídia, CTAs, SEO.
2. **Configuração do fluxo de IA** — modelos por tarefa, prompts, rubrica, thresholds, params do RAG.
3. **Gestão da base de conhecimento** — upload de documentos, ingestão (chunk → embedding → pgvector),
   listagem/remoção/re-indexação, status de vetorização.
4. **Pipeline de leads (Kanban + Lista)** — estágios drag-and-drop, filtros/busca, detalhe + histórico +
   score, re-sincronização manual com o CRM.
5. **Usuários e permissões (RBAC)** — cadastro, papéis, escopos.
6. **Integrações** — configurar CRM/Ads (fake↔real), chaves, testar conexão.
7. **Dashboards** — leads, conversões e custo de LLM sobre as métricas da V1.
8. **Guardrails de prompt** — classificador de escopo do input `in | out | mix` (análise abaixo).

## Guardrails de prompt — classificador `in | out | mix` (migrado do fecho da V1)

Análise a executar na V2 (registrada originalmente no fecho da V1). Comparar a estratégia de **serviço de
contexto** usada em **outros projetos de IA** — que **qualifica a mensagem do usuário** como `in` (no tema),
`out` (fora do tema) ou `mix` (misto) **antes/ao redor** da chamada ao LLM, como **guardrail contra prompt
injection** e desvio de escopo — com os guardrails que a V1 já tem, e decidir se vale trazer:

- **O que a V1 já protege (saída/estrutura):** o **número da cotação é determinístico** (nunca sai do LLM);
  funil e handoff determinísticos; **degradação determinística** no fallback (nunca eco de stub/erro cru —
  DEC-ORB-046); input **capado**; escopo no **system prompt**; PII mascarada; a IA **não decide**
  contratar/handoff (confirmação explícita — DEC-ORB-045).
- **O delta do classificador `in|out|mix` (entrada):** camada de classificação de escopo/intenção do input
  (pré-LLM) que barra/neutraliza injeção e off-topic **antes** do prompt principal — complementar
  (defense-in-depth), não redundante com os guardrails de saída atuais.
- **Decidir:** adotar — e **como** (regras/embeddings? um LLM barato tipo `claude-haiku-4-5`? híbrido?) —
  **ou** não, se o funil determinístico + escopo do system prompt já cobrem o risco. Registrar como DEC-ORB-04x.

## Onde vive o admin (decisão da V2)
- **Recomendado:** rotas `/admin/*` no mesmo app Next.js (reuso de build/deploy) + endpoints
  `POST/GET /admin/*` no ai-service, atrás de auth.
- Alternativa: app frontend separado.

## O que a V1 faz agora para não pagar retrabalho
- Params por `core/config` (nunca literais espalhados).
- LP consome um **content provider** (estático na V1).
- **`IngestionService`** isolado — o upload da V2 chama a **mesma** função do seed da V1.
- **`lead.status`** modela os estágios do funil desde a V1.
- Namespace **`/admin`** reservado (vazio na V1).
