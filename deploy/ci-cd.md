# CI/CD — deploy automatizado de produção

O subdomínio público **é o ambiente de produção** (não há homolog separado). Modelo: **dev local → `main` →
deploy automático no remoto**. Toda atualização da `main` (merge de PR ou push direto) que passa no CI é
deployada — sem branch intermediária (evita burocracia).

- [`ci.yml`](../.github/workflows/ci.yml) — **gate** (3 jobs sem segredo) em push/PR na `main`.
- [`deploy.yml`](../.github/workflows/deploy.yml) — **CD**: dispara via `workflow_run` **após o CI passar** num
  push na `main` (só commit verde deploya) e sobe o stack no servidor.

## Mecanismo: self-hosted runner no servidor
O deploy precisa do **daemon Docker local** (build local sem registry + `docker network connect` no proxy
compartilhado) → roda num **runner self-hosted** no servidor (conexão só de saída, não expõe SSH). Repo
privado + deploy só em commit da `main` que passou no CI → sem risco de código não confiável.

## Setup (uma vez)
1. **Runner self-hosted** — GitHub → repo → *Settings → Actions → Runners → New self-hosted runner*. Instale
   como serviço (systemd), sob um usuário no grupo `docker`, com os **labels**: `self-hosted`, `segurauto`,
   `production` (o `deploy.yml` seleciona por eles).
2. **GitHub Environment `production`** — *Settings → Environments → New environment: `production`*. Nele:
   - **Secret `ENV_FILE`** — o **conteúdo inteiro** do `.env` de produção (multi-linha). ⚠️ **Copie o `.env`
     ATUAL do servidor** para preservar `POSTGRES_PASSWORD` e `AUTH_PEPPER` — o CI **nunca** os regenera (o
     volume do banco já foi inicializado com eles; trocá-los quebra a conexão/os hashes). Inclui também
     `ANTHROPIC_API_KEY`, `SMTP_PASSWORD`, etc.
   - **Variable `GATEWAY_CONTAINER`** — o nome do container do reverse proxy compartilhado (específico do
     servidor; fica aqui, **não** no repo). Sem ela, o passo de `network connect` é pulado.
3. **Proteção da `main`** — opcional mas recomendado: exigir PR + checks do `ci.yml` verdes para merge. Como o
   deploy é gated no CI (`workflow_run` só deploya em `conclusion == success`), um push direto quebrado **não**
   deploya (o CI falha → o deploy nem roda).

## Release (a cada entrega)
Só publicar na `main`:
```
git push origin main            # push direto, OU merge de uma PR na main
```
O CI roda; passando, o `deploy.yml` escreve o `.env` (600) do `ENV_FILE`, roda
`docker compose -f docker-compose.production.yml up -d --build` (**stack completa**, incl. frontend em
**produção** — `next start`, não `next dev`), reconecta o proxy à rede (idempotente) e poda imagens dangling.
As migrations rodam no entrypoint do `ai-service`; o deploy é do **exato commit** que passou no CI (`head_sha`).

## Notas
- O compose fixa `name: segurauto` + `container_name`/nomes de rede e volume → o deploy pelo runner atinge o
  **mesmo** stack do deploy manual (`/opt/segurauto`), sem duplicar containers.
- `concurrency: cancel-in-progress: false` — um deploy nunca é cancelado no meio.
- Persistência da rede do proxy: além do passo idempotente a cada deploy, declarar `segurauto-network` como
  `external` no compose do próprio proxy dá religação durável caso o container do proxy seja recriado.
