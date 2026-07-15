# Análise — SegurAuto

> Passo 1 do protocolo (ANÁLISE). O que construir, para quem, com quais restrições e critérios de aceite.

## Problema e objetivo

Uma seguradora de automóveis precisa **captar** e **qualificar** leads com eficiência. Entregamos:

1. **Landing Page** de captação (formulário + suporte por chat).
2. **Agente de IA de suporte** — responde dúvidas do visitante (RAG sobre a base de conhecimento).
3. **Agente de IA de qualificação** — pontua e classifica cada lead (score + faixa + motivo).
4. **Sincronização automática** do lead para o CRM da seguradora e **eventos de conversão** para
   plataformas de anúncios.

## Escopo (V1)

**Dentro:**
- LP responsiva com formulário de lead e widget de chat de suporte.
- API de captura que **persiste** o lead de forma atômica e idempotente.
- Enriquecimento **assíncrono** via worker: qualificação (IA) → sync CRM (fake) → eventos de conversão (fakes).
- RAG sobre uma base de conhecimento SegurAuto (seed de documentos vetorizados em pgvector).
- Integrações **fake** (CRM, Ads, opcionalmente LLM stub) trocáveis por reais via `.env`.
- Observabilidade (logs estruturados correlacionados, `/metrics`, `/health`) e resiliência (outbox,
  retry/backoff, dead-letter, migrations).
- Docker Compose + CI (GitHub Actions).

**Fora (V2 — ver `.claude/plan/roadmap-v2.md`):**
- Painel administrativo: CMS da LP, configuração de IA por interface, upload/gestão de RAG, pipeline de
  leads em Kanban/lista, usuários e permissões (RBAC), dashboards.
- Na V1, tudo isso é operado por **env vars / hardcoded / seed / escrita direta no banco**.

## Restrições

- **Time-box curto** — correção e clareza antes de completude; fatia vertical antes de largura.
- **Sem segredos no CI** — o gate roda com fakes + LLM stub; provedores reais são opt-in local.
- **Domínio testável sem infra** — ports com fakes; o núcleo não depende de rede.
- **LGPD/PII** — dados pessoais do lead nunca em log claro.
- **Repositório neutro** — sem referências a outros projetos/empresas.

## Fluxo-alvo (fatia vertical)

```
LP form → /api/lead (BFF Next.js) → POST /leads (FastAPI)
  → [tx atômica] LeadRepository.persist(lead) + outbox{qualify, crm_sync, ads_meta, ads_google} → 201
Worker (async) consome outbox:
  → qualification_agent (RAG + orchestrator) grava score
  → CrmPort.upsert(lead)      (idempotente)
  → AdsPort.send_conversion   (event_id estável, dedup Meta+Google)
```

## Critérios de aceite (por capacidade)

- **Captura idempotente:** dois POST com a mesma `Idempotency-Key` → **1 lead**.
- **Atomicidade:** ou o lead **e** as intents da outbox são gravados, ou nada (mesma transação).
- **Assincronismo:** o POST responde sem esperar LLM/CRM/Ads; o worker processa depois.
- **Idempotência de efeitos:** rodar o worker 2x → efeitos externos aplicados **1x** (asserts nos fakes).
- **Qualificação:** retorna `QualificationResult` estruturado e determinístico com LLM stub; o RAG recupera do seed.
- **Suporte:** `POST /support/chat` responde com base no RAG.
- **Observabilidade:** `grep lead_id=X` mostra o rastro completo (form→API→outbox→worker→IA→CRM→Ads).
- **Resiliência:** com uma dependência externa fora do ar, o lead **não se perde** (fica na outbox e é retentado).
- **CI verde** (mock, sem segredos) e `docker compose up --build` do zero funcionando.

## Requisitos não-funcionais essenciais

- Idempotência, atomicidade (commit-boundary + outbox), assincronismo (worker at-least-once).
- Observabilidade end-to-end em 5 planos (HTTP, lead, worker/outbox, IA/RAG, integrações) com correlação
  que sobrevive à fronteira assíncrona.
- Resiliência: volume+healthcheck+depends_on, alembic, timeout/retry/backoff, dead-letter.
- Segurança: validação de payload, rate-limit, e guardrail de prompt-injection no agente de suporte
  (superfície a aprofundar).
