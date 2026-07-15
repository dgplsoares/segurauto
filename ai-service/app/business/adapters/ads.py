"""Plataformas de anúncios fake (Meta/Google): eventos de conversão idempotentes por `event_id`
(DEC-ORB-014). Enviar a MESMA conversão duas vezes → a segunda é deduplicada.
"""
from app.business.ports import ConversionResult


class _FakeAds:
    platform = "generic"

    def __init__(self) -> None:
        self._sent: set[str] = set()
        self.events: list[dict] = []

    async def send_conversion(
        self, *, event_id: str, lead_id: str, value: float | None = None
    ) -> ConversionResult:
        if event_id in self._sent:
            return ConversionResult(event_id=event_id, deduped=True)
        self._sent.add(event_id)
        self.events.append(
            {"event_id": event_id, "lead_id": lead_id, "value": value, "platform": self.platform}
        )
        return ConversionResult(event_id=event_id, deduped=False)


class FakeMetaAds(_FakeAds):
    platform = "meta"


class FakeGoogleAds(_FakeAds):
    platform = "google"
