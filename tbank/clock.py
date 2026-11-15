"""Time sources. Injecting a clock keeps expiry rules testable."""

from datetime import datetime, timedelta, timezone


def iso(dt: datetime) -> str:
    """Format a datetime as an ISO-8601 UTC string."""
    return dt.astimezone(timezone.utc).isoformat()


def parse(value: str) -> datetime:
    """Parse an ISO-8601 string; naive values are treated as UTC."""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class SystemClock:
    """Real wall-clock time in UTC."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FixedClock:
    """A manually driven clock for tests and scripted demos."""

    def __init__(self, start: datetime = None):
        self._now = start or datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self._now

    def advance(self, **kwargs) -> datetime:
        """Move time forward, e.g. advance(hours=49)."""
        self._now = self._now + timedelta(**kwargs)
        return self._now
