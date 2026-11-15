"""Shared state handed to every service."""

import uuid
from dataclasses import dataclass

from .clock import iso
from .config import CommunityConfig
from .errors import PermissionDenied
from .models import COORDINATOR, Member
from .repository import Repository


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@dataclass
class Context:
    config: CommunityConfig
    repo: Repository
    clock: object

    def now_iso(self) -> str:
        return iso(self.clock.now())

    # ----- permission helpers -------------------------------------------
    def can_act_for(self, actor_id: str, member_id: str) -> bool:
        """A member may act for themselves; a guardian may act for a ward."""
        if actor_id == member_id:
            return True
        return actor_id in self.repo.member(member_id).guardians

    def require_act_for(self, actor_id: str, member_id: str) -> None:
        if not self.can_act_for(actor_id, member_id):
            raise PermissionDenied(f"{actor_id} may not act for {member_id}")

    def require_coordinator(self, actor_id: str) -> Member:
        actor = self.repo.member(actor_id)
        if not actor.has_role(COORDINATOR):
            raise PermissionDenied(f"{actor_id} is not a coordinator")
        return actor

    def require_active(self, member_id: str) -> Member:
        member = self.repo.member(member_id)
        if not member.active:
            raise PermissionDenied(f"member {member_id} is not active")
        return member
