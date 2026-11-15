"""Domain records. All are plain dataclasses that round-trip through dicts."""

from dataclasses import asdict, dataclass, field, fields
from typing import Any, Dict, List, Optional

# Balance buckets held per member per label.
ETD = "etd"          # Earnest Time Deposit: starting credit, locked to member
EARNED = "earned"    # credit earned from confirmed contributions
DEBT = "debt"        # hours owed (stored as a positive number)
BUCKETS = (ETD, EARNED, DEBT)

COORDINATOR = "coordinator"


class Record:
    """Mixin giving dataclasses dict conversion."""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in names})


@dataclass
class Member(Record):
    id: str
    name: str
    phone: str
    joined_at: str
    roles: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    guardians: List[str] = field(default_factory=list)
    etd_label: Optional[str] = None
    active: bool = True

    def has_role(self, role: str) -> bool:
        return role in self.roles


@dataclass
class Posting(Record):
    """One change to one bucket of one member's balance."""

    member_id: str
    label: str
    bucket: str
    hours: float


@dataclass
class Entry(Record):
    """An immutable ledger entry. Balances are the sum of all postings."""

    id: str
    kind: str
    at: str
    actor_id: str
    postings: List[Dict[str, Any]] = field(default_factory=list)
    ref: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def posting_objects(self) -> List[Posting]:
        return [Posting.from_dict(p) for p in self.postings]


# Claim statuses
PENDING = "pending"
CONFIRMED = "confirmed"
AUTO_CONFIRMED = "auto_confirmed"
DISPUTED = "disputed"
UPHELD = "upheld"
DISMISSED = "dismissed"
COMMITTED_STATUSES = (CONFIRMED, AUTO_CONFIRMED, UPHELD)


@dataclass
class Claim(Record):
    """Time a provider says they gave a recipient, awaiting confirmation."""

    id: str
    provider_id: str
    recipient_id: str
    label: str
    hours: float
    performed_at: str
    created_at: str
    confirm_by: str
    status: str = PENDING
    note: str = ""
    commitment_id: Optional[str] = None
    decided_by: Optional[str] = None
    decided_at: Optional[str] = None
    reason: str = ""
    entry_id: Optional[str] = None


# Commitment statuses
OPEN = "open"
COVER_REQUESTED = "cover_requested"
DELIVERED = "delivered"
FULFILLED = "fulfilled"
DEFAULTED = "defaulted"
BOUGHT_OUT = "bought_out"
CANCELLED = "cancelled"
LIVE_COMMITMENT = (OPEN, COVER_REQUESTED, DEFAULTED)


@dataclass
class Commitment(Record):
    """A promise by a provider to give time to a recipient by a due date."""

    id: str
    provider_id: str
    recipient_id: str
    label: str
    hours: float
    due_at: str
    created_at: str
    status: str = OPEN
    claim_id: Optional[str] = None
    cover_offered_to: Optional[str] = None
    history: List[Dict[str, Any]] = field(default_factory=list)


# Default kinds
CONFIRMATION_DEFAULT = "confirmation"
COMMITMENT_DEFAULT = "commitment"


@dataclass
class DefaultRecord(Record):
    """A duty a member did not meet."""

    id: str
    member_id: str
    kind: str
    ref: str
    at: str
    resolved: bool = False
    resolution: Optional[str] = None
    resolved_at: Optional[str] = None
