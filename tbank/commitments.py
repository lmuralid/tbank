"""Promised time, and what happens when a promise is not kept.

A commitment is a provider's promise to give a recipient some hours under a
label by a due date. When the provider cannot keep it they may:

* **Cover for me** – pass the commitment to another member, who accepts it.
* **Buy out** – clear it with money.

A commitment not delivered by its due date plus the grace period becomes a
default against the provider; it can still be covered or bought out.
"""

from datetime import timedelta
from typing import List, Optional

from .clock import iso, parse
from .context import Context, new_id
from .defaults import DefaultService
from .errors import InvalidOperation, PermissionDenied, ValidationError
from .ledger import Ledger
from .models import (BOUGHT_OUT, CANCELLED, COMMITMENT_DEFAULT,
                     COVER_REQUESTED, DEFAULTED, LIVE_COMMITMENT, OPEN,
                     Commitment)


class CommitmentService:
    def __init__(self, ctx: Context, ledger: Ledger, defaults: DefaultService):
        self.ctx = ctx
        self.ledger = ledger
        self.defaults = defaults

    def create(self, actor_id: str, provider_id: str, recipient_id: str,
               label: str, hours: float, due_at: str) -> Commitment:
        """Either party (or a guardian) may set up the commitment."""
        self.ctx.config.require_label(label)
        if not (self.ctx.can_act_for(actor_id, provider_id)
                or self.ctx.can_act_for(actor_id, recipient_id)):
            raise PermissionDenied("only the provider or recipient may commit")
        if provider_id == recipient_id:
            raise ValidationError("provider and recipient must differ")
        if not isinstance(hours, (int, float)) or hours <= 0:
            raise ValidationError("hours must be positive")
        self.ctx.require_active(provider_id)
        self.ctx.require_active(recipient_id)
        parse(due_at)
        commitment = Commitment(
            id=new_id("cmt"), provider_id=provider_id, recipient_id=recipient_id,
            label=label, hours=float(hours), due_at=due_at,
            created_at=self.ctx.now_iso(),
        )
        self._log(commitment, actor_id, "created")
        self.ctx.repo.save_commitment(commitment)
        return commitment

    # ----- cover for me -------------------------------------------------
    def request_cover(self, actor_id: str, commitment_id: str,
                      to_member_id: Optional[str] = None) -> Commitment:
        """The provider asks someone (or anyone, if None) to cover for them."""
        commitment = self._live(commitment_id)
        self.ctx.require_act_for(actor_id, commitment.provider_id)
        if to_member_id in (commitment.provider_id, commitment.recipient_id):
            raise ValidationError("cover must come from a third member")
        if to_member_id:
            self.ctx.require_active(to_member_id)
        commitment.status = COVER_REQUESTED
        commitment.cover_offered_to = to_member_id
        self._log(commitment, actor_id, "cover_requested", to=to_member_id)
        self.ctx.repo.save_commitment(commitment)
        return commitment

    def accept_cover(self, member_id: str, commitment_id: str) -> Commitment:
        """A member takes over the commitment and becomes its provider."""
        commitment = self.ctx.repo.commitment(commitment_id)
        if commitment.status != COVER_REQUESTED:
            raise InvalidOperation("no cover has been requested")
        if commitment.cover_offered_to not in (None, member_id):
            raise PermissionDenied("cover was offered to another member")
        if member_id in (commitment.provider_id, commitment.recipient_id):
            raise ValidationError("cover must come from a third member")
        self.ctx.require_active(member_id)
        previous = commitment.provider_id
        commitment.provider_id = member_id
        commitment.status = OPEN
        commitment.cover_offered_to = None
        self._log(commitment, member_id, "covered", previous_provider=previous)
        self.ctx.repo.save_commitment(commitment)
        self.defaults.resolve(commitment.id, f"covered by {member_id}")
        return commitment

    # ----- buyout -------------------------------------------------------
    def buyout(self, actor_id: str, commitment_id: str,
               amount: Optional[float] = None, reference: str = "") -> Commitment:
        """Clear the commitment with money paid by the provider."""
        commitment = self._live(commitment_id)
        if not (self.ctx.can_act_for(actor_id, commitment.provider_id)
                or self._is_coordinator(actor_id)):
            raise PermissionDenied("only the provider or a coordinator may buy out")
        money = self.ctx.config.money
        if amount is None:
            amount = commitment.hours * money.rate(commitment.label)
        if amount < 0:
            raise ValidationError("amount cannot be negative")
        self.ledger.post("buyout", actor_id, [], ref=commitment.id, meta={
            "member_id": commitment.provider_id, "label": commitment.label,
            "hours": commitment.hours, "amount": amount,
            "currency": money.currency, "reference": reference,
        })
        commitment.status = BOUGHT_OUT
        self._log(commitment, actor_id, "bought_out", amount=amount)
        self.ctx.repo.save_commitment(commitment)
        self.defaults.resolve(commitment.id, "bought out")
        return commitment

    # ----- missing and cancelling ---------------------------------------
    def mark_missed(self, actor_id: str, commitment_id: str) -> Commitment:
        """The recipient (or a coordinator) reports the time was not given."""
        commitment = self._live(commitment_id)
        if not (self.ctx.can_act_for(actor_id, commitment.recipient_id)
                or self._is_coordinator(actor_id)):
            raise PermissionDenied("only the recipient or a coordinator may report")
        return self._default(commitment, actor_id)

    def process_overdue(self) -> List[Commitment]:
        """Default every open commitment past its due date plus grace."""
        grace = timedelta(hours=self.ctx.config.commitment_grace_hours)
        now = self.ctx.clock.now()
        done = []
        for c in self.ctx.repo.commitments(lambda c: c.status in (OPEN, COVER_REQUESTED)):
            if now > parse(c.due_at) + grace:
                done.append(self._default(c, "system"))
        return done

    def cancel(self, actor_id: str, commitment_id: str) -> Commitment:
        """The recipient no longer needs the time. No default is recorded."""
        commitment = self._live(commitment_id)
        self.ctx.require_act_for(actor_id, commitment.recipient_id)
        commitment.status = CANCELLED
        self._log(commitment, actor_id, "cancelled")
        self.ctx.repo.save_commitment(commitment)
        self.defaults.resolve(commitment.id, "cancelled by recipient")
        return commitment

    # ----- queries ------------------------------------------------------
    def get(self, commitment_id: str) -> Commitment:
        return self.ctx.repo.commitment(commitment_id)

    def for_member(self, member_id: str) -> List[Commitment]:
        return self.ctx.repo.commitments(
            lambda c: member_id in (c.provider_id, c.recipient_id))

    def open_cover_requests(self, member_id: str) -> List[Commitment]:
        return self.ctx.repo.commitments(
            lambda c: c.status == COVER_REQUESTED
            and c.cover_offered_to in (None, member_id)
            and member_id not in (c.provider_id, c.recipient_id))

    # ----- internals ----------------------------------------------------
    def _live(self, commitment_id: str) -> Commitment:
        commitment = self.ctx.repo.commitment(commitment_id)
        if commitment.status not in LIVE_COMMITMENT:
            raise InvalidOperation(f"commitment is {commitment.status}")
        return commitment

    def _default(self, commitment: Commitment, actor_id: str) -> Commitment:
        if commitment.status == DEFAULTED:
            return commitment
        commitment.status = DEFAULTED
        self._log(commitment, actor_id, "defaulted")
        self.ctx.repo.save_commitment(commitment)
        self.defaults.record(commitment.provider_id, COMMITMENT_DEFAULT, commitment.id)
        return commitment

    def _is_coordinator(self, actor_id: str) -> bool:
        try:
            self.ctx.require_coordinator(actor_id)
            return True
        except PermissionDenied:
            return False

    def _log(self, commitment: Commitment, actor_id: str, event: str, **extra):
        commitment.history.append(
            {"at": self.ctx.now_iso(), "actor_id": actor_id, "event": event, **extra})
