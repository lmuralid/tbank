"""The storage interface every adapter implements.

Storage is a set of named collections of JSON-compatible documents keyed by
id. The core never talks to a database directly, so a flat file, SQLite or a
hosted database can be swapped in without changing domain code.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ..errors import InvalidOperation

Document = Dict[str, Any]


class Storage(ABC):
    """Abstract document store."""

    @abstractmethod
    def put(self, collection: str, doc_id: str, data: Document) -> None:
        """Insert or replace a document."""

    @abstractmethod
    def get(self, collection: str, doc_id: str) -> Optional[Document]:
        """Return a document or None."""

    @abstractmethod
    def list(self, collection: str) -> List[Document]:
        """Return every document in a collection, in insertion order."""

    def append(self, collection: str, doc_id: str, data: Document) -> None:
        """Insert a document that may never be replaced (append-only data)."""
        if self.get(collection, doc_id) is not None:
            raise InvalidOperation(f"{collection}/{doc_id} already exists")
        self.put(collection, doc_id, data)

    def close(self) -> None:
        """Release resources. Optional for adapters."""
