"""Contexto `eval` (DEC-ORB-042) — projeção de LEITURA da jornada do lead, para avaliação/demo.

Fail-closed: as rotas só são montadas em `environment=local` ou com `enable_eval_api` ligado. NÃO é CRM
nem funil de vendas: apenas agrega o que os outros contextos já persistiram (leads, chat, cotações,
outbox e `integration_events`). Read-only, sem lógica de domínio.
"""
