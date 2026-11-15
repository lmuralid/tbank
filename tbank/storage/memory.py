"""In-memory storage, for unit tests and scripted demos."""

import copy
from typing import Dict, List, Optional

from .base import Document, Storage


class MemoryStorage(Storage):
    def __init__(self):
        self._data: Dict[str, Dict[str, Document]] = {}

    def put(self, collection: str, doc_id: str, data: Document) -> None:
        self._data.setdefault(collection, {})[doc_id] = copy.deepcopy(data)

    def get(self, collection: str, doc_id: str) -> Optional[Document]:
        doc = self._data.get(collection, {}).get(doc_id)
        return copy.deepcopy(doc) if doc is not None else None

    def list(self, collection: str) -> List[Document]:
        return [copy.deepcopy(d) for d in self._data.get(collection, {}).values()]
