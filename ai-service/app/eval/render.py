"""Render HTML da jornada (DEC-ORB-042, `?format=html`) — conveniência de avaliação.

Uma timeline cronológica autocontida (CSS inline). TODO valor derivado de dados do usuário (mensagens de
chat, slots, request/response dos eventos) passa por `html.escape` — o conteúdo do chat é entrada livre do
usuário e nunca pode ser interpretado como markup (anti-XSS na própria página de avaliação).
"""
import html
import json
from datetime import datetime


def _esc(value: object) -> str:
    return html.escape("" if value is None else str(value))


def _fmt_ts(ts: object) -> str:
    if isinstance(ts, datetime):
        return ts.strftime("%d/%m/%Y %H:%M:%S UTC")
    return _esc(ts)


def _sort_key(ts: object) -> str:
    # Ordena por ISO string (datas tz-aware → ordem estável); ausência vai para o fim.
    return ts.isoformat() if isinstance(ts, datetime) else "~"


def _pre_json(obj: object) -> str:
    return f'<pre class="json">{html.escape(json.dumps(obj, ensure_ascii=False, indent=2))}</pre>'


def _events(journey: dict) -> list[dict]:
    """Achata a jornada numa lista de eventos cronológicos {ts, kind, title, body}."""
    out: list[dict] = []
    for lead in journey.get("leads", []):
        badge = " · ".join(
            _esc(x) for x in [lead.get("status"), lead.get("band"), lead.get("source")] if x
        )
        out.append({
            "ts": lead.get("created_at"),
            "kind": "lead",
            "title": f"Lead capturado — {_esc(lead.get('vehicle'))}",
            "body": f'<div class="meta">{badge}</div>'
            + (f'<div class="reason">{_esc(lead.get("reason"))}</div>' if lead.get("reason") else ""),
        })
    for sess in journey.get("chat_sessions", []):
        for msg in sess.get("messages", []):
            role = msg.get("role")
            out.append({
                "ts": msg.get("created_at"),
                "kind": f"msg-{'user' if role == 'user' else 'assistant'}",
                "title": ("🧑 Cliente" if role == "user" else "🤖 Consultor") + f" · #{_esc(msg.get('seq'))}",
                "body": f'<div class="bubble">{_esc(msg.get("content"))}</div>',
            })
    for q in journey.get("quotes", []):
        cents = q.get("premium_cents") or 0
        brl = f"{q.get('currency', 'BRL')} {cents / 100:,.2f}"
        covs = ", ".join(_esc(c) for c in (q.get("coverages") or []))
        broker = " · corretor aplicado" if q.get("broker_applied") else ""
        out.append({
            "ts": q.get("created_at"),
            "kind": "quote",
            "title": f"💰 Cotação — {_esc(brl)}{broker}",
            "body": f'<div class="meta">{covs}</div>'
            + (f'<div class="meta">pdf: {_esc(q.get("pdf_ref"))}</div>' if q.get("pdf_ref") else ""),
        })
    for o in journey.get("outbox", []):
        out.append({
            "ts": o.get("created_at"),
            "kind": "outbox",
            "title": f"📤 Outbox — {_esc(o.get('intent_type'))} [{_esc(o.get('status'))}]",
            "body": f'<div class="meta">retries: {_esc(o.get("retry_count"))} · req: {_esc(o.get("request_id"))}</div>',
        })
    for e in journey.get("integration_events", []):
        out.append({
            "ts": e.get("created_at"),
            "kind": "integration",
            "title": f"🔗 {_esc(e.get('event_type'))} [{_esc(e.get('status'))}]",
            "body": "<div class=\"cols\"><div><b>request</b>" + _pre_json(e.get("request"))
            + "</div><div><b>response</b>" + _pre_json(e.get("response")) + "</div></div>",
        })
    out.sort(key=lambda ev: _sort_key(ev.get("ts")))
    return out


_STYLE = """
:root{color-scheme:light}
*{box-sizing:border-box}
body{margin:0;background:#f4f6fb;color:#1c2434;font:14px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:920px;margin:0 auto;padding:28px 18px 64px}
h1{font-size:20px;margin:0 0 4px}
.sub{color:#5b6472;margin:0 0 20px;font-size:13px}
.pill{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;background:#e4e9f5;color:#33415c;margin-right:6px}
.pill.canon{background:#d6f5e3;color:#116b3a}
.timeline{position:relative;margin-top:8px;padding-left:20px;border-left:2px solid #dbe1ee}
.ev{position:relative;margin:0 0 14px;background:#fff;border:1px solid #e6eaf2;border-left:4px solid #94a3b8;border-radius:10px;padding:11px 14px;box-shadow:0 1px 2px rgba(20,30,60,.04)}
.ev::before{content:"";position:absolute;left:-27px;top:16px;width:10px;height:10px;border-radius:50%;background:#94a3b8;border:2px solid #fff}
.ev .t{font-weight:600}
.ev .when{float:right;color:#8a93a6;font-size:12px;font-weight:400}
.ev.lead{border-left-color:#2563eb}.ev.lead::before{background:#2563eb}
.ev.msg-user{border-left-color:#64748b}.ev.msg-user::before{background:#64748b}
.ev.msg-assistant{border-left-color:#16a34a}.ev.msg-assistant::before{background:#16a34a}
.ev.quote{border-left-color:#d97706}.ev.quote::before{background:#d97706}
.ev.outbox{border-left-color:#7c3aed}.ev.outbox::before{background:#7c3aed}
.ev.integration{border-left-color:#0891b2}.ev.integration::before{background:#0891b2}
.meta{color:#5b6472;font-size:13px;margin-top:3px}
.reason{color:#5b6472;font-size:13px;margin-top:3px;font-style:italic}
.bubble{margin-top:5px;white-space:pre-wrap}
.cols{display:flex;gap:12px;margin-top:6px;flex-wrap:wrap}
.cols>div{flex:1 1 320px;min-width:0}
.json{background:#0f172a;color:#c7d2fe;padding:9px 11px;border-radius:7px;overflow-x:auto;font-size:12px;margin:4px 0 0;white-space:pre-wrap;word-break:break-word}
.empty{color:#8a93a6;padding:20px 0}
"""


def render_html(journey: dict) -> str:
    """HTML autocontido da jornada. Todos os campos de usuário já escapados em `_events`/aqui."""
    email = _esc(journey.get("email"))
    resolved = _esc(journey.get("resolved_lead_id"))
    canon = journey.get("canonical_identity")
    canon_pill = '<span class="pill canon">identidade canônica</span>' if canon else \
        '<span class="pill">sem identidade verificada (fallback: lead mais recente)</span>'
    n_leads = len(journey.get("leads", []))
    n_msgs = sum(len(s.get("messages", [])) for s in journey.get("chat_sessions", []))
    n_events = len(journey.get("integration_events", []))
    header = (
        f"<h1>Jornada — {email}</h1>"
        f'<p class="sub">lead resolvido <code>{resolved}</code> · {n_leads} lead(s) · '
        f"{n_msgs} mensagem(ns) · {n_events} evento(s) de integração<br>{canon_pill}</p>"
    )
    events = _events(journey)
    if events:
        rows = "".join(
            f'<div class="ev {_esc(ev["kind"])}">'
            f'<span class="when">{_fmt_ts(ev.get("ts"))}</span>'
            f'<div class="t">{ev["title"]}</div>{ev["body"]}</div>'
            for ev in events
        )
        body = f'<div class="timeline">{rows}</div>'
    else:
        body = '<div class="empty">Nenhum evento nesta jornada ainda.</div>'
    return (
        "<!doctype html><html lang=pt-br><head><meta charset=utf-8>"
        '<meta name=viewport content="width=device-width,initial-scale=1">'
        f"<title>Jornada — {email}</title><style>{_STYLE}</style></head>"
        f'<body><div class="wrap">{header}{body}</div></body></html>'
    )
