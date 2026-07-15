"""Qualificação do lead — saída estruturada e parte determinística (DEC-ORB-008/021).

Vive em `shared/` porque é o **contrato comum** entre `business` (que persiste o resultado) e `ai` (que o
produz/refina): assim o `ai` não importa nada de `business` (cross-import `ai→business` = 0, DEC-ORB-021).
A rubrica é a base previsível do score (testável sem LLM); na Fase 3 o agente refina/explica.
"""
from dataclasses import dataclass
from enum import Enum


class QualificationBand(str, Enum):
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"


@dataclass(frozen=True)
class QualificationResult:
    score: int  # 0..100
    band: QualificationBand
    reason: str


def band_for(score: int) -> QualificationBand:
    if score >= 70:
        return QualificationBand.HOT
    if score >= 40:
        return QualificationBand.WARM
    return QualificationBand.COLD


def rubric_score(
    *,
    has_vehicle: bool,
    has_phone: bool,
    has_zipcode: bool,
    consent: bool,
    source: str | None,
) -> QualificationResult:
    """Score determinístico por sinais do lead. Soma limitada a 100."""
    score = 0
    reasons: list[str] = []
    if consent:
        score += 20
        reasons.append("consentimento")
    if has_phone:
        score += 25
        reasons.append("telefone")
    if has_vehicle:
        score += 25
        reasons.append("veiculo")
    if has_zipcode:
        score += 15
        reasons.append("cep")
    if source and source.lower() in {"meta", "google", "ads"}:
        score += 15
        reasons.append(f"origem:{source.lower()}")
    score = min(score, 100)
    return QualificationResult(score=score, band=band_for(score), reason="+".join(reasons) or "sem-sinais")
