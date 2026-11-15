"""The TimeBank facade: wires configuration, storage and services together."""

from typing import Any, Dict, Optional

from .auth import AuthService, ConsoleSender, OtpSender
from .clock import SystemClock
from .commitments import CommitmentService
from .config import CommunityConfig
from .context import Context
from .contributions import ContributionService
from .defaults import DefaultService
from .ledger import Ledger
from .members import MemberService
from .repository import Repository
from .settlements import SettlementService
from .storage import Storage, open_storage


class TimeBank:
    """One community's time bank.

    Example::

        bank = TimeBank(CommunityConfig.load("config.json"),
                        open_storage("jsonl", "./data"))
        bank.auth.request_otp("+919800000001")
        token = bank.auth.verify_otp("+919800000001", "123456")
        alice = bank.members.join(token, "Alice", etd_label="some/label")
    """

    def __init__(self, config: CommunityConfig, storage: Storage,
                 clock=None, otp_sender: Optional[OtpSender] = None):
        self.config = config
        self.storage = storage
        self.ctx = Context(config=config, repo=Repository(storage),
                           clock=clock or SystemClock())
        self.ledger = Ledger(self.ctx)
        self.defaults = DefaultService(self.ctx)
        self.auth = AuthService(self.ctx, otp_sender or ConsoleSender())
        self.members = MemberService(self.ctx, self.ledger, self.auth)
        self.contributions = ContributionService(self.ctx, self.ledger, self.defaults)
        self.commitments = CommitmentService(self.ctx, self.ledger, self.defaults)
        self.settlements = SettlementService(self.ctx, self.ledger)

    @classmethod
    def open(cls, config_path: str, storage_kind: str, location: str,
             clock=None, otp_sender: Optional[OtpSender] = None) -> "TimeBank":
        return cls(CommunityConfig.load(config_path),
                   open_storage(storage_kind, location), clock, otp_sender)

    def tick(self) -> Dict[str, Any]:
        """Run time-based rules: auto-confirm expired claims, default
        overdue commitments. Call periodically (or before reading balances)."""
        return {
            "auto_confirmed": self.contributions.process_expired(),
            "defaulted": self.commitments.process_overdue(),
        }

    def statement(self, member_id: str) -> Dict[str, Any]:
        """A member's balances, open defaults and pending work."""
        member = self.members.get(member_id)
        return {
            "member": member.to_dict(),
            "balances": self.ledger.balances(member_id),
            "totals": self.ledger.totals(member_id),
            "awaiting_my_confirmation": [c.id for c in self.contributions.awaiting(member_id)],
            "open_defaults": [d.to_dict() for d in
                              self.defaults.for_member(member_id, open_only=True)],
            "money_eligible": self.settlements.is_money_eligible(member_id),
        }

    def close(self) -> None:
        self.storage.close()
