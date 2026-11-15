"""Flat-file storage: one append-only JSON-lines file per collection.

Every write appends a line ``{"id": ..., "data": ...}``. On read, the last
line for an id wins, so the files double as a full audit trail. No server or
infrastructure is needed; files are human-readable.
"""

import json
import os
from typing import Dict, List, Optional

from ..errors import ValidationError
from .base import Document, Storage


class JsonFileStorage(Storage):
    def __init__(self, directory: str):
        self.directory = directory
        os.makedirs(directory, exist_ok=True)
        self._cache: Dict[str, tuple] = {}

    def _path(self, collection: str) -> str:
        if not collection.replace("_", "").isalnum():
            raise ValidationError(f"bad collection name {collection!r}")
        return os.path.join(self.directory, f"{collection}.jsonl")

    def _load(self, collection: str) -> Dict[str, Document]:
        path = self._path(collection)
        if not os.path.exists(path):
            return {}
        stamp = os.stat(path)
        key = (stamp.st_mtime_ns, stamp.st_size)
        cached = self._cache.get(collection)
        if cached and cached[0] == key:
            return cached[1]
        docs: Dict[str, Document] = {}
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    row = json.loads(line)
                    docs[row["id"]] = row["data"]  # first position, latest data
        self._cache[collection] = (key, docs)
        return docs

    def put(self, collection: str, doc_id: str, data: Document) -> None:
        line = json.dumps({"id": doc_id, "data": data}, sort_keys=True)
        with open(self._path(collection), "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        self._cache.pop(collection, None)

    def get(self, collection: str, doc_id: str) -> Optional[Document]:
        doc = self._load(collection).get(doc_id)
        return json.loads(json.dumps(doc)) if doc is not None else None

    def list(self, collection: str) -> List[Document]:
        return json.loads(json.dumps(list(self._load(collection).values())))
