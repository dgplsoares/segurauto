"""Contexto `business`: dono do ciclo de vida do lead (leads, outbox, adapters CRM/Ads,
worker). Unidade **extraível** para um backend dedicado na V2 (DEC-ORB-021).

Chama o contexto `ai` **apenas** via `AiPort` — nunca importa internals de IA.
"""
