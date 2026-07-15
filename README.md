# SegurAuto

<p align="center">
  <img src="docs/screenshot-segurauto.png" alt="SegurAuto — landing page de captação com consultor de IA" width="840">
</p>

Captação e qualificação de leads para **seguros de automóvel**. Uma landing page de captação
alimenta um serviço de IA que **qualifica** cada lead e oferece **suporte** conversacional, com
sincronização automática para o CRM da seguradora e eventos de conversão para plataformas de anúncios.

> **Fictício / demonstração.** CRM e plataformas de anúncios são **fakes** trocáveis por integrações
> reais via configuração (`.env`), sem alterar o domínio.

## Arquitetura (resumo)

Monorepo com dois serviços e um banco:

```
segurauto/
├── frontend/     # Next.js — Landing Page + widget de chat; route handlers como BFF
├── ai-service/   # FastAPI — dono do ciclo de vida do lead; agentes (LangGraph) + RAG (pgvector)
└── docker-compose.yml   # postgres+pgvector, ai-service, frontend
```

- **Integrações externas atrás de Ports & Adapters** (CRM, Ads, LLM, Rerank): *fake* por padrão,
  *real* opt-in por `.env`.
- **Fluxo assíncrono resiliente:** o lead é persistido de forma atômica e a resposta é imediata;
  qualificação + sync CRM + eventos de conversão rodam num **worker** que consome uma **outbox**
  (at-least-once, idempotente).
- **Observabilidade** end-to-end (logs estruturados com correlação por lead, `/metrics`).

Detalhes e histórico de decisões em [`.claude/`](.claude): protocolo, decisões (`DECISIONS.md`),
análise e plano de execução.

## Como rodar

```bash
cp .env.example .env      # ajuste flags: USE_FAKE_CRM, USE_FAKE_ADS, LLM_PROVIDER
docker compose up --build
```

- Frontend (LP): http://localhost:3000
- ai-service (API + docs): http://localhost:8000/docs · saúde: `/health`, `/health/ready` · métricas: `/metrics`

### Modo fake (padrão) vs real
- Padrão: `LLM_PROVIDER=stub`, `USE_FAKE_CRM=1`, `USE_FAKE_ADS=1` — roda sem segredos e é o modo do CI.
- Real (opt-in): `LLM_PROVIDER=openai` + `OPENAI_API_KEY=...` (e flags de integração) — **sem mudar código**.

## Testes

```bash
# ai-service
cd ai-service && pytest            # unit (sem infra) + integração (fakes + LLM stub)
# frontend
cd frontend && npm test
```

Testes contra provedores reais ficam em `ai-service/tests/real/` e são **opt-in** por `.env`.

## Escopo

**V1 (este entregável):** núcleo funcional — captura → qualificação por IA → sync CRM/Ads —
operado por variáveis de ambiente, seed e escrita direta no banco.
**V2 (futuro):** painel administrativo para gerenciar conteúdo da LP, parâmetros de IA, base de
conhecimento (upload de documentos), pipeline de leads (Kanban) e usuários/permissões
(ver `.claude/plan/roadmap-v2.md`).
