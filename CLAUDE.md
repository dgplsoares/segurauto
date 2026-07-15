# CLAUDE.md — SegurAuto

> Documento operacional lido a cada sessão. O "o que construir" está em `.claude/docs/analise-orbitus.md`
> e `.claude/plan/plano-execucao.md`. O "como trabalhar" está em `.claude/protocols/dev-protocol.md`.

## Projeto

Landing page de **captação de leads** para seguros de automóvel + **serviço de IA** que qualifica
os leads e dá suporte conversacional, com sincronização para um CRM (fake) e eventos de conversão
para plataformas de anúncios (fakes). Time-box de entrega curto: **correção e clareza antes de completude**.

## Stack

- **frontend/** — Next.js (TypeScript). Landing Page + widget de chat. Route handlers (`/api/*`)
  atuam como **BFF/proxy fino** para o `ai-service`.
- **ai-service/** — Python 3.11, FastAPI, SQLAlchemy async (asyncpg), LangChain + **LangGraph**
  (agentes de qualificação e suporte), pgvector (RAG). Camadas: `api → services → agents → providers/repositories/core`.
- **Banco** — PostgreSQL + pgvector (leads relacionais + embeddings do RAG).
- **Infra** — Docker Compose; CI em GitHub Actions.

## Estrutura

```
frontend/     Landing Page (Next.js) + BFF (route handlers)
ai-service/   FastAPI — monólito modular extraível (DEC-ORB-021):
  app/shared/     config · database · observabilidade (correlação, auth-seam)
  app/business/   leads · api (/leads) · service · repository (+ outbox) · worker · adapters (CRM/Ads) · ai_port.py
  app/ai/         api (/ai/qualify, /ai/support) · agents (LangGraph) · rag · providers (orchestrator/LLM/rerank)
.claude/      protocolo, decisões (DECISIONS.md), análise e planos
docker-compose.yml   postgres+pgvector + ai-service + frontend
```

## Princípios de arquitetura (invariantes)

1. **Domínio desacoplado da infra** — ports (`Protocol`/ABC) com adapters *fake* (default) e *real*
   (opt-in por `.env`). O domínio depende da interface, nunca da implementação concreta.
2. **Atomicidade + assincronismo** — o endpoint é o boundary de transação (o domínio não commita);
   o lead é persistido junto com uma **outbox** na mesma transação, e um **worker** processa
   qualificação/CRM/Ads fora do request (at-least-once, **idempotente**).
3. **Idempotência** — submissão de lead com `Idempotency-Key` (UNIQUE); efeitos externos com
   `event_id`/upsert e re-checagem de estado terminal.
4. **Observabilidade** — logs estruturados com **correlação `request_id`/`lead_id`** que sobrevive à
   fronteira assíncrona (ids gravados na outbox); `/health`, `/health/ready`, `/metrics`. **PII mascarada**.
5. **Guiado por testes** — unit (domínio sem infra) + integração (fakes + LLM stub, gate de CI);
   testes reais opt-in por `.env`.
6. **Preparado para extração (V2)** — `ai-service` é um **monólito modular extraível**: contextos
   `business/` (negócio) e `ai/` (IA) com **`AiPort`** entre eles (in-process → HTTP), contrato `/ai/*`
   stateless e schemas `business.*`/`ai.*` **sem FK cruzada**. Ver DEC-ORB-021 e `.claude/plan/roadmap-v2.md`.

## Como rodar

```bash
cp .env.example .env && docker compose up --build
```
Ver `README.md` para portas e modo fake vs real.

## Convenções

- **Nada de referências a outros projetos/empresas** neste repositório. Descreva padrões de forma neutra.
- Commits pequenos ao fim de cada fase/bloco, incluindo os docs de processo (`.claude/`). Mensagens
  semânticas (`feat(fase-2): POST /leads persiste + enfileira outbox`). Nada destrutivo sem aprovação.
- Params (modelos, prompts, thresholds, flags) sempre via `core/config` — **nunca literais espalhados**
  (prepara a V2, ver `.claude/plan/roadmap-v2.md`).

## Memória (Engram)

Sempre com `project="orbitus"` explícito em `mem_save`/`mem_search`/`mem_context`. Salvar decisões,
bugs com causa raiz, descobertas e convenções de forma proativa.

## Escopo V1 vs V2

- **V1 (agora):** captura → qualificação IA → sync CRM/Ads, operado por env/seed/DB direto.
- **V2 (futuro):** painel admin (CMS da LP, config de IA, upload de RAG, Kanban de leads, RBAC).
  A V1 mantém os *seams* para a V2 ser aditiva. Ver `.claude/plan/roadmap-v2.md`.
