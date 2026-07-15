"""DEC-ORB-021 — o contexto `ai` é EXTRAÍVEL: não importa nada de `business` (só `shared`/stdlib/libs).

Guarda contra regressão do cross-import — o 8c moveu `QualificationResult` (o único contrato compartilhado)
para `shared/`. Se alguém reintroduzir `from app.business ...` dentro de `app/ai/`, este teste falha.
"""
import pathlib

_AI_DIR = pathlib.Path(__file__).resolve().parents[2] / "app" / "ai"


def test_ai_context_does_not_import_business():
    offenders = [
        str(py.relative_to(_AI_DIR.parents[1]))
        for py in _AI_DIR.rglob("*.py")
        if "from app.business" in py.read_text(encoding="utf-8")
        or "import app.business" in py.read_text(encoding="utf-8")
    ]
    assert offenders == [], f"cross-import ai→business proibido (DEC-ORB-021): {offenders}"
