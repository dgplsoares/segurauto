# Fase 4 — Auth + Suporte + LP (plano-mestre)

> Refatiada em **4a / 4b / 4c**. Entrega o **primeiro contato do lead com a IA**, **autenticado e
> isolado**: o lead se identifica (OTP), conversa com o suporte (RAG single-turn) e tudo isso pela
> Landing Page real. Fecha o **V1**.
>
> **Protocolo:** reanálise pré-fase dedicada ao iniciar cada subfase (contexto fresco → antecipar gaps).
> Registrar decisões em `DECISIONS.md`, descobertas no diário, e atualizar a memória.

## Subfases

| Sub | Entrega | Verificação-chave |
|---|---|---|
| **4a — Auth/OTP** | tabelas `auth_sessions`/`otp_codes` + `AuthService`/`OtpService` + `NotificationPort` fake + `/auth/*` + `require_session`; **sessão só pós-OTP** | OTP válido/errado/expirado/reuso; rate-limit; **anti-lockout**; sessão expira (idle+absoluto) |
| **4b — support_agent** | LangGraph `guardrail_in→retrieve→validate→generate→guardrail_out→handoff` (single-turn); `AiPort.support` + `/ai/support`; `POST /support/chat` **autenticado** | resposta grounded; recusa se insuficiente (`rag_preferred`); guardrail de injeção; chat exige sessão |
| **4c — LP conectada** | Next.js (Figma Make): `LeadForm`→BFF→`/leads`; **modal OTP** (5 campos, timer 30s, "Já tem cadastro? Entre"); `SupportChat`→BFF | teste do BFF/form; smoke E2E (lead → worker sincroniza; chat responde) |

## Decisões que fundamentam a Fase 4
- **DEC-ORB-037 (auth):** token opaco server-side → `lead_id` via `require_session`; **sessão só pós-OTP**
  (prova de posse do inbox); **e-mail = identidade, sem `UNIQUE`** (múltiplos leads/pessoa); OTP hasheado
  (HMAC+pepper), **cooldown-não-burn** (tentativa errada não queima o código) + rate-limit; sliding+absoluto.
  **Reconciliado via pentest adversarial** (`workspace/10`).
- **Support single-turn = stateless:** o histórico persistente (`chat_sessions`/`chat_messages`, lock por
  sessão) só entra na **F5** (multi-turn). Na 4b o suporte responde por turno, sem guardar conversa → sem
  vazamento de histórico entre leads. RAG **genérico compartilhado** (nenhum dado de lead no vector store).
- **Guardrails (DEC-ORB-026):** input e docs recuperados são dados não-confiáveis (scope-and-strip); PII mascarada.

## Isolamento (pré-condições de `../docs/isolamento-leads.md`)
4a entrega o **primitivo de auth**; 4b **aplica `require_session`** no `/support/chat` (anti-IDOR) e mantém
o suporte **stateless**. As invariantes de histórico/lock/thread_id valem quando o chat multi-turn existir (**F5**).
