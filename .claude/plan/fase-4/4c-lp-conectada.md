# Fase 4c — Landing Page conectada (Next.js)

Meta: a LP real (layout do Figma Make) consumindo a API pelo **BFF**, com captura de lead, **modal de
OTP** e widget de suporte. Fecha o V1 visível.

## Entregáveis
- **BFF (route handlers)** — `app/api/lead/route.ts` → `POST {ai-service}/leads` (esconde a URL interna,
  valida server-side, gera/repassa `Idempotency-Key`); `app/api/support/route.ts` → `POST /support/chat`
  (repassa o `Authorization: Bearer` da sessão); `app/api/auth/*` → `/auth/request-otp` e `/auth/verify-otp`.
- **LP** — reconciliar o export do Figma Make com `../arquitetura-visual-lp.md` (hero, coberturas, FAQ,
  footer). A LP é **camada de apresentação fina** sobre o BFF (sem lógica de negócio no front).
- **`LeadForm`** (modal de pré-cadastro) — Nome, E-mail, Telefone/WhatsApp, Placa + **consent LGPD**;
  `Idempotency-Key` gerada no load; submit → `/api/lead`.
- **Modal de OTP** (DEC-ORB-037) — botão secundário **"Já tem cadastro? Entre"**; ao pedir OTP: **5 campos
  sequenciais** de dígito + **timer regressivo de 30s** para reenvio; colisão de e-mail no cadastro →
  informar + mesmo fluxo OTP. Verify → guarda o token da sessão → libera o chat.
- **`SupportChat`** (widget) — envia `/api/support` com o token; exibe a resposta (single-turn).

## Testes
- **frontend:** teste do `LeadForm`/BFF (mock do ai-service) — validação client+server, header
  `Idempotency-Key`; teste do fluxo do modal OTP (mock).
- **smoke E2E (docker):** enviar lead pela LP → persiste e (via worker) sincroniza; pedir OTP → verify →
  sessão → `SupportChat` responde do RAG.

## Riscos
- Export do Figma Make pode trazer deps/estrutura próprias → tratar como apresentação fina; não deixar
  lógica de negócio vazar. Armazenamento do token de sessão no front (localStorage vs cookie httpOnly) —
  decidir aqui (trade-off XSS×CSRF).

## Reanálise pré-fase (a fazer)
Inspecionar o export do Figma Make em `frontend/`; mapear seções reais para `arquitetura-visual-lp.md`;
decidir armazenamento do token; confirmar os contratos do BFF com os endpoints do ai-service.
