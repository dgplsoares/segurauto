"""F6 (DEC-ORB-045) — partes puras: `action_event_id`, o `NotificationPort` fake e a sanitização do click_id."""
from app.business.adapters.notification import FakeNotification, _mask
from app.business.api.schemas import LeadCreate
from app.business.domain.events import action_event_id, conversion_event_id


def test_action_event_id_stable_and_distinct():
    a = action_event_id("sess1", "contract", "meta")
    assert a == action_event_id("sess1", "contract", "meta")   # estável
    assert a != action_event_id("sess1", "contract", "google")  # por plataforma
    assert a != action_event_id("sess2", "contract", "meta")    # por sessão
    assert a != conversion_event_id("sess1", "meta")            # distinto da conversão de qualify (não deduplicam)


def test_mask_handles_email_and_phone():
    assert _mask("ana@example.com").startswith("an") and "example" not in _mask("ana@example.com")
    assert _mask("11999998888") == "***8888"  # telefone: só os últimos 4
    assert _mask("") == "-"


async def test_notify_returns_deterministic_id_and_records_without_pii():
    n = FakeNotification()
    mid1 = await n.notify(channel="whatsapp", to="11999998888", template="quote_confirmation")
    mid2 = await n.notify(channel="whatsapp", to="11999998888", template="quote_confirmation")
    assert mid1 == mid2 and mid1.startswith("whatsapp_")  # determinístico por (canal, destino, template)
    assert n.sent == [{"channel": "whatsapp", "template": "quote_confirmation"}] * 2  # sem destino cru


def test_leadcreate_sanitizes_click_id():
    m = LeadCreate(
        name="A", email="a@b.com", phone="11999998888", vehicle="Onix", zipcode="01001000",
        consent=True, click_id="gclid.ABC-123<x>",
    )
    assert m.click_id == "gclid.ABC-123x"  # < e > removidos; só charset seguro sobrevive
    assert "<" not in m.click_id and ">" not in m.click_id
