# Deploy — SegurAuto (produção/homolog)

Stack **isolado e auto-contido**: Postgres próprio + `ai-service` + `worker` + `frontend`, numa **rede docker
própria** (`segurauto-network`), **sem publicar nenhuma porta no host**. O acesso externo é por um **reverse
proxy compartilhado** que faz `proxy_pass` para o container `segurauto-frontend:3000` — o **único** ponto de
integração com a infra de fora.

> O ambiente remoto é um **HOMOLOG** que funciona como prod, mas **não é indexado** (`ALLOW_INDEXING=false` →
> `noindex` + `robots.txt disallow`). Na prod real, ligar `ALLOW_INDEXING=true`.

## Arquivos
- [`../docker-compose.production.yml`](../docker-compose.production.yml) — o stack isolado (build local, sem registry).
- [`reverse-proxy.conf.example`](reverse-proxy.conf.example) — bloco de servidor (nginx) a copiar/adaptar no proxy.

## `.env` de produção (no servidor, **NÃO versionar**)
Colocar em `/opt/segurauto/.env` (ou o path do checkout). Injetar os segredos a partir do secret store (ex.:
GitHub Actions Secrets) — **nunca** commitar. Modelo:

```dotenv
ENVIRONMENT=production
LOG_LEVEL=INFO

# Banco (senha forte — obrigatória)
POSTGRES_USER=segurauto
POSTGRES_PASSWORD=<senha-forte>
POSTGRES_DB=segurauto
DATABASE_URL=postgresql+asyncpg://segurauto:<senha-forte>@db:5432/segurauto

# Auth (pepper real — obrigatório fora de local)
AUTH_PEPPER=<pepper-aleatório-forte>

# Avaliação (jornada com dados fake, protegida por basic-auth no proxy)
ENABLE_EVAL_API=true

# LLM (stub sem segredo; real opt-in)
LLM_PROVIDER=anthropic            # stub | openai | anthropic
ANTHROPIC_API_KEY=<chave>         # ou OPENAI_API_KEY, conforme o provider

# E-mail (SMTP genérico — provider é infra trocável; preencha com o SEU servidor SMTP)
USE_FAKE_NOTIFICATIONS=0
SMTP_HOST=<seu-servidor-smtp>
SMTP_PORT=465                     # 465 = TLS implícito (SMTP_SSL=1) | 587 = STARTTLS (SMTP_SSL=0)
SMTP_SSL=1
SMTP_USER=<usuário-smtp>
SMTP_PASSWORD=<senha/api-key-smtp>
MAIL_FROM=SegurAuto <noreply@seu-dominio>   # o domínio precisa estar verificado (DKIM/SPF) no provider

# Frontend
AI_SERVICE_URL=http://ai-service:8000
ALLOW_INDEXING=false             # homolog = não indexar
```

## Passos (genéricos)
1. Checkout do repo no servidor + criar o `.env` acima.
2. Subir o stack: `docker compose -f docker-compose.production.yml up -d --build`. As migrations rodam no
   start do `ai-service`; o `worker` reinicia até o schema existir (por design).
3. **Wire do proxy (único toque compartilhado):** fazer o proxy participar da rede `segurauto-network`
   (external) e adicionar o bloco de [`reverse-proxy.conf.example`](reverse-proxy.conf.example) ao `conf.d`;
   validar e recarregar (`nginx -t && nginx -s reload`).
4. Gerar o `.htpasswd` da rota `/eval/` (ex.: `htpasswd -c <arquivo> <usuário>`).
5. Verificar: a LP carrega em `https://<seu-subdominio>`, `/eval/` pede credencial, nenhuma porta nova no host.

> Detalhes específicos de um servidor concreto (nomes de containers/redes do proxy, paths, DNS/CDN, permissões)
> ficam no runbook operacional **fora deste repositório**.
