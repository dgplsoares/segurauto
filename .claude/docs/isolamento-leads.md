# Isolamento entre leads, sessões e mensagens — invariantes de segurança

> Resultado de uma **verificação adversarial** dedicada: o isolamento **ainda não está garantido**.
> Este doc fixa as invariantes a honrar **antes** de construir o chat/sessões (Fase 4+). Prioridade alta.

## Estado atual (F0-F2)
Leads/outbox estão isolados por `id` (repos/services por request, sessão nova por request, sem estado
mutável global que vaze PII). **Mas** a base de identidade é frágil (ver LEAK-1) e não há auth.

## 🔴 Achado crítico (a corrigir)
**LEAK-1 — `Idempotency-Key` como âncora de identidade.** A key é fornecida pelo cliente
(`POST /leads`). No caminho de dedup, a resposta hoje devolve `id`+`score`+`band` do lead existente. Se
duas requisições colidem/adivinham a mesma key, um lead recebe dados de **outro**. Quando o `lead_id`
ancorar a sessão de chat, isso vira impersonação.

**Correção mínima (aplicável já):**
- No dedup, **não** retornar dados materiais quando a chave não pertence ao principal atual: devolver
  `{deduped:true}` mínimo (sem `score`/`band`) ou **409** em colisão.
- A resposta de captura não precisa expor `score`/`band` (são calculados async; nulos na captura).

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

> Detalhe da auditoria e cenários de ataque: registrado no diário e na análise consolidada do processo.
