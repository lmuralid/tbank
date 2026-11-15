"""Moving credit between members and settling debt.

* **Transfer** – earned credit moves to any member, without limit. ETD is
  locked to its member and is never transferred.
* **Debt pay-off** – a member uses earned credit to clear their own or
  another member's debt in the same label (or equivalent labels).
* **Money settlement** – members who meet the configured eligibility rule
  (e.g. senior citizens with limited mobility) may clear debt with money.
"""

from typing import List, Optional

from .context import Context
from .errors import InvalidOperation, PermissionDenied, ValidationError
from .ledger import EPS, Ledger
from .models import DEBT, EARNED, ETD, Posting


class SettlementService:
    def __init__(self, ctx: Context, ledger: Ledger):
        self.ctx = ctx
        self.ledger = ledger

    def transfer(self, actor_id: str, from_id: str, to_id: str,
                 label: str, hours: float, note: str = ""):
        """Give earned credit to another member."""
        self.ctx.require_act_for(actor_id, from_id)
        self.ctx.require_active(to_id)
        if from_id == to_id:
            raise ValidationError("cannot transfer to yourself")
        _positive(hours)
        available = self.ledger.bucket(from_id, label, EARNED)
        if hours > available + EPS:
            raise InvalidOperation(
                f"only {available:g} earned hours of {label!r} can be transferred "
                "(ETD is locked to its member)")
        postings = [Posting(from_id, label, EARNED, -hours)]
        postings += self.ledger.plan_credit(to_id, label, hours)
        return self.ledger.post("transfer", actor_id, postings,
                                meta={"from": from_id, "to": to_id, "note": note})

    def pay_off_debt(self, actor_id: str, payer_id: str, debtor_id: str,
                     label: str, hours: float):
        """Clear ``hours`` of the debtor's debt in ``label`` using payer credit.

        A member paying their own debt may draw on earned credit and then
        their ETD. Paying someone else's debt draws only on earned credit.
        """
        self.ctx.require_act_for(actor_id, payer_id)
        self.ctx.require_active(debtor_id)
        _positive(hours)
        owed = self.ledger.bucket(debtor_id, label, DEBT)
        if hours > owed + EPS:
            raise InvalidOperation(f"debtor owes only {owed:g} hours of {label!r}")
        sources = (EARNED, ETD) if payer_id == debtor_id else (EARNED,)
        postings = self._draw(payer_id, label, hours, sources)
        postings.append(Posting(debtor_id, label, DEBT, -hours))
        return self.ledger.post("debt_payoff", actor_id, postings,
                                meta={"payer": payer_id, "debtor": debtor_id})

    def is_money_eligible(self, member_id: str) -> bool:
        member = self.ctx.repo.member(member_id)
        return self.ctx.config.is_money_eligible(member.attributes)

    def settle_in_money(self, actor_id: str, member_id: str, label: str,
                        hours: float, amount: Optional[float] = None,
                        reference: str = ""):
        """An eligible member clears debt with money.

        The member, a guardian or a coordinator (recording a receipt) may do this.
        """
        if not (self.ctx.can_act_for(actor_id, member_id)
                or self._is_coordinator(actor_id)):
            raise PermissionDenied(f"{actor_id} may not settle for {member_id}")
        if not self.is_money_eligible(member_id):
            raise PermissionDenied("member is not eligible to settle in money")
        _positive(hours)
        owed = self.ledger.bucket(member_id, label, DEBT)
        if hours > owed + EPS:
            raise InvalidOperation(f"member owes only {owed:g} hours of {label!r}")
        money = self.ctx.config.money
        if amount is None:
            amount = hours * money.rate(label)
        if amount < 0:
            raise ValidationError("amount cannot be negative")
        return self.ledger.post(
            "money_settlement", actor_id, [Posting(member_id, label, DEBT, -hours)],
            meta={"member_id": member_id, "amount": amount,
                  "currency": money.currency, "reference": reference})

    # ----- internals ----------------------------------------------------
    def _draw(self, member_id: str, label: str, hours: float,
              sources) -> List[Posting]:
        balances = self.ledger.balances(member_id)
        remaining = hours
        postings: List[Posting] = []
        for bucket in sources:
            for lbl in self.ctx.config.spendable_labels(label):
                take = min(self.ledger.bucket(member_id, lbl, bucket, balances), remaining)
                if take > EPS:
                    postings.append(Posting(member_id, lbl, bucket, -take))
                    remaining -= take
        if remaining > EPS:
            raise InvalidOperation(
                f"{member_id} lacks {remaining:g} hours of credit in {label!r}")
        return postings

    def _is_coordinator(self, actor_id: str) -> bool:
        try:
            self.ctx.require_coordinator(actor_id)
            return True
        except PermissionDenied:
            return False


def _positive(hours) -> None:
    if not isinstance(hours, (int, float)) or hours <= 0:
        raise ValidationError("hours must be positive")
