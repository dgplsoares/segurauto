"""Domínio puro do lead — sem infra (DEC-ORB-006)."""
import pytest

from app.business.domain.lead import InvalidTransition, Lead, LeadStatus
from app.business.domain.qualification import QualificationBand, band_for, rubric_score


def _lead(**kw) -> Lead:
    base = dict(
        idempotency_key="k1", name="Ana", email="a@x.com", phone="11999",
        vehicle="Onix 2020", zipcode="01001000", consent=True,
    )
    base.update(kw)
    return Lead(**base)


def test_new_lead_is_received():
    assert _lead().status is LeadStatus.RECEIVED


def test_valid_transition():
    lead = _lead()
    lead.transition_to(LeadStatus.QUALIFYING)
    assert lead.status is LeadStatus.QUALIFYING


def test_invalid_transition_raises():
    with pytest.raises(InvalidTransition):
        _lead().transition_to(LeadStatus.SYNCED)


def test_apply_qualification_sets_score_and_qualified():
    lead = _lead()
    result = rubric_score(has_vehicle=True, has_phone=True, has_zipcode=True, consent=True, source="meta")
    lead.apply_qualification(result)
    assert lead.status is LeadStatus.QUALIFIED
    assert lead.score == result.score
    assert lead.band is result.band


def test_rubric_is_deterministic_and_bounded():
    kw = dict(has_vehicle=True, has_phone=True, has_zipcode=True, consent=True, source="meta")
    r1, r2 = rubric_score(**kw), rubric_score(**kw)
    assert r1 == r2
    assert 0 <= r1.score <= 100
    assert r1.band is QualificationBand.HOT  # 20+25+25+15+15 = 100


def test_band_thresholds():
    assert band_for(70) is QualificationBand.HOT
    assert band_for(40) is QualificationBand.WARM
    assert band_for(39) is QualificationBand.COLD
