"""Contexto `ai`: infraestrutura de IA (agentes LangGraph, RAG, orquestrador de modelos,
embeddings/rerank). Permanece FastAPI na V2 (DEC-ORB-021).

Expõe um contrato HTTP stateless (`/ai/qualify`, `/ai/support`) — não acessa tabelas de negócio.
"""
