# Isolamento entre leads, sessões e mensagens — invariantes de segurança

> Resultado de uma **verificação adversarial** dedicada: o isolamento **ainda não está garantido**.
> Este doc fixa as invariantes a honrar **antes** de construir o chat/sessões (Fase 4+). Prioridade alta.

## Estado atual (F0-F2)
Leads/outbox estão isolados por `id` (repos/services por request, sessão nova por request, sem estado
mutável global que vaze PII). **Mas** a base de identidade é frágil (ver LEAK-1) e não há auth.

## ✅ LEAK-1 — CORRIGIDO na Fase 3.5 (era achado crítico) — DEC-ORB-035
**Era:** `Idempotency-Key` (client-controlled) como âncora de identidade — o dedup do `POST /leads`
devolvia `id`+`score`+`band` do lead existente; key colidida vazava dados de **outro** lead.

**Corrigido:** `LeadResponse` **não** expõe `score`/`band`; no dedup compara-se o **e-mail normalizado** —
dono legítimo → 200 `{id,status,deduped}`; colisão de key com outra identidade → **409 neutro** (sem
`id`/`score`/`band`/e-mail). Verificado (`pytest` + docker). Sem `UNIQUE(email)` (DEC-ORB-037): não há
enumeração via 409 no cadastro nem 500 em corrida mesmo-email/chave-diferente.

## Invariantes obrigatórias (Fase 4+)

1. **Auth primeiro.** Token opaco assinado **server-side** emitido no pré-cadastro, mapeado a `lead_id`
   numa tabela server-side. Identidade vem **do token**, nunca de chave/campo client-controlled.
2. **Anti-IDOR real.** `session_id` do path/body é **sempre** revalidado contra `token.lead_id` no
   backend (não só no BFF). Toda leitura de histórico: `WHERE session_id = :sid` (nunca só por `lead_id`, nunca sem filtro).
3. **História é do negócio; a IA é stateless.** `chat_sessions` (escopo `lead_id`) + `chat_messages`
   (escopo `session_id`, `UNIQUE(session_id, seq)`), FK+CASCADE **dentro** do schema de negócio. O
   transcrito é **montado e passado** para a IA; a IA nunca consulta por `lead_id`/`session_id`.
4. **Serialização por sessão.** Lock por `session_id` (advisory lock / `SELECT FOR UPDATE`) no turno do
   agente — evita corromper histórico e **duplicar ações** sob concorrência.
5. **Correlação não é autorização.** `X-Request-Id` só de origem confiável (header assinado do gateway em
   allowlist); senão gerar server-side; **nunca ecoar** um valor vindo do cliente.
6. **Streaming.** Usar middleware pure-ASGI (ou setar o contextvar dentro do gerador) para o `request_id`
   sobreviver ao stream de tokens do chat.
7. **RAG sem escopo só para conteúdo genérico.** A base de conhecimento é compartilhada (ok). **Artefato
   específico do lead (cotação/PDF/personalização) NÃO entra no vector store.** Se um dia entrar: colunas
   `owner_scope`+`owner_id` + filtro obrigatório + índice; default global-only.
8. **Entrega de artefato (PDF/quote).** Nunca por URL adivinhável/pública; endpoint autenticado que
   revalida `principal→lead_id`; chave opaca + TTL curto.
9. **Grafo sem estado compartilhado.** Agente LangGraph **reentrante**, estado passado por invocação; se
   usar checkpointer, `thread_id === session_id` (nunca `lead_id`/default). Sem `dict`/`ContextVar` de
   "conversa atual" no módulo.
10. **Masking central de PII.** `logging.Filter` no handler redige email/telefone/**placa**/CPF por regex
    (não confiar em call-sites); `SQLAlchemy echo=off` em prod; **nunca** logar `chat_messages.content` cru.
11. **Ações do chat na outbox** com `event_id` derivado de `(session_id, tipo, turno)` — não só
    `(lead, plataforma)` — para retry at-least-once não duplicar ação de um turno.

## Ciclo de vida da sessão + re-autenticação (OTP) — desenhar na fase de Hardening/Auth (pré-F4)

Requisito registrado; **design dedicado no início da fase de Hardening/Auth** (contexto fresco).

- **Sessão** ligada ao lead pelo token server-side (invariante 1). **Expiração:** definir política no design
  (proposta inicial: inatividade ~30 min com *sliding window*; TTL absoluto de segurança). Não deixar aberta para sempre.
- **Retorno após expirar — NÃO duplicar o lead.** O usuário **re-autentica para a MESMA identidade**
  (resolvida por **e-mail verificado**), nunca cria lead novo. Isso encerra o LEAK-1 (a `Idempotency-Key`
  deixa de ser âncora de identidade; a identidade passa a ser o e-mail verificado via OTP).
- **Login do recorrente (UX tradicional):** no modal aberto ao iniciar um chat (não autenticado), **botão
  secundário "Já tem cadastro? Entre"** → pede **e-mail** → dispara e-mail com **token OTP de 5 dígitos** →
  o modal desativa o botão e revela **5 campos sequenciais** + **timer regressivo de 30s** para reenviar o token.
- **Colisão no cadastro:** se o usuário digitar no cadastro um e-mail **já existente** → informar "você já
  tem cadastro" e disparar o **MESMO fluxo OTP** (não cria duplicado).
- **OTP:** curto, **TTL ~10 min**, **uso único**, **rate-limit** de envio, nunca logado em claro; o e-mail é
  fake/mock na V1 (seam de `NotificationPort`), real opt-in.

> Detalhe da auditoria e cenários de ataque: registrado no diário e na análise consolidada do processo.
