"""SQLite storage: a single local database file, no server needed."""

import json
import sqlite3
from typing import List, Optional

from .base import Document, Storage

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    collection TEXT NOT NULL,
    id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    data TEXT NOT NULL,
    PRIMARY KEY (collection, id)
);
CREATE INDEX IF NOT EXISTS documents_seq ON documents (collection, seq);
"""


class SqliteStorage(Storage):
    def __init__(self, path: str):
        self.path = path
        self._conn = sqlite3.connect(path)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def put(self, collection: str, doc_id: str, data: Document) -> None:
        payload = json.dumps(data, sort_keys=True)
        with self._conn:
            row = self._conn.execute(
                "SELECT seq FROM documents WHERE collection=? AND id=?",
                (collection, doc_id),
            ).fetchone()
            if row:
                self._conn.execute(
                    "UPDATE documents SET data=? WHERE collection=? AND id=?",
                    (payload, collection, doc_id),
                )
            else:
                seq = self._conn.execute(
                    "SELECT COALESCE(MAX(seq), 0) + 1 FROM documents WHERE collection=?",
                    (collection,),
                ).fetchone()[0]
                self._conn.execute(
                    "INSERT INTO documents (collection, id, seq, data) VALUES (?,?,?,?)",
                    (collection, doc_id, seq, payload),
                )

    def get(self, collection: str, doc_id: str) -> Optional[Document]:
        row = self._conn.execute(
            "SELECT data FROM documents WHERE collection=? AND id=?",
            (collection, doc_id),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def list(self, collection: str) -> List[Document]:
        rows = self._conn.execute(
            "SELECT data FROM documents WHERE collection=? ORDER BY seq",
            (collection,),
        ).fetchall()
        return [json.loads(r[0]) for r in rows]

    def close(self) -> None:
        self._conn.close()
