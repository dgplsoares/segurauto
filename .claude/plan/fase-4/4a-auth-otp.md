# Fase 4a — Auth / OTP (DEC-ORB-037)

Meta: primitivo de identidade — o lead prova posse do e-mail (OTP) e recebe um **token de sessão**
server-side → `lead_id`. É o pré-requisito do chat (anti-IDOR). Desenho **reconciliado por pentest**.

## Tabelas (migration 0003, aditiva, schema `business`)
- **`auth_sessions`**: `token_hash` char(64) **PK** (guarda o `sha256` do token, nunca o token cru),
  `lead_id` (ref por id), `created_at`, `last_seen_at`, `expires_at` (idle, index), `absolute_expires_at`,
  `revoked_at` nullable.
- **`otp_codes`**: `id`, `email` (normalizado, index), `code_hash`, `expires_at`, `attempts` int,
  `consumed_at` nullable, `created_at`. Índice parcial `WHERE consumed_at IS NULL`.

## `shared/security.py`
- `new_session_token()` = `secrets.token_urlsafe(32)`; `token_pk(t)` = `sha256(t)` (hash-at-rest).
- `gen_otp()` = `secrets.randbelow(100000)` → 5 dígitos zero-pad; `otp_hash(email, code)` =
  `hmac_sha256(pepper, email+code)`; comparação `hmac.compare_digest` (constant-time).
- **`auth_pepper`** server-side (env). **Fail-closed** fora de `environment=local`: sem pepper → não emitir OTP/sessão.

## Serviços (`business/service/auth_service.py`) — não commitam (boundary no endpoint)
- **`request_otp(email)`**: normaliza; **rate-limit** por e-mail (reenvio ≥ 30s + N/15min); **supersede** OTP
  ativo; gera+hasheia+grava; **envia via `NotificationPort` (fake: loga mascarado, nunca o código)** — só se
  existir lead p/ o e-mail; responde **202 neutro** em qualquer caso (enumeração aceita + rate-limit — D4).
- **`verify_otp(email, code)`**: `SELECT ... FOR UPDATE` no OTP ativo; se expirado/consumido → 401. **Errado
  → `attempts++` + cooldown/backoff (NÃO consome o código)** — anti-lockout (B2): um terceiro não queima o
  código da vítima; `verify` limitado por `(email[,ip])`. **Certo → consome + resolve lead (mais recente por
  e-mail) + cunha sessão** (token, `token_pk`, `expires_at=now+idle`, `absolute_expires_at=now+absoluto`);
  retorna o token cru (uma vez).
- **`validate_session(token)`**: `token_pk` lookup; rejeita revogado/absoluto/idle vencidos; **slide** (empurra
  `expires_at`, com coalescing ~60s); retorna `lead_id`.

## API (`business/api/auth.py`) + dependency
- `POST /auth/request-otp` {email} → 202 neutro. `POST /auth/verify-otp` {email, code} → 200 {token,
  expires_at} | 401. `POST /auth/logout` (revoga) → 204.
- **`require_session`** (`Authorization: Bearer <token>`) → `validate_session` → `lead_id`. Base do anti-IDOR da 4b.

## Portas
- **`NotificationPort`** (Protocol) + `FakeNotification` (default): registra envios p/ teste, loga e-mail
  **mascarado**, **nunca o código**. Real (email de verdade) = pós-V1, mesmo seam.

## Config (`shared/config.py`)
`otp_ttl` (~10min), `otp_length` (5), `otp_max_attempts` (~5), `otp_resend_interval` (30s), `otp_rate_window`,
`session_idle_ttl` (~30min), `session_absolute_ttl` (~12h), `auth_pepper`, `use_fake_notifications`.

## Testes
- **unit:** `security` (token/otp hash, constant-time), rate-limit, slide/expiração (idle+absoluto).
- **integração:** OTP válido→token; expirado/errado→401; **reuso do código → 401**; **anti-lockout** (5
  tentativas erradas de terceiro NÃO impedem o dono de logar depois); sessão expira; `require_session` bloqueia
  sem token; e-mail sem lead → 202 mas sem sessão.

## Riscos (do pentest)
- `auth_pepper` ausente em prod → fail-closed no startup. Corrida no `verify` → `FOR UPDATE`. OTP 5 díg
  (100k) → mitigado por cooldown-não-burn + rate-limit + TTL. Enumeração aceita (D4) + rate-limit.
