"""Recording, confirming and disputing time given.

Lifecycle::

    pending ──confirm──► confirmed            (credit/debit posted)
       │
       ├──reject──► disputed ──coordinator──► upheld (posted) | dismissed
       │
       └──window ends──► auto_confirmed       (posted; default on confirmer)

The confirmer is the recipient (person cared for, pet owner) or one of the
recipient's guardians. Confirming is their duty: when the window ends the
credit and debit are committed anyway and a default is recorded against them.
"""

from datetime import timedelta
from typing import List, Optional

from .clock import iso, parse
from .context import Context, new_id
from .defaults import DefaultService
from .errors import InvalidOperation, PermissionDenied, ValidationError
from .ledger import Ledger
from .models import (AUTO_CONFIRMED, COMMITTED_STATUSES, CONFIRMATION_DEFAULT,
                     CONFIRMED, DELIVERED, DISMISSED, DISPUTED, EARNED, ETD, FULFILLED,
                     LIVE_COMMITMENT, OPEN, PENDING, UPHELD, Claim)


class ContributionService:
    def __init__(self, ctx: Context, ledger: Ledger, defaults: DefaultService):
        self.ctx = ctx
        self.ledger = ledger
        self.defaults = defaults

    # ----- recording ----------------------------------------------------
    def record(self, provider_id: str, recipient_id: str, label: str,
               hours: float, performed_at: Optional[str] = None,
               note: str = "", commitment_id: Optional[str] = None) -> Claim:
        """The provider records time they gave. It awaits confirmation."""
        cfg = self.ctx.config
        cfg.require_label(label)
        self.ctx.require_active(provider_id)
        self.ctx.require_active(recipient_id)
        if provider_id == recipient_id:
            raise ValidationError("a member cannot give time to themselves")
        if not isinstance(hours, (int, float)) or hours <= 0:
            raise ValidationError("hours must be positive")
        if cfg.max_hours_per_claim and hours > cfg.max_hours_per_claim:
            raise ValidationError(f"at most {cfg.max_hours_per_claim:g} hours per claim")
        if commitment_id:
            self._link_commitment(commitment_id, provider_id, recipient_id, label)
        now = self.ctx.clock.now()
        claim = Claim(
            id=new_id("clm"),
            provider_id=provider_id,
            recipient_id=recipient_id,
            label=label,
            hours=float(hours),
            performed_at=performed_at or iso(now),
            created_at=iso(now),
            confirm_by=iso(now + timedelta(hours=cfg.confirmation_window_hours)),
            note=note,
            commitment_id=commitment_id,
        )
        self.ctx.repo.save_claim(claim)
        if commitment_id:
            commitment = self.ctx.repo.commitment(commitment_id)
            commitment.status = DELIVERED
            commitment.claim_id = claim.id
            self.ctx.repo.save_commitment(commitment)
        return claim

    def _link_commitment(self, commitment_id, provider_id, recipient_id, label):
        commitment = self.ctx.repo.commitment(commitment_id)
        if commitment.status not in LIVE_COMMITMENT:
            raise InvalidOperation(f"commitment is {commitment.status}")
        if (commitment.provider_id, commitment.recipient_id, commitment.label) != (
                provider_id, recipient_id, label):
            raise ValidationError("claim does not match the commitment")

    # ----- confirming ---------------------------------------------------
    def confirm(self, actor_id: str, claim_id: str) -> Claim:
        claim = self._pending(claim_id)
        self._require_confirmer(actor_id, claim)
        return self._commit(claim, CONFIRMED, actor_id)

    def reject(self, actor_id: str, claim_id: str, reason: str) -> Claim:
        """The confirmer disputes the claim. A coordinator will decide."""
        claim = self._pending(claim_id)
        self._require_confirmer(actor_id, claim)
        if not reason:
            raise ValidationError("a reason is required to dispute a claim")
        claim.status = DISPUTED
        claim.reason = reason
        claim.decided_by = actor_id
        claim.decided_at = self.ctx.now_iso()
        self.ctx.repo.save_claim(claim)
        return claim

    def resolve_dispute(self, coordinator_id: str, claim_id: str,
                        uphold: bool, note: str = "") -> Claim:
        """A coordinator settles a disputed claim."""
        self.ctx.require_coordinator(coordinator_id)
        claim = self.ctx.repo.claim(claim_id)
        if claim.status != DISPUTED:
            raise InvalidOperation(f"claim is {claim.status}, not disputed")
        if coordinator_id in (claim.provider_id, claim.recipient_id):
            raise PermissionDenied("a coordinator cannot settle their own dispute")
        if note:
            claim.reason = f"{claim.reason} | coordinator: {note}"
        if uphold:
            return self._commit(claim, UPHELD, coordinator_id)
        claim.status = DISMISSED
        claim.decided_by = coordinator_id
        claim.decided_at = self.ctx.now_iso()
        self.ctx.repo.save_claim(claim)
        if claim.commitment_id:
            commitment = self.ctx.repo.commitment(claim.commitment_id)
            commitment.status = OPEN
            commitment.claim_id = None
            self.ctx.repo.save_commitment(commitment)
        return claim

    def process_expired(self) -> List[Claim]:
        """Commit every pending claim whose confirmation window has ended."""
        now = self.ctx.clock.now()
        done = []
        for claim in self.ctx.repo.claims(lambda c: c.status == PENDING):
            if now > parse(claim.confirm_by):
                self._commit(claim, AUTO_CONFIRMED, "system")
                self.defaults.record(claim.recipient_id, CONFIRMATION_DEFAULT, claim.id)
                done.append(self.ctx.repo.claim(claim.id))
        return done

    # ----- queries ------------------------------------------------------
    def get(self, claim_id: str) -> Claim:
        return self.ctx.repo.claim(claim_id)

    def awaiting(self, actor_id: str) -> List[Claim]:
        """Pending claims this member must confirm (for self or wards)."""
        return [c for c in self.ctx.repo.claims(lambda c: c.status == PENDING)
                if self.ctx.can_act_for(actor_id, c.recipient_id)
                and actor_id != c.provider_id]

    def disputed(self) -> List[Claim]:
        return self.ctx.repo.claims(lambda c: c.status == DISPUTED)

    def for_member(self, member_id: str) -> List[Claim]:
        return self.ctx.repo.claims(
            lambda c: member_id in (c.provider_id, c.recipient_id))

    # ----- internals ----------------------------------------------------
    def _pending(self, claim_id: str) -> Claim:
        claim = self.ctx.repo.claim(claim_id)
        if claim.status != PENDING:
            raise InvalidOperation(f"claim is {claim.status}, not pending")
        return claim

    def _require_confirmer(self, actor_id: str, claim: Claim) -> None:
        if actor_id == claim.provider_id:
            raise PermissionDenied("the provider cannot confirm their own claim")
        self.ctx.require_act_for(actor_id, claim.recipient_id)

    def _commit(self, claim: Claim, status: str, actor_id: str) -> Claim:
        if claim.status in COMMITTED_STATUSES:
            raise InvalidOperation("claim already committed")
        provider = self.ctx.repo.member(claim.provider_id)
        first_volunteer = provider.etd_label is None
        postings = self.ledger.plan_debit(claim.recipient_id, claim.label, claim.hours)
        bucket = ETD if first_volunteer else EARNED
        postings += self.ledger.plan_credit(claim.provider_id, claim.label,
                                            claim.hours, bucket=bucket)
        entry = self.ledger.post(
            "contribution", actor_id, postings, ref=claim.id,
            meta={"status": status, "first_volunteer_etd": first_volunteer},
        )
        if first_volunteer:
            provider.etd_label = claim.label
            self.ctx.repo.save_member(provider)
        claim.status = status
        claim.entry_id = entry.id
        claim.decided_by = actor_id
        claim.decided_at = self.ctx.now_iso()
        self.ctx.repo.save_claim(claim)
        if claim.commitment_id:
            commitment = self.ctx.repo.commitment(claim.commitment_id)
            commitment.status = FULFILLED
            self.ctx.repo.save_commitment(commitment)
            self.defaults.resolve(commitment.id, "fulfilled")
        return claim
