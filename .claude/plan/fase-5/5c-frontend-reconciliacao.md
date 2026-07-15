# Fase 5c — Reconciliação do frontend (Figma Make → Next.js) · V1.5

> O export do Figma Make (Vite + React 18 + Tailwind v4 + shadcn/ui) foi clonado na zona **local**
> (`workspace/`, fora do git). A F5c porta a UI para o nosso `frontend/` (Next.js), liga ao BFF real e traz
> a **conversa de cotação multi-turn** + o **card de cotação** (F5) e a atribuição **UTM**.

## Levantamento (export do Figma Make)

- **Contrato quase drop-in:** o `lib/api.ts` deles tem as **mesmas 4 funções** (`createLead`, `requestOtp`,
  `verifyOtp`, `sendChatMessage`), **mesmos endpoints** (`/api/lead`, `/api/auth/request-otp`,
  `/api/auth/verify-otp`, `/api/support`) e **mesmos tipos** (`LeadPayload`, `LeadResult`, `VerifyOtpResult`,
  `ChatResult`, `ApiError.status`) — porque demos o prompt certo. Integrar = trocar o corpo mock por `fetch`.
- **Máquina de estados igual:** `LeadFlowProvider` (Context) `idle → presignup → otp → chat`, token em memória.
- **Port delimitado:** das deps pesadas do `package.json`, **nenhuma é usada** fora de `ui/` (MUI,
  react-router, slick, dnd, confetti, recharts, sonner…). Os componentes usam só **lucide-react, motion,
  react-hook-form** e **shadcn/ui** (Radix) + **input-otp**. **Sem `figma:asset`/`imports/`** no app (ilustrações
  são SVG-as-TSX, portáveis). Tailwind v4 via CSS (sem `tailwind.config`). → sem inferno de MUI/emotion SSR.
- **LP renderizada:** componentes `v2/*` (`V2Header/Hero/Mission/Features/CoverageTabs/Deep/Ratings/Story/
  Reconversion/Footer`) + `faq` + o fluxo (`prompt-box`, `pre-signup-modal`, `otp-modal`, `chat-panel`,
  `chat-bubble`, `support-widget`).

## O gap central (chat)

O chat do export é **single-turn**: `sendChatMessage(msg, token) → /api/support` (o suporte RAG single-turn
da F4b). A nossa **conversa de cotação (F5)** é **multi-turn**: `/support/sessions` → turnos com slot-filling
→ **card de cotação**. O hero prompt-first deve levar a essa conversa de cotação. Portanto o chat precisa
evoluir para o fluxo de sessão + renderizar o card — não é um port mecânico.

## Plano (fatiado)

- **F5c.1 — Port + ligar o data layer.** Portar a UI (`v2/*` + fluxo + `ui/*` usados + tema Tailwind v4) para
  `frontend/` (Next.js App Router, `"use client"` nos componentes de estado). Ligar `lib/api.ts` ao **BFF
  real** (as 3 primeiras funções + o chat **single-turn** `/api/support`, que **já funciona** com o nosso
  backend usando o token do `verify-otp`). Entrega a **LP polida conectada ponta a ponta** (prompt → cadastro
  → OTP → chat), verificável.
- **F5c.2 — Cotação multi-turn + card + UTM.** Evoluir o `chat-panel` para o fluxo de sessão
  (`POST /api/support/sessions` → `.../messages`), acumular slots e **renderizar o card de cotação** quando
  `quote` chega. **Serviço fake de UTM** no frontend (4 campanhas: 2 Meta + 2 Google, sorteio por submissão)
  alimentando `source` do lead. Novos route handlers no BFF (`/api/support/sessions`, `.../messages`) + funções
  no `lib/api.ts` (`createChatSession`, `sendTurn`).

## Invariantes a manter

- **BFF preservado** (route handlers finos; nenhuma lógica de negócio no front). Token em memória na V1
  (cookie httpOnly = decisão de integração posterior — §7 do doc de handoff).
- **Zona git:** `segurauto/` sem referência a projetos externos (o export vive em `workspace/`, fora do git).
- **Reconciliar `lib/api.ts`:** o nosso (F5a prep) já tem os `fetch` reais; fundir com os tipos/assinaturas do
  export (que são idênticos).

## Verificação prevista

- **F5c.1:** `next build` (typecheck + lint) + smoke E2E na stack real (LP renderiza; prompt→modal→OTP→chat
  single-turn responde). grep-clean.
- **F5c.2:** turno multi-turn preenche slots e o **card de cotação** aparece; UTM sorteado vai no `source`.

## Decisões (a confirmar)

1. **Fatiamento** — F5c.1 (port + ligar, chat single-turn) e depois F5c.2 (multi-turn + card + UTM), vs tudo
   de uma vez.
2. **Escopo do port** — portar **todas** as seções `v2/*` (LP completa) vs só o núcleo do fluxo + seções
   principais.
