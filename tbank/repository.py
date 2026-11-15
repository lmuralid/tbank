"""Typed access to storage. Converts between documents and domain records."""

from typing import Callable, List, Optional, Type, TypeVar

from .errors import NotFound
from .models import Claim, Commitment, DefaultRecord, Entry, Member, Record
from .storage.base import Storage

MEMBERS = "members"
ENTRIES = "entries"
CLAIMS = "claims"
COMMITMENTS = "commitments"
DEFAULTS = "defaults"
OTPS = "otps"
SESSIONS = "sessions"

T = TypeVar("T", bound=Record)


class Repository:
    def __init__(self, storage: Storage):
        self.storage = storage

    # ----- generic helpers ----------------------------------------------
    def _get(self, collection: str, cls: Type[T], doc_id: str) -> T:
        doc = self.storage.get(collection, doc_id)
        if doc is None:
            raise NotFound(f"{collection[:-1]} {doc_id!r} not found")
        return cls.from_dict(doc)

    def _list(self, collection: str, cls: Type[T],
              where: Optional[Callable[[T], bool]] = None) -> List[T]:
        items = [cls.from_dict(d) for d in self.storage.list(collection)]
        return [i for i in items if where is None or where(i)]

    def _save(self, collection: str, record: Record) -> None:
        self.storage.put(collection, record.id, record.to_dict())

    # ----- members ------------------------------------------------------
    def member(self, member_id: str) -> Member:
        return self._get(MEMBERS, Member, member_id)

    def members(self, where=None) -> List[Member]:
        return self._list(MEMBERS, Member, where)

    def member_by_phone(self, phone: str) -> Optional[Member]:
        found = self.members(lambda m: m.phone == phone)
        return found[0] if found else None

    def save_member(self, member: Member) -> None:
        self._save(MEMBERS, member)

    # ----- ledger entries (append-only) ---------------------------------
    def append_entry(self, entry: Entry) -> None:
        self.storage.append(ENTRIES, entry.id, entry.to_dict())

    def entries(self, where=None) -> List[Entry]:
        return self._list(ENTRIES, Entry, where)

    def entries_for(self, member_id: str) -> List[Entry]:
        return self.entries(
            lambda e: any(p["member_id"] == member_id for p in e.postings)
            or e.meta.get("member_id") == member_id
        )

    # ----- claims -------------------------------------------------------
    def claim(self, claim_id: str) -> Claim:
        return self._get(CLAIMS, Claim, claim_id)

    def claims(self, where=None) -> List[Claim]:
        return self._list(CLAIMS, Claim, where)

    def save_claim(self, claim: Claim) -> None:
        self._save(CLAIMS, claim)

    # ----- commitments --------------------------------------------------
    def commitment(self, commitment_id: str) -> Commitment:
        return self._get(COMMITMENTS, Commitment, commitment_id)

    def commitments(self, where=None) -> List[Commitment]:
        return self._list(COMMITMENTS, Commitment, where)

    def save_commitment(self, commitment: Commitment) -> None:
        self._save(COMMITMENTS, commitment)

    # ----- defaults -----------------------------------------------------
    def default(self, default_id: str) -> DefaultRecord:
        return self._get(DEFAULTS, DefaultRecord, default_id)

    def defaults(self, where=None) -> List[DefaultRecord]:
        return self._list(DEFAULTS, DefaultRecord, where)

    def save_default(self, record: DefaultRecord) -> None:
        self._save(DEFAULTS, record)
