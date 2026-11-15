import os
import tempfile
import unittest

from tbank import InvalidOperation, JsonFileStorage, MemoryStorage, SqliteStorage
from tbank.models import EARNED

from helpers import B, BankTestCase


class StorageContract:
    """Every adapter must pass these."""

    def make(self):
        raise NotImplementedError

    def test_put_get_list(self):
        s = self.make()
        s.put("things", "1", {"v": 1})
        s.put("things", "2", {"v": 2})
        s.put("things", "1", {"v": 3})
        self.assertEqual(s.get("things", "1"), {"v": 3})
        self.assertIsNone(s.get("things", "missing"))
        self.assertEqual(s.list("things"), [{"v": 3}, {"v": 2}])

    def test_append_only(self):
        s = self.make()
        s.append("entries", "e1", {"x": 1})
        with self.assertRaises(InvalidOperation):
            s.append("entries", "e1", {"x": 2})


class MemoryStorageTests(StorageContract, unittest.TestCase):
    def make(self):
        return MemoryStorage()


class JsonFileStorageTests(StorageContract, unittest.TestCase):
    def make(self):
        return JsonFileStorage(tempfile.mkdtemp())


class SqliteStorageTests(StorageContract, unittest.TestCase):
    def make(self):
        return SqliteStorage(os.path.join(tempfile.mkdtemp(), "t.db"))


class PersistenceTests(BankTestCase):
    """Data written by one TimeBank is visible to a fresh one on the same files."""

    def check(self, factory):
        self.bank = self.make_bank(factory())
        p = self.join("P", "+919800000001")
        r = self.join("R", "+919800000002")
        self.give(p, r, B, 1.5)
        self.bank.close()
        self.bank = self.make_bank(factory())
        self.assertEqual(self.bal(p, B, EARNED), 1.5)
        self.assertEqual(len(self.bank.members.list()), 2)

    def test_jsonl(self):
        d = tempfile.mkdtemp()
        self.check(lambda: JsonFileStorage(d))

    def test_sqlite(self):
        path = os.path.join(tempfile.mkdtemp(), "t.db")
        self.check(lambda: SqliteStorage(path))


if __name__ == "__main__":
    unittest.main()
