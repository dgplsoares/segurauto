"""Entidade de domínio `Lead` e sua máquina de estados (pura, sem SQLAlchemy)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from app.business.domain.qualification import QualificationBand, QualificationResult


class LeadStatus(str, Enum):
    RECEIVED = "received"
    QUALIFYING = "qualifying"
    QUALIFIED = "qualified"
    SYNCED = "synced"
    FAILED = "failed"


# Transições válidas do funil (o Kanban da V2 lê/atualiza estes estados — DEC-ORB-020).
_ALLOWED: dict[LeadStatus, set[LeadStatus]] = {
    LeadStatus.RECEIVED: {LeadStatus.QUALIFYING, LeadStatus.FAILED},
    LeadStatus.QUALIFYING: {LeadStatus.QUALIFIED, LeadStatus.FAILED},
    LeadStatus.QUALIFIED: {LeadStatus.SYNCED, LeadStatus.FAILED},
    LeadStatus.SYNCED: set(),
    LeadStatus.FAILED: set(),
}


class InvalidTransition(Exception):
    pass


def can_transition(src: LeadStatus, dst: LeadStatus) -> bool:
    return dst in _ALLOWED[src]


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Lead:
    idempotency_key: str
    name: str
    email: str
    phone: str
    vehicle: str
    zipcode: str
    consent: bool
    source: str | None = None
    click_id: str | None = None  # gclid/fbclid capturado na LP (F6) — atribuição de campanha
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: LeadStatus = LeadStatus.RECEIVED
    score: int | None = None
    band: QualificationBand | None = None
    reason: str | None = None
    created_at: datetime = field(default_factory=_now)

    def transition_to(self, dst: LeadStatus) -> None:
        if not can_transition(self.status, dst):
            raise InvalidTransition(f"transição inválida: {self.status.value} -> {dst.value}")
        self.status = dst

    def apply_qualification(self, result: QualificationResult) -> None:
        """Aplica o resultado da qualificação e avança received/qualifying -> qualified."""
        if self.status == LeadStatus.RECEIVED:
            self.transition_to(LeadStatus.QUALIFYING)
        self.score = result.score
        self.band = result.band
        self.reason = result.reason
        self.transition_to(LeadStatus.QUALIFIED)
