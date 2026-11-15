"""The append-only time ledger.

Balances are never stored; they are always the sum of postings in ledger
entries. Each member has, per label, three buckets: ETD, earned and debt.

Spending order when a member receives time under a label:
  1. earned credit (the label, then equivalent labels)
  2. ETD (the label, then equivalent labels)
  3. debt on the label (subject to the configured debt limit, if any)

Crediting a member under a label first repays any debt in that label (and
equivalent labels) when ``auto_repay_debt`` is on; the rest becomes earned.
"""

from collections import defaultdict
from typing import Dict, Iterable, List, Optional

from .context import Context, new_id
from .errors import InvalidOperation, ValidationError
from .models import BUCKETS, DEBT, EARNED, ETD, Entry, Posting

EPS = 1e-9

Balances = Dict[str, Dict[str, float]]


def _r(value: float) -> float:
    return round(value + 0.0, 6)


class Ledger:
    def __init__(self, ctx: Context):
        self.ctx = ctx

    # ----- reading ------------------------------------------------------
    def balances(self, member_id: str) -> Balances:
        """{label: {"etd": h, "earned": h, "debt": h}} for one member."""
        result: Balances = defaultdict(lambda: {b: 0.0 for b in BUCKETS})
        for entry in self.ctx.repo.entries_for(member_id):
            for p in entry.postings:
                if p["member_id"] == member_id:
                    result[p["label"]][p["bucket"]] += p["hours"]
        return {label: {b: _r(v) for b, v in buckets.items()}
                for label, buckets in result.items()}

    def bucket(self, member_id: str, label: str, bucket: str,
               balances: Optional[Balances] = None) -> float:
        balances = self.balances(member_id) if balances is None else balances
        return balances.get(label, {}).get(bucket, 0.0)

    def totals(self, member_id: str) -> Dict[str, float]:
        totals = {b: 0.0 for b in BUCKETS}
        for buckets in self.balances(member_id).values():
            for b, v in buckets.items():
                totals[b] += v
        totals = {b: _r(v) for b, v in totals.items()}
        totals["net"] = _r(totals[ETD] + totals[EARNED] - totals[DEBT])
        return totals

    def etd_granted(self, member_id: str) -> float:
        """Total ETD ever credited to a member (used for debt limits)."""
        total = 0.0
        for entry in self.ctx.repo.entries_for(member_id):
            for p in entry.postings:
                if (p["member_id"] == member_id and p["bucket"] == ETD
                        and p["hours"] > 0):
                    total += p["hours"]
        return _r(total)

    def history(self, member_id: str) -> List[Entry]:
        return self.ctx.repo.entries_for(member_id)

    # ----- planning -----------------------------------------------------
    def plan_debit(self, member_id: str, label: str, hours: float) -> List[Posting]:
        """Postings that charge ``hours`` of ``label`` to a member."""
        _require_positive(hours)
        balances = self.balances(member_id)
        labels = self.ctx.config.spendable_labels(label)
        remaining = hours
        postings: List[Posting] = []
        for bucket in (EARNED, ETD):
            for lbl in labels:
                available = self.bucket(member_id, lbl, bucket, balances)
                take = min(available, remaining)
                if take > EPS:
                    postings.append(Posting(member_id, lbl, bucket, -_r(take)))
                    remaining -= take
        if remaining > EPS:
            self.check_debt_limit(member_id, remaining, balances)
            postings.append(Posting(member_id, label, DEBT, _r(remaining)))
        return postings

    def plan_credit(self, member_id: str, label: str, hours: float,
                    bucket: str = EARNED) -> List[Posting]:
        """Postings that give ``hours`` of ``label`` to a member."""
        _require_positive(hours)
        self.ctx.config.require_label(label)
        remaining = hours
        postings: List[Posting] = []
        if bucket == EARNED and self.ctx.config.auto_repay_debt:
            balances = self.balances(member_id)
            for lbl in self.ctx.config.spendable_labels(label):
                owed = self.bucket(member_id, lbl, DEBT, balances)
                repay = min(owed, remaining)
                if repay > EPS:
                    postings.append(Posting(member_id, lbl, DEBT, -_r(repay)))
                    remaining -= repay
        if remaining > EPS:
            postings.append(Posting(member_id, label, bucket, _r(remaining)))
        return postings

    def check_debt_limit(self, member_id: str, extra: float,
                         balances: Optional[Balances] = None) -> None:
        limit = self.ctx.config.debt_limit_hours(self.etd_granted(member_id))
        if limit is None:
            return
        balances = self.balances(member_id) if balances is None else balances
        current = sum(b.get(DEBT, 0.0) for b in balances.values())
        if current + extra > limit + EPS:
            raise InvalidOperation(
                f"debt limit exceeded for {member_id}: "
                f"{current:g} + {extra:g} > {limit:g} hours"
            )

    # ----- writing ------------------------------------------------------
    def post(self, kind: str, actor_id: str, postings: Iterable[Posting],
             ref: Optional[str] = None, meta: Optional[dict] = None) -> Entry:
        """Validate and append one entry. Buckets may never go negative."""
        postings = list(postings)
        meta = dict(meta or {})
        if not postings and not meta:
            raise ValidationError("an entry needs postings or meta data")
        projected: Dict[tuple, float] = {}
        for p in postings:
            if p.bucket not in BUCKETS:
                raise ValidationError(f"unknown bucket {p.bucket!r}")
            self.ctx.config.require_label(p.label)
            if abs(p.hours) <= EPS:
                raise ValidationError("posting hours must be non-zero")
            key = (p.member_id, p.label, p.bucket)
            if key not in projected:
                projected[key] = self.bucket(p.member_id, p.label, p.bucket)
            projected[key] += p.hours
        for (member_id, label, bucket), value in projected.items():
            if value < -EPS:
                raise InvalidOperation(
                    f"{member_id} would have negative {bucket} in {label!r}"
                )
        entry = Entry(
            id=new_id("ent"),
            kind=kind,
            at=self.ctx.now_iso(),
            actor_id=actor_id,
            postings=[p.to_dict() for p in postings],
            ref=ref,
            meta=meta,
        )
        self.ctx.repo.append_entry(entry)
        return entry


def _require_positive(hours: float) -> None:
    if not isinstance(hours, (int, float)) or hours <= 0:
        raise ValidationError(f"hours must be a positive number, got {hours!r}")
