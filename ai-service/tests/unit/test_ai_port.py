"""`AiPort` — o único ponto de contato business→ai (DEC-ORB-021). Mockável e determinístico."""
from app.business.ai_port import AiPort, InProcessAiAdapter
from app.business.domain.qualification import QualificationResult


async def test_qualify_is_deterministic_and_typed():
    ai = InProcessAiAdapter()
    kw = dict(has_vehicle=True, has_phone=True, has_zipcode=True, consent=True, source="meta")
    r1, r2 = await ai.qualify(**kw), await ai.qualify(**kw)
    assert isinstance(r1, QualificationResult)
    assert r1 == r2


def test_inprocess_adapter_satisfies_port():
    # runtime_checkable Protocol: o adapter cumpre o contrato do AiPort.
    assert isinstance(InProcessAiAdapter(), AiPort)


async def test_support_echoes_query():
    out = await InProcessAiAdapter().support(query="O seguro cobre roubo?")
    assert "suporte" in out.lower()
