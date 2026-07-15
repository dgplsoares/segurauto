# Fase 5b — Tools de cotação (quote/PDF) + audit de integração (reanálise)

> Constrói sobre a F5a (conversa multi-turn com `ready_to_quote`). Duas entregas: **(1)** as tools
> read-inline `quote_tool`/`pdf_tool` (a cotação e o PDF), **(2)** o **audit de integração** que registra as
> trocas reais com CRM/Ads/e-mail — habilitando a **jornada do lead** (DEC-ORB-042).

## O que já existe (terreno)

- `ready_to_quote`/`quote_ready_at` na sessão (F5a.2) — o gancho onde a cotação pluga.
- **`CrmPort.price_quote(*, vehicle, zipcode) -> dict`** já implementado (FakeCrm: prêmio determinístico por
  região do 1º dígito do CEP). O `quote_tool` reusa — **o número vem do CRM, nunca do LLM** (DEC-ORB-027).
- `worker` processa `QUALIFY → CRM_SYNC/ADS_META/ADS_GOOGLE` via outbox, chamando os fakes (só loga hoje).
- `NotificationPort.send_otp` (fake) — o envio de OTP.

## Design proposto

**Orquestração pelo `business` (não pelo LLM).** Coerente com o refino da F5a.2: o `business` decide e chama
as tools deterministicamente; o agente só **fraseia** a resposta com o resultado. O número/decisão de
cotação ficam fora do LLM (reconcilia DEC-ORB-027 como fizemos com a extração de slots).

**1. `quote_tool` (read-inline, business).** Quando o turno detecta `ready_to_quote` e ainda não há cotação,
o `ChatService` chama o `quote_tool`: valida os slots (já validados na F5a.2), chama `CrmPort.price_quote`,
aplica desconto de corretor **se `broker_code` for autorizado** (fecha o E6 — a autorização de `broker_code`
é aqui, via CRM fake), persiste em `business.quotes` e devolve a cotação (card) na resposta do turno.

**2. `pdf_tool` (fake, business).** Gera um artefato de cotação (fake) e o disponibiliza por **GET
autenticado com gate de posse** (invariante 8 de `isolamento-leads.md`: artefato do lead nunca por URL
adivinhável) — reusa `require_session_chat` + `load_owned`.

**3. Audit de integração (`business.integration_events`).** Tabela **append-only** que registra cada troca
com um sistema externo (fake): `crm_sync`, `crm_price_quote`, `ads_conversion`, `notify_otp` — com
`lead_id`/`session_id`/tipo/`request`/`response`/`status`/`request_id`/`created_at`. Escrita pelos
**callers** (worker, `quote_tool`, o caminho do OTP) logo após chamar o fake — sem acoplar cada adapter ao
banco. É o que a **jornada do lead** (DEC-ORB-042, F7) vai ler para mostrar os fluxos ponta a ponta.

**Guardrails/isolamento reusados:** args da tool vêm de slots **validados** (E6); `quotes`/`integration_events`
em `business` sem FK cruzada (DEC-ORB-021); `quote` escopada à sessão (gate de posse anti-IDOR); PII de
`request`/`response` mascarada nos logs (E8); `premium` em **centavos** (Integer) para não perder precisão.

## Fatiamento

- **F5b.1** — `quotes` (migração) + `quote_tool` (business) + autorização de `broker_code` no CRM fake +
  `pdf_tool` (fake) + GET autenticado da cotação/PDF + resposta do turno com o card.
- **F5b.2** — `integration_events` (migração) + escrita pelo worker/quote/OTP (habilita a jornada).

## Verificação prevista (inclui adversarial)

- Slots completos → turno devolve cotação com `premium` do CRM (não do LLM); `broker_code` inválido → sem
  desconto (autorização server-side, E6). Cotação idempotente (uma por sessão; re-cota = F6).
- GET da cotação/PDF: dono → 200; outro lead → **404 neutro** (anti-IDOR).
- `integration_events` registra cada troca (crm_sync/ads/price_quote/otp) com request/response.
- `ruff` + suite verde + smoke HTTP + grep-clean.

## Decisões (travadas)

1. **Gatilho: automático** — quando os slots completam no turno, o business chama `quote_tool` e já devolve a
   cotação (card) na resposta. → **DEC-ORB-043**
2. **Audit: tabela dedicada `integration_events`** (append-only) — cobre também `price_quote`/OTP (fora do
   outbox), habilitando a jornada completa. → **DEC-ORB-044**
3. **PDF: só um marcador** (`pdf_ref` na cotação) — sem bytes nem endpoint de download. Simplifica a F5b.1;
   sem GET de PDF. → **DEC-ORB-043**
4. **Confirmados no plano:** `quote_tool`/`pdf_tool` **orquestrados pelo business** (número do CRM, não do
   LLM); `broker_code` **autorizado no CRM fake** (fecha o E6); cotação **escopada à sessão** (gate de posse)
   e **uma por sessão** (re-cota = F6).
