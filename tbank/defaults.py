"""Recording and resolving defaults (duties a member did not meet)."""

from typing import List, Optional

from .context import Context, new_id
from .models import DefaultRecord


class DefaultService:
    def __init__(self, ctx: Context):
        self.ctx = ctx

    def record(self, member_id: str, kind: str, ref: str) -> DefaultRecord:
        record = DefaultRecord(
            id=new_id("def"), member_id=member_id, kind=kind,
            ref=ref, at=self.ctx.now_iso(),
        )
        self.ctx.repo.save_default(record)
        return record

    def resolve(self, ref: str, resolution: str) -> Optional[DefaultRecord]:
        """Mark the open default for ``ref`` as resolved, if there is one."""
        for record in self.ctx.repo.defaults(lambda d: d.ref == ref and not d.resolved):
            record.resolved = True
            record.resolution = resolution
            record.resolved_at = self.ctx.now_iso()
            self.ctx.repo.save_default(record)
            return record
        return None

    def for_member(self, member_id: str, open_only: bool = False) -> List[DefaultRecord]:
        return self.ctx.repo.defaults(
            lambda d: d.member_id == member_id and (not open_only or not d.resolved)
        )
