# Fase 8 (intermediária V1 ↔ V2) — Provider LLM real + Produção

> Fase entre o entregável V1.5 e o painel V2. Fecha o `.env`-driven provider real, poli o repo para um
> avaliador clonar do zero, remove o último cross-import `ai→business` e sobe o app em produção atrás de um
> reverse proxy compartilhado. **O runbook operacional específico do servidor NÃO vive neste repositório**
> (neutralidade): fica fora do versionamento; aqui só a arquitetura e o que muda no código do SegurAuto.

## Decisões (aprovadas)

- **Providers:** habilitar **OpenAI e Anthropic** por `.env`, mantendo o **stub** sempre disponível (default/CI).
- **Fallback do provider real:** **degradação determinística + observabilidade + circuit-breaker** — NÃO cair
  no stub (vaza `"[stub]"`), NÃO erro cru. O funil segue (cotação/handoff são determinísticos).
- **Acesso do avaliador no deploy público:** **seed + eval API protegida** (dados são fakes), sem infra de
  e-mail; o fluxo de chat completo com OTP real fica para depois.
- **Sequência:** 8a (LLM) → 8b (README) → 8c (refactor) → 8d (deploy).

---

## 8a — Provider LLM real (OpenAI + Anthropic) + fallback resiliente

**Estado atual:** o seam já é limpo — `LLMPort.complete(system, user) → str`; `StubLLM` (determinístico) e
`OpenAILLM` (já real). `get_llm()` despacha por `llm_provider`. O `ModelOrchestrator` já faz timeout + retry +
backoff e, na falha, retorna `None` → cada agente cai num **fallback determinístico** (não no stub). Os SDKs
são import lazy (não estão no `requirements.txt`).

**Tarefas:**
1. **`AnthropicLLM`** em `ai/providers/llm.py` (espelha `OpenAILLM`; SDK `anthropic`, `messages.create` com
   `system=` + `[{user}]`). `get_llm()` vira factory `stub | openai | anthropic`.
2. **Config:** `anthropic_api_key`, comentário `llm_provider = stub|openai|anthropic`, `masked_anthropic_key`;
   **default de modelo por provider** (o `AgentConfig.model="gpt-4o-mini"` é OpenAI-específico — cada provider
   com o seu default, ex. um modelo econômico da Anthropic).
3. **Generalizar os 2 checks literais `"openai"`** (`ai/agents/config.py` `use_llm_assess` e
   `ai/agents/converse_agent.py` guard do `respond`): trocar por `!= "stub"` (ou um flag `real_provider`) —
   senão `anthropic` cai mudo no determinístico.
4. **Fallback resiliente** (no `ModelOrchestrator`, único ponto de resiliência):
   - **Classificar o erro:** `insufficient_quota`/401/403 (billing/config → **não** retenta, alerta) vs 429
     (retenta com backoff) vs 5xx/timeout (retenta → degrada). O retry atual retenta tudo — refinar.
   - **Circuit-breaker leve:** após N falhas consecutivas, abre por um cooldown → serve determinístico direto
     (protege latência **e saldo de tokens** numa incidência/saldo zerado); half-open após o cooldown.
   - **Observabilidade:** métrica `llm_error_total{reason}` + `llm_fallback_total` + log estruturado.
   - **Comportamento por agente na degradação (mantém o atual):** converse → `_fallback_reply` (pergunta o
     próximo slot / confirma a cotação — número é determinístico); support → mensagem honesta + handoff;
     qualification → razão da rubrica. **Nunca** o `StubLLM` em runtime de usuário.
5. **`requirements.txt`:** += `anthropic` (e fixar `openai`, hoje out-of-band).
6. **`.env.example`:** `ANTHROPIC_API_KEY=` + documentar `LLM_PROVIDER=anthropic`.

**Verificar:** unit (factory despacha os 3; classificação de erro; breaker abre/fecha) sem rede; o CI segue
no **stub** (sem segredos); testes reais opt-in por `.env` (`tests/real/` — hoje inexistente, criar). Smoke
manual com uma chave real (OpenAI e Anthropic) — cotação e suporte com frase real; simular 401/quota → degrada.

## 8b — README from-scratch (avaliador clona e roda)

Endereçar os gaps (referência de qualidade: um README que separa pré-requisitos por caminho, mostra o
primeiro boot com saída esperada e antecipa surpresas):
1. **Corrigir o claim falso** de `ai-service/tests/real/` (não existe hoje) — criar o diretório na 8a ou ajustar o texto.
2. **Pré-requisitos explícitos:** Docker + Docker Compose v2 (caminho padrão); Python 3.11 / Node 20 (só p/ rodar local/testes).
3. **Primeiro boot + saída esperada:** o `worker` **reinicia até o ai-service migrar** (por design) — dizer que é normal; "saudável quando `/health/ready` OK e a LP carrega".
4. **OTP em local:** o código só é ecoado em `ENVIRONMENT=local` como `otp_dev_echo` nos logs →
   `docker compose logs -f ai-service | grep otp_dev_echo` (e o `seed` bypassa o OTP).
5. **Receita de testes reproduzível:** `pip install -r requirements-dev.txt` + Postgres migrado (ou "rode como o CI"); avisar que sem DB a integração é *skipped*, não *failed*.
6. **Troubleshooting/portas:** citar as 3 portas publicadas **incl. 5432** (conflito com Postgres local); `.env` é opcional (compose tem defaults).
7. **Tabela de `.env`** cobrindo todas as vars, com destaque para o acoplamento do **`ENVIRONMENT`** (gate da eval API + OTP dev-echo + fallback do pepper).

## 8c — `QualificationResult` → `shared/` (refino DEC-ORB-021)

Mover o dataclass `QualificationResult`/`QualificationBand` de `ai/` para `app/shared/` para eliminar o
**último cross-import `ai→business`** (o domínio `business` importa o tipo de resultado que hoje vive em `ai`).
Refactor mecânico: mover o módulo, reapontar imports em `ai/` e `business/`, rodar `ruff` + suíte completa.
Verificar novamente que **cross-import business↔ai = 0** (a invariante do DEC-ORB-021).

## 8d — Deploy (HOMOLOG remoto que funciona como prod, co-hosting seguro, isolado)

> O alvo `app-segurauto.diogosoares.com.br` é um **homolog** — funciona como prod, mas **não é indexado** por
> buscadores (`ALLOW_INDEXING=false` → `noindex` + `robots.txt disallow`). Na prod real, ligar `ALLOW_INDEXING=true`.

**Arquitetura (neutra):** o servidor de destino já expõe a web atrás de um **reverse proxy compartilhado**
que roteia por host/path e termina TLS no **edge (Cloudflare)**, falando HTTP com a origem. O SegurAuto entra
como um **stack isolado**:
- **Compose próprio** (`db` Postgres próprio + `ai-service` + `worker` + `frontend`) numa **rede Docker
  própria**; **zero portas publicadas no host** (evita conflitos e reduz superfície).
- **Um único ponto de integração:** o proxy compartilhado ganha um `server_name` novo
  (**`app-segurauto.diogosoares.com.br`**) → `frontend` interno na raiz; nada do que já roda no servidor é alterado.
- **Subdomínio dedicado ⇒ sem `basePath`** no Next.js (serve na `/`); a BFF fala com o `ai-service` pela rede interna.
- **Postura de produção:** `ENVIRONMENT=production` (eval API + OTP dev-echo OFF por padrão), `auth_pepper`
  real, provider LLM real por `.env`. Para a **avaliação**: `ENABLE_EVAL_API=true` (dados fakes) + a rota
  a rota `/eval/*` (em `app-segurauto.diogosoares.com.br`) protegida por basic-auth no proxy; o avaliador usa o **seed** (bypassa OTP) + as URLs
  da jornada.
- **CI/CD:** um workflow de deploy dedicado (o CI atual continua sendo o gate de PR). Rollback em falha.

**Detalhes operacionais do servidor** (SSH, caminhos, config do proxy, alocação de portas, DNS/Cloudflare,
permissões) ficam **no runbook local, fora deste repositório**.

**Decisão de infra:** **IP dedicado não é necessário** — o roteamento por host/path no proxy compartilhado
serve múltiplos domínios no mesmo IP/443.

**Verificar:** stack isolado sobe sem tocar o que já roda; `https://app-segurauto.diogosoares.com.br`
carrega a LP; jornada acessível (protegida); nenhuma porta nova publicada no host; smoke do fluxo completo.

---

## Sequenciamento e docs

8a → 8b → 8c → **8d por último** (precisa dos anteriores estáveis + DNS/permissões). Cada sub-fase fecha com
`ruff` + suíte + (frontend) `next build` e, quando aplicável, smoke; revisão adversarial nos pontos de risco
(fallback do LLM; isolamento do deploy). Decisões formais viram DEC-ORB-046+ ao implementar.
