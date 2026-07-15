"""render_html (DEC-ORB-042, `?format=html`) — escaping anti-XSS em TODOS os caminhos.

Cobre não só o `content` da mensagem (caminho já exercitado pelo teste de integração), mas também os
demais campos de input livre renderizados (vehicle/reason/status/band/source do lead, coverages/pdf_ref da
cotação, request_id da outbox) e — crucial — o `_pre_json` do request/response dos `integration_events`,
que é um caminho de escape DISTINTO do `_esc` usado nos títulos/corpos.
"""
from app.eval.render import render_html

_XSS = "<script>alert('x')</script>"
_ATTR = '"><img src=x onerror=alert(1)>'


def _journey_with_payload_everywhere() -> dict:
    """Uma jornada com payload de XSS em CADA campo derivado de dados do usuário."""
    return {
        "email": _XSS,
        "resolved_lead_id": _XSS,
        "canonical_identity": True,
        "lead_ids": ["l1"],
        "leads": [{
            "id": "l1", "name": _XSS, "email": _XSS, "phone": "1", "vehicle": _XSS, "zipcode": "1",
            "consent": True, "source": _XSS, "status": _XSS, "score": 1, "band": _XSS, "reason": _XSS,
            "created_at": None,
        }],
        "chat_sessions": [{
            "session_id": "s1", "lead_id": "l1", "status": "active", "slots": {},
            "quote_ready_at": None, "handoff_requested_at": None, "created_at": None, "last_turn_at": None,
            "messages": [{"seq": 1, "role": "user", "content": _XSS, "created_at": None}],
        }],
        "quotes": [{
            "quote_id": "q1", "session_id": "s1", "lead_id": "l1", "premium_cents": 100, "currency": "BRL",
            "coverages": [_XSS], "broker_applied": False, "pdf_ref": _XSS, "slots": {}, "created_at": None,
        }],
        "outbox": [{
            "intent_type": _XSS, "status": _XSS, "retry_count": 0, "request_id": _ATTR, "created_at": None,
        }],
        "integration_events": [{
            "event_type": _XSS, "status": _XSS, "request": {"payload": _XSS, "attr": _ATTR},
            "response": {"payload": _XSS}, "session_id": "s1", "request_id": "r1", "created_at": None,
        }],
    }


def test_render_html_escapes_all_user_fields_including_event_json():
    html = render_html(_journey_with_payload_everywhere())
    # Nenhuma tag CRUA sobrevive — nem nos títulos/corpos (_esc) nem no <pre> de request/response (_pre_json).
    assert "<script>" not in html
    assert "<img" not in html
    # As formas escapadas ESTÃO presentes (o conteúdo foi renderizado, só que neutralizado) — incluindo o
    # `<img` do _ATTR, que só chega ao HTML pelos caminhos _esc (outbox request_id) e _pre_json (event JSON).
    assert "&lt;script&gt;" in html
    assert "&lt;img" in html


def test_render_html_empty_journey_is_safe():
    html = render_html({
        "email": "a@b.com", "resolved_lead_id": "x", "canonical_identity": False,
        "leads": [], "chat_sessions": [], "quotes": [], "outbox": [], "integration_events": [],
    })
    assert "Nenhum evento" in html and "<script" not in html
