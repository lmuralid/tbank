"""Joining, Earnest Time Deposits, guardians and roles."""

from typing import Any, Dict, List, Optional

from .auth import AuthService, normalize_phone
from .context import Context, new_id
from .errors import InvalidOperation, ValidationError
from .ledger import Ledger
from .models import COORDINATOR, ETD, Member, Posting


class MemberService:
    def __init__(self, ctx: Context, ledger: Ledger, auth: AuthService):
        self.ctx = ctx
        self.ledger = ledger
        self.auth = auth

    def join(self, session_token: str, name: str,
             etd_label: Optional[str] = None,
             etd_hours: Optional[float] = None) -> Member:
        """Create a member for an OTP-verified phone.

        With ``etd_label`` the ETD is granted now as advance time. Without
        it, the member's first confirmed volunteer time becomes their ETD and
        its label becomes the ETD label. The first member to join a community
        becomes its coordinator. Attributes that drive eligibility are set
        later by a coordinator, not self-declared.
        """
        phone = self.auth.phone_for(session_token)
        if self.ctx.repo.member_by_phone(phone) is not None:
            raise InvalidOperation("this mobile number already belongs to a member")
        if not name or not name.strip():
            raise ValidationError("name is required")
        first = not self.ctx.repo.members()
        member = Member(
            id=new_id("mem"),
            name=name.strip(),
            phone=phone,
            joined_at=self.ctx.now_iso(),
            roles=[COORDINATOR] if first else [],
        )
        self.ctx.repo.save_member(member)
        if etd_label is not None:
            hours = self.ctx.config.etd_default_hours if etd_hours is None else etd_hours
            member = self.grant_etd(member.id, member.id, etd_label, hours)
        return member

    def grant_etd(self, actor_id: str, member_id: str, label: str,
                  hours: float) -> Member:
        """Record advance time as a member's ETD. Allowed once per member."""
        member = self.ctx.repo.member(member_id)
        if actor_id != member_id:
            self.ctx.require_coordinator(actor_id)
        if member.etd_label is not None:
            raise InvalidOperation("ETD has already been set for this member")
        self.ctx.config.require_label(label)
        self.ledger.post("etd_grant", actor_id,
                         [Posting(member_id, label, ETD, hours)],
                         meta={"member_id": member_id, "source": "advance"})
        member.etd_label = label
        self.ctx.repo.save_member(member)
        return member

    def get(self, member_id: str) -> Member:
        return self.ctx.repo.member(member_id)

    def list(self) -> List[Member]:
        return self.ctx.repo.members()

    def find(self, ref: str) -> Member:
        """Look a member up by id or mobile number."""
        member = self.ctx.repo.storage.get("members", ref)
        if member is not None:
            return Member.from_dict(member)
        found = self.ctx.repo.member_by_phone(normalize_phone(ref))
        if found is None:
            raise ValidationError(f"no member {ref!r}")
        return found

    def add_guardian(self, actor_id: str, member_id: str, guardian_id: str) -> Member:
        """Let ``guardian_id`` confirm and act for ``member_id``."""
        if actor_id != member_id:
            self.ctx.require_coordinator(actor_id)
        if guardian_id == member_id:
            raise ValidationError("a member cannot be their own guardian")
        self.ctx.repo.member(guardian_id)
        member = self.ctx.repo.member(member_id)
        if guardian_id not in member.guardians:
            member.guardians.append(guardian_id)
            self.ctx.repo.save_member(member)
        return member

    def remove_guardian(self, actor_id: str, member_id: str, guardian_id: str) -> Member:
        if actor_id != member_id:
            self.ctx.require_coordinator(actor_id)
        member = self.ctx.repo.member(member_id)
        member.guardians = [g for g in member.guardians if g != guardian_id]
        self.ctx.repo.save_member(member)
        return member

    def set_attributes(self, actor_id: str, member_id: str,
                       attributes: Dict[str, Any]) -> Member:
        """Attributes (e.g. age, mobility) drive eligibility rules.

        Coordinators set them so members cannot make themselves eligible.
        """
        self.ctx.require_coordinator(actor_id)
        member = self.ctx.repo.member(member_id)
        member.attributes.update(attributes)
        self.ctx.repo.save_member(member)
        return member

    def grant_role(self, actor_id: str, member_id: str, role: str) -> Member:
        self.ctx.require_coordinator(actor_id)
        member = self.ctx.repo.member(member_id)
        if role not in member.roles:
            member.roles.append(role)
            self.ctx.repo.save_member(member)
        return member
