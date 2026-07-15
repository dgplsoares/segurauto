"""`AiPort` — o único ponto de contato business→ai (DEC-ORB-021). Mockável e determinístico."""
from app.business.ai_port import AiPort, InProcessAiAdapter
from app.shared.qualification import QualificationResult


async def test_qualify_is_deterministic_and_typed():
    ai = InProcessAiAdapter()
    kw = dict(has_vehicle=True, has_phone=True, has_zipcode=True, consent=True, source="meta")
    r1, r2 = await ai.qualify(**kw), await ai.qualify(**kw)
    assert isinstance(r1, QualificationResult)
    assert r1 == r2


def test_inprocess_adapter_satisfies_port():
    # runtime_checkable Protocol: o adapter cumpre o contrato do AiPort.
    assert isinstance(InProcessAiAdapter(), AiPort)
    # `support` agora lê o RAG (precisa de sessão) → testado em integração (test_support_flow.py).
