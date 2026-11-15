"""tbank: a time bank for communities.

Members give time to one another; every hour given is recorded and later
repaid by someone else in the community. See docs/design.md.
"""

from .auth import ConsoleSender, FileSender, MemorySender
from .bank import TimeBank
from .clock import FixedClock, SystemClock
from .config import CommunityConfig, MoneyConfig
from .errors import (AuthError, InvalidOperation, NotFound, PermissionDenied,
                     TBankError, ValidationError)
from .storage import JsonFileStorage, MemoryStorage, SqliteStorage, open_storage

__version__ = "0.1.0"

__all__ = [
    "TimeBank", "CommunityConfig", "MoneyConfig",
    "MemoryStorage", "JsonFileStorage", "SqliteStorage", "open_storage",
    "ConsoleSender", "FileSender", "MemorySender",
    "SystemClock", "FixedClock",
    "TBankError", "AuthError", "InvalidOperation", "NotFound",
    "PermissionDenied", "ValidationError",
]
