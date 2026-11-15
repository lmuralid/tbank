"""Pluggable storage adapters."""

import os

from ..errors import ValidationError
from .base import Storage
from .jsonfile import JsonFileStorage
from .memory import MemoryStorage
from .sqlite import SqliteStorage

__all__ = ["Storage", "MemoryStorage", "JsonFileStorage", "SqliteStorage", "open_storage"]


def open_storage(kind: str, location: str = "") -> Storage:
    """Open a storage adapter by name: ``memory``, ``jsonl`` or ``sqlite``.

    For ``jsonl`` the location is a directory; for ``sqlite`` it is a
    directory (a ``tbank.db`` file is created in it) or a ``.db`` file path.
    """
    if kind == "memory":
        return MemoryStorage()
    if kind == "jsonl":
        return JsonFileStorage(location)
    if kind == "sqlite":
        if not location.endswith(".db"):
            os.makedirs(location, exist_ok=True)
            location = os.path.join(location, "tbank.db")
        return SqliteStorage(location)
    raise ValidationError(f"unknown storage kind {kind!r}")
