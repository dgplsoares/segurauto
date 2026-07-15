"""Guardrails de texto reusáveis (DEC-ORB-026/039): o texto do usuário é DADO não-confiável.

`strip_injection` (scope-and-strip) e `detect_handoff` vivem em `shared` para reuso por `business`
(sanitização do transcrito na montagem — E5) e por `ai` (guard_in do agente), **sem cross-import** entre os
contextos. `strip_injection` é **best-effort**, NUNCA uma fronteira de segurança — a defesa real é o schema
de valor de slot (E6) + a delimitação do transcrito + manter a decisão determinística fora do LLM.
"""
import re

_INJECTION_RE = re.compile(
    r"(?i)(ignore\s+(as\s+|todas\s+as\s+)?(instru\w+|previous|anteriores)|desconsidere|system\s+prompt|"
    r"forget\s+(the\s+)?(above|previous)|act\s+as|aja\s+como|revele|reveal)"
)
_HANDOFF_TERMS = ("corretor", "contratar", "fechar", "falar com humano", "atendente", "comprar")


def strip_injection(text: str) -> str:
    """Neutraliza diretivas de prompt-injection, mantendo a pergunta (scope-and-strip). Best-effort."""
    return " ".join(_INJECTION_RE.sub(" ", text).split())[:500]


def detect_handoff(text: str) -> bool:
    low = text.lower()
    return any(term in low for term in _HANDOFF_TERMS)
