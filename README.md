# SegurAuto

[![CI](https://github.com/dgplsoares/segurauto/actions/workflows/ci.yml/badge.svg)](https://github.com/dgplsoares/segurauto/actions/workflows/ci.yml)

<p align="center">
  <img src="docs/screenshot-segurauto.png" alt="SegurAuto — landing page de captação com consultor de IA" width="840">
</p>

<p align="center">
  🎨 <a href="https://www.figma.com/proto/PYqHA3t5ZoUPHlrnqoF3Na/Untitled?node-id=7-917&t=oo5RD4Y8RH7TQ3Hz-1&scaling=min-zoom&content-scaling=fixed&page-id=0%3A1"><strong>Protótipo interativo no Figma</strong></a>
</p>

Captação de leads para **seguros de automóvel**, **chat-first**: da landing page o lead conversa com um
**consultor de IA** que coleta os dados, gera uma **cotação** e, com a confirmação, dispara as **ações**
(notificação, conversão, sinal ao CRM) ou o **handoff** para um corretor. Em paralelo, cada lead é
**qualificado** por IA e **sincronizado** ao CRM da seguradora + plataformas de anúncios.

> **Fictício / demonstração.** CRM e plataformas de anúncios são **fakes** trocáveis por integrações
> reais via configuração (`.env`), sem alterar o domínio.

## Arquitetura (resumo)

Monorepo com dois serviços e um banco:

```
segurauto/
├── frontend/     # Next.js — Landing Page + widget de chat; route handlers como BFF
├── ai-service/   # FastAPI — dono do ciclo de vida do lead; agentes (LangGraph) + RAG (pgvector)
└── docker-compose.yml   # postgres+pgvector, ai-service, worker, frontend
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

## Fluxo ponta a ponta

1. **LP → captura:** o lead envia o formulário; `POST /leads` persiste + enfileira a qualificação na **outbox** (atômico e idempotente).
2. **Worker (assíncrono):** qualifica por IA (score/faixa) → sincroniza o CRM → dispara conversões (Meta/Google) — idempotente, com retry/dead-letter.
3. **Autenticação:** OTP por e-mail; a sessão só existe **após** a verificação.
4. **Conversa de cotação:** o consultor coleta veículo/CEP/corretor (slot-filling **determinístico**) e gera a **cotação** vinda do CRM (número **fora do LLM**).
5. **Confirmação → ações:** "Quero contratar" dispara notificação (e-mail/WhatsApp/SMS) + conversão + sinal ao CRM; "Falar com corretor" faz o **handoff** — tudo write-through-outbox e idempotente.

## Avaliação: a jornada do lead

Para inspecionar o resultado de ponta a ponta sem vasculhar o banco, a app expõe uma **jornada agregada**
por e-mail — cadastro + conversa + cotação + ações + as trocas reais com CRM/Ads/e-mail. **Só em `local`**
(fail-closed).

```bash
# gera uma jornada COMPLETA de demonstração (captura → qualifica → OTP → cotação → conversa)
docker compose exec ai-service python -m app.eval.seed
```

O comando imprime o e-mail e as URLs:
- Lista de leads recentes: `GET http://localhost:8000/eval/leads`
- Jornada (JSON, p/ máquina/LLM): `GET http://localhost:8000/eval/leads/journey?email=...`
- Jornada (**timeline HTML**): o mesmo endpoint com `&format=html`

## Observabilidade

- `GET /health` (liveness) · `GET /health/ready` (banco + migrations) · `GET /metrics` (Prometheus).
- Logs estruturados com **correlação `request_id`/`lead_id`** que sobrevive à fronteira assíncrona (worker).
- **PII mascarada** nos logs; segredos nunca logados; o código do OTP nunca é persistido.

## Testes

```bash
cd ai-service && pytest            # unit (sem infra) + integração (fakes + LLM stub)
cd frontend && npm run build       # typecheck + build de produção
```

O **CI** (GitHub Actions, `.github/workflows/ci.yml`) roda `ruff` + `pytest` (unit + integração), o build do
frontend e o build das imagens Docker — tudo com **fakes + LLM stub, sem segredos**. Testes contra
provedores reais ficam em `ai-service/tests/real/` e são **opt-in** por `.env`.

## Decisões

O histórico rastreável de decisões de arquitetura (Contexto / Escolha / Trade-off) está em
[`.claude/decisions/DECISIONS.md`](.claude/decisions/DECISIONS.md) — Ports & Adapters, atomicidade por
outbox + worker, idempotência, monólito modular extraível (V2), auth/OTP, conversa de cotação e ações.
O plano por fases e o diário ficam em [`.claude/plan/`](.claude/plan).

## Escopo

**Entregue:** o caminho **chat-first** completo — captura → qualificação por IA → sync CRM/Ads (worker) →
autenticação (OTP) → **conversa de cotação** → **cotação** → **confirmação → ações** (notificação/conversão/
CRM + handoff) + atribuição por **Click_ID**, mais a **jornada do lead** para avaliação. Operado por
env/seed/DB direto (sem painel).
**V2 (futuro):** painel administrativo — CMS da LP, parâmetros de IA, base de conhecimento (upload),
pipeline de leads (Kanban), usuários/permissões e marketplace multi-seguradora
(ver [`.claude/plan/roadmap-v2.md`](.claude/plan/roadmap-v2.md)).
