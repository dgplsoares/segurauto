# Fase 5a — Persistência de conversa + agente multi-turn (reanálise)

> Reanálise conduzida por um fluxo adversarial (5 leitores das fontes de verdade → 3 designs com
> posturas distintas → juiz sintetiza → 3 pentesters quebram o design escolhido). O pentest achou
> **8 furos reais** (vários verificados contra o código), incorporados abaixo como **emendas
> obrigatórias**. Este doc é a base para a **aprovação** antes de codar.

## Escopo

**Dentro da F5a (backend):** persistência de conversa (`chat_sessions`/`chat_messages`), agente
conversacional **multi-turn** com slot-filling (veículo, CEP, tem corretor?/código), isolamento e lock
por sessão, endpoint stateful autenticado.

**Fora da F5a:** as tools de cotação/PDF (`quote_tool`/`pdf_tool`) e a entrega de artefato = **F5b**;
UTM fake + UI de chat multi-turn + card de cotação = **F5c** (quando o front do Figma aterrissar).

> ⚠️ **Tensão de escopo:** a DEC-ORB-027 lista `quote_tool`/`pdf_tool` como tools *read-inline* "de F5a",
> mas o fatiamento aprovado coloca a cotação na F5b. Esta reanálise **segue o fatiamento**: a F5a só
> **sinaliza** `ready_to_quote` (nó `signal` + coluna `quote_ready_at`), sem executar tool nem enfileirar
> outbox. Precisa de confirmação (e reconciliar a redação da DEC-ORB-027).

## Design escolhido

**Postura:** isolamento/robustez sob concorrência primeiro, executado com a disciplina do seam de
extração V2 — cada decisão fecha um vetor de `isolamento-leads.md` reusando idiomas que já existem no repo
(`active_otp_for_update` FOR UPDATE, `require_session→lead_id`, o esqueleto LangGraph do 4b, migração 0003).

**1. Schema.** `business.chat_sessions` + `business.chat_messages` (nenhuma tabela em `ai.*`). O contexto
`ai` ganha só `AiPort.converse` + endpoint **stateless** `POST /ai/converse` (sem tabela). `lead_id` é
`String(36)` **NU, sem FK** (convenção de `OutboxRow`/`AuthSessionRow`: referência cross-context por id,
resolvida pelo token — mantém o split de banco V2 trivial). FK+CASCADE só existe **dentro** de `business`
(`chat_messages → chat_sessions`). Zero FK cruzando `business↔ai` (DEC-ORB-021).

**2. Lock/concorrência.** `SELECT ... FOR UPDATE` na linha de `chat_sessions` (reusa `active_otp_for_update`):
a **mesma** query faz lock **e** anti-IDOR (`WHERE id=:sid AND lead_id=:token_lead_id`) num round-trip;
`None → 404 neutro`. `UNIQUE(session_id, seq)` é o backstop determinístico.

**3. Slot-filling.** Coluna `slots` **JSONB** business-owned (`vehicle/zipcode/has_broker/broker_code`),
autoritativa (não re-derivada do histórico). Por turno, sob o lock: carrega `slots` → passa ao agente →
mescla os extraídos → **valida** → regrava. `chat_messages` (seq) é a auditoria/ordenação.

**4. Endpoint.** Família stateful sob `require_session`, com **criar** separado de **postar turno**:
- `POST /support/sessions` → minta `session_id`, insere sessão escopada ao `lead_id` (aceita `seed_slots`
  e/ou o hero-prompt bufferizado, validados no server), retorna `{session_id, slots, missing_slots}`.
- `POST /support/sessions/{session_id}/messages {message}` → **o turno**, boundary de commit.
- `GET /support/sessions/{session_id}/messages` → histórico (sempre após **gate de posse explícito**).

**5. Grafo (`ConverseAgent`, esqueleto do 4b).** `guard_in → extract → retrieve → [cond] → respond | refuse
| signal`. `retrieve` sempre roda (permite FAQ no meio do slot-filling via RAG `rag_preferred`, barato no
stub). Nós **disjuntos** das state keys (evita o gotcha `score`×`rubric`). **Sem checkpointer** (reentrância
pura; se um dia usar, `thread_id === session_id`, nunca `lead_id`/default). `RagService` injetada **no state**
(não engine global). `signal` seta `ready_to_quote` (gancho onde `quote_tool`/`pdf_tool` plugam em **F5b**).

**6. Migração.** `0004_chat.py` à mão (down_revision `0003`), `upgrade` cria `identities`, `chat_sessions`
e `chat_messages`; ORM na mesma `Base` de `business/repository/models.py`.

**7. Identidade canônica (decisão nº 3).** Nova tabela `business.identities(email_normalized UNIQUE,
canonical_lead_id, created_at)`. No `verify_otp`, resolve-se o `canonical_lead_id` (upsert: usa o existente;
senão cria apontando para a lead resolvida hoje por e-mail) e a sessão é mintada com `lead_id =
canonical_lead_id`. O gate segue **estrito em `lead_id`** (nunca relaxa para e-mail — fecha o E2/IDOR-MED),
mas `lead_id` passa a ser **estável por identidade**, dando continuidade na re-auth. Refina a DEC-ORB-037.

## Emendas obrigatórias (do pentest adversarial)

| # | Sev | Furo | Emenda |
|---|---|---|---|
| E1 | **HIGH** | GET histórico / montagem do transcrito **sem gate de posse** — `chat_messages` não tem `lead_id`; a posse só é provada no POST (subproduto do FOR UPDATE). Um `SELECT ... WHERE session_id=:sid` literal vaza o transcrito da vítima. | Helper **compartilhado** `load_owned_session_or_404(sid, lead_id)` (`WHERE id=:sid AND lead_id=:token_lead_id`), chamado por **todo** caminho de leitura **antes** de tocar `chat_messages`. Teste: A lê sessão de B → **404**. |
| E2 | **HIGH** | **Sem idempotência de turno lógico**: retry/double-submit aloca `seq` novo → **duplica** o turno (LLM 2×, `quote_ready_at` 2×) e derrota o `event_id=(session,tipo,turno)` do F6. `UNIQUE(session_id,seq)` **não** protege (cada retry ganha seq novo). | Turno aceita **`client_turn_id`** com `UNIQUE(session_id, client_turn_id)`. Sob o lock: se já existe → **replay** da resposta gravada (sem novo seq, sem LLM). Espelha `leads.py` (Idempotency-Key + `resolve_after_conflict`). |
| E3 | **HIGH** | **FOR UPDATE + conexão do pool presos durante RAG+LLM** (~46,5s no pior caso; pool default 15; sem `lock_timeout`/`statement_timeout`) → exaustão do pool pode **inanir a captura** (`/leads`), contrariando DEC-ORB-025. | **Não segurar o lock/txn através do LLM.** Decisão do usuário: **(A)** commit único (DEC-ORB-012) + `lock_timeout` + `statement_timeout` + cap de transcrito + **pool isolado** do chat; **(B)** dois-commits (lock curto→LLM fora da txn→re-lock). Ver questão em aberto. |
| E4 | MED | Alocador de `seq` com **dupla fonte de verdade** (`last_seq` + `UNIQUE`): se dessincronizar, o "409 retryable" vira **poison pill** (loop de 409), sem reconciliação. | Alocador **auto-curável**: `next_seq = COALESCE(MAX(seq),0)+1 FROM chat_messages WHERE session_id=:sid` sob o lock (fonte única = as mensagens). Se manter `last_seq` como cache, reconciliar no `IntegrityError`. |
| E5 | **HIGH** | **`guard_in` é no-op**: `chat_messages.content` é gravado **cru** (auditoria) e o transcrito remonta a linha crua → o LLM vê texto **não-sanitizado** apesar do `strip_injection`. Injeção plantada no turno 1 **persiste** e re-executa (stored, 2ª ordem). | Tratar o transcrito como **fonte não-confiável**: sanitizar/**delimitar estruturalmente cada linha** na montagem (não só a mensagem nova); passar `safe_message` como turno corrente (não relê a linha crua recém-gravada). |
| E6 | **HIGH** | **Slot poisoning**: whitelist só de **chaves** deixa **valores** arbitrários virarem args de `quote_tool`/`pdf_tool` (F5b) e estado "confiável" re-injetado — `broker_code` de outro corretor (desvio de comissão), `zipcode` mais barato, `has_broker=false` para pular validação. | **Schema de VALOR** por slot **antes** de persistir/alimentar: `zipcode ^\d{5}-?\d{3}$`, `broker_code` padrão + **resolução/autorização server-side** (nunca aceitar cru), `has_broker` bool estrito, `vehicle` vocab/pattern + cap de tamanho. `ready_to_quote` deriva de slots **validados**. **Recomendação: extração determinística (regex), não por LLM.** |
| E7 | MED | `strip_injection` é **denylist trivialmente contornável** (até "ignore all previous instructions" passa). É o único guardrail programático e é reusado no caminho de maior risco. | Tratar como **best-effort, nunca fronteira de segurança**. Defesa real = E5 (delimitar transcrito) + E6 (schema de valor) + número determinístico (já feito). |
| E8 | MED | Masking (inv.10) **não** cobre CEP, telefone nem placa minúscula; **CRLF** em valor de slot permite **log-forging**. Sem `max_length` na mensagem; transcrito sem `LIMIT` → O(n²) + estouro de contexto. | Estender `redact_pii` (CEP `\d{5}-?\d{3}`, telefone BR, placa case-insensitive); neutralizar `\r\n` nos valores; **nunca** logar `content`/`slots` crus. `max_length` no Pydantic da mensagem + **janela de transcrito** (últimos-K/orçamento de tokens). |

## Decisões (travadas)

1. **Escopo:** F5a só **sinaliza** `ready_to_quote` (nó `signal` + `quote_ready_at`); a cotação
   (`quote_tool`/`pdf_tool`) é a **F5b**. Reconcilia a redação da DEC-ORB-027. → **DEC-ORB-039**
2. **Extração de slots: determinística** (regex/regras) + schema de valor server-side; a resposta
   conversacional segue por LLM. Fecha a superfície do E6 e é CI-determinística. → **DEC-ORB-039**
3. **Boundary do turno: commit único** (DEC-ORB-012) + `lock_timeout` + `statement_timeout` + cap de
   transcrito + **pool de conexões isolado** do chat. Turno lento falha rápido, nunca prende a captura. → **DEC-ORB-040**
4. **Continuidade: `canonical_lead_id` agora** (tabela `identities`). O gate segue estrito em `lead_id`
   (canônico); re-auth resolve a mesma âncora. → **DEC-ORB-041** (refina DEC-ORB-037)
5. **Confirmados (defaults):** `slots` JSONB; `session_id` do path como `str` (404 neutro, nunca 422/403);
   endpoints em `/support/sessions` (o `/support/chat` single-turn do 4b é depreciado/migrado); **sem
   streaming** na F5a (JSON; streaming = F5c); expiração herdada do `auth_session` (F5a só adiciona
   `status` + `last_turn_at`).

## Fatiamento e verificação previstos

- **F5a.1** — migração + ORM + repositórios (sessão/mensagem) + `load_owned_session_or_404` + alocador de
  seq auto-curável + endpoints (`create`/`turn`/`GET`) com gate de posse e idempotência de turno.
- **F5a.2** — `ConverseAgent` (LangGraph) + `AiPort.converse` + `/ai/converse` stateless + extração/validação
  de slots + guardrails (E5/E6/E7) + masking estendido (E8).
- **Verificar (inclui adversarial):** A lê/posta sessão de B → 404 (E1); retry de turno → efeito 1× (E2);
  dois turnos concorrentes → seq íntegro; injeção no turno 1 não re-executa no turno N (E5); valor de slot
  fora do schema é rejeitado, `broker_code` autorizado server-side (E6); LLM lento não prende a captura (E3);
  logs sem CEP/telefone/placa/CRLF (E8).
