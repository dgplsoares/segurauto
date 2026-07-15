"""Contrato dos adapters fake — a dedup/idempotência precisa estar no fake, senão o teste não prova
nada (DEC-ORB-014)."""
from app.business.adapters.ads import FakeGoogleAds, FakeMetaAds
from app.business.adapters.crm import FakeCrm
from app.business.domain.events import conversion_event_id


async def test_crm_upsert_is_idempotent():
    crm = FakeCrm()
    args = dict(name="Ana", email="a@x.com", phone="1", vehicle="Onix", zipcode="01001000", score=80, band="hot")
    r1 = await crm.upsert_lead(lead_id="lead-1", **args)
    r2 = await crm.upsert_lead(lead_id="lead-1", **args)
    assert r1.created is True
    assert r2.created is False            # 2º upsert não duplica
    assert r1.external_id == r2.external_id
    assert crm.calls == 2


async def test_crm_price_quote_deterministic():
    crm = FakeCrm()
    q1 = await crm.price_quote(vehicle="Onix", zipcode="01001000")
    q2 = await crm.price_quote(vehicle="Onix", zipcode="01001000")
    assert q1 == q2
    assert q1["currency"] == "BRL"
    assert q1["annual_premium"] > 0


async def test_ads_conversion_dedup_by_event_id():
    ads = FakeMetaAds()
    eid = conversion_event_id("lead-1", "meta")
    r1 = await ads.send_conversion(event_id=eid, lead_id="lead-1")
    r2 = await ads.send_conversion(event_id=eid, lead_id="lead-1")
    assert r1.deduped is False
    assert r2.deduped is True             # mesma conversão não conta 2x
    assert len(ads.events) == 1


def test_event_id_stable_and_platform_scoped():
    assert conversion_event_id("lead-1", "meta") == conversion_event_id("lead-1", "meta")
    assert conversion_event_id("lead-1", "meta") != conversion_event_id("lead-1", "google")


def test_ads_platforms_distinct():
    assert FakeMetaAds().platform == "meta"
    assert FakeGoogleAds().platform == "google"
