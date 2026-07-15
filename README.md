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

## Pré-requisitos

Você só precisa do que o caminho escolhido exige:
- **Rodar tudo (recomendado):** **Docker** + **Docker Compose v2**. Nada mais.
- **Rodar serviços/testes localmente:** **Python 3.11** (ai-service) e **Node 20** (frontend).

## Como rodar (clone do zero)

```bash
git clone https://github.com/dgplsoares/segurauto.git && cd segurauto
cp .env.example .env      # opcional — o compose tem defaults; o modo fake roda sem editar nada
docker compose up --build
```

- Frontend (LP): http://localhost:3000
- ai-service (API + docs): http://localhost:8000/docs · saúde: `/health`, `/health/ready` · métricas: `/metrics`

**No primeiro boot** o ai-service roda as migrations (`alembic upgrade head`) antes de servir; o `worker`
**reinicia até isso terminar** (por design) — vê-lo reiniciando nos logs é normal, não é falha. Está
**saudável** quando `GET /health/ready` responde `{"db":true}` e a LP carrega em `:3000`.

### Modo fake (padrão) vs real
- **Padrão** (sem segredos, é o modo do CI): `LLM_PROVIDER=stub`, `USE_FAKE_CRM=1`, `USE_FAKE_ADS=1`.
- **LLM real** (opt-in, **sem mudar código**): `LLM_PROVIDER=openai` + `OPENAI_API_KEY=…` **ou**
  `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY=…`. Se o provider real falhar (incidente ou saldo esgotado),
  a app **degrada para o comportamento determinístico** (a cotação/handoff seguem funcionando) — não quebra.

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

> A jornada só existe com **`ENVIRONMENT=local`** (o default) — rode o comando **após** a stack subir e
> migrar. Para autenticar **manualmente** pela LP (fora do seed), o código do **OTP** é ecoado só em `local`
> nos logs: `docker compose logs -f ai-service | grep otp_dev_echo`. O `seed` acima bypassa o OTP.

## Observabilidade

- `GET /health` (liveness) · `GET /health/ready` (banco + migrations) · `GET /metrics` (Prometheus).
- Logs estruturados com **correlação `request_id`/`lead_id`** que sobrevive à fronteira assíncrona (worker).
- **PII mascarada** nos logs; segredos nunca logados; o código do OTP nunca é persistido.

## Testes

Do jeito reprodutível (o mesmo do CI — a integração precisa de um Postgres migrado):

```bash
cd ai-service
pip install -r requirements.txt -r requirements-dev.txt   # Python 3.11
alembic upgrade head                                        # cria o schema no DATABASE_URL
pytest tests/unit tests/integration -q                      # unit (sem infra) + integração (fakes + stub)
cd ../frontend && npm ci && npm run build                   # Node 20 — typecheck + build
```

Sem um Postgres em `DATABASE_URL`, a suíte de **integração é pulada** (não falha) — não confunda com "verde".
Alternativa com a stack de pé: `docker compose exec ai-service pytest tests/unit tests/integration -q`. O
**CI** (`.github/workflows/ci.yml`) roda exatamente isso + o build das imagens Docker — tudo com **fakes +
stub, sem segredos**. Testes contra provedores **reais** ficam em
[`ai-service/tests/real/`](ai-service/tests/real) e são **opt-in** (pulados sem `LLM_PROVIDER` real + a chave).

## Variáveis de ambiente

Todas estão em [`.env.example`](.env.example) com defaults sensatos (o compose usa `${VAR:-default}`, então o
`.env` é **opcional** — mas então tudo assume o default, inclusive `ENVIRONMENT=local`). As principais:

| Variável | Default | Papel |
|---|---|---|
| `ENVIRONMENT` | `local` | **Chave de tudo:** `local` monta a **eval API** da jornada, ecoa o **OTP** nos logs e usa um `auth_pepper` de dev. Trocar para `production` desliga os três. |
| `LLM_PROVIDER` | `stub` | `stub` (default/CI) · `openai` · `anthropic`. |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | — | Chave do provider real (opt-in). |
| `ANTHROPIC_MODEL` | `claude-opus-4-8` | Modelo Anthropic — use `claude-haiku-4-5` p/ baratear a conversa. |
| `USE_FAKE_CRM` / `USE_FAKE_ADS` | `1` | Fakes de CRM/Ads (default). |
| `ENABLE_EVAL_API` | `false` | Liga a jornada **fora** de `local` (deploy público, com a rota protegida) — os dados são fakes. |
| `POSTGRES_*`, `DATABASE_URL`, `AI_SERVICE_URL`, `LOG_LEVEL` | ver `.env.example` | Banco, ligação BFF→ai-service, log. |

> ⚠️ `ENVIRONMENT` acopla a **jornada de avaliação**, o **echo do OTP** e o **pepper** — é o jeito mais fácil
> de "sumir" com o fluxo de avaliação. Mantenha **`local`** para avaliar.

## Troubleshooting

- **Porta em uso.** O compose publica **3000** (LP), **8000** (API) e **5432** (Postgres) no host. Um Postgres
  local já ocupando a **5432** impede o `db` de subir — pare-o ou remapeie a porta no `docker-compose.yml`.
- **`worker` reiniciando no boot** — normal até o ai-service migrar (ver "Como rodar").
- **OTP inválido** — o código muda a cada envio; pegue o atual com
  `docker compose logs -f ai-service | grep otp_dev_echo` (só em `local`), ou use o `seed` (bypassa o OTP).
- **`pytest` "passa" com a integração pulada** — falta o Postgres migrado em `DATABASE_URL`; rode como no CI.

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
