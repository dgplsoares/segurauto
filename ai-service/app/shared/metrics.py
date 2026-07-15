"""Métricas Prometheus (DEC-ORB-016). Set mínimo; cresce por fase."""
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
from starlette.responses import Response

LEADS_CAPTURED = Counter("leads_captured_total", "Total de leads capturados", ["result"])  # created|deduped


def render_metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
