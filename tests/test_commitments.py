import unittest

from tbank import InvalidOperation, PermissionDenied
from tbank.clock import iso
from tbank.models import (BOUGHT_OUT, COMMITMENT_DEFAULT, COVER_REQUESTED,
                          DEFAULTED, EARNED, FULFILLED, OPEN)

from helpers import B, BankTestCase


class CommitmentTests(BankTestCase):
    def setUp(self):
        super().setUp()
        self.coord = self.join("Coord", "+919800000001")
        self.p = self.join("Provider", "+919800000002")
        self.r = self.join("Recipient", "+919800000003")
        self.c = self.join("Cover", "+919800000004")
        due = iso(self.clock.now().replace(hour=18))
        self.cm = self.bank.commitments.create(self.r.id, self.p.id, self.r.id, B, 1, due)

    def test_cover_for_me(self):
        cm = self.bank.commitments.request_cover(self.p.id, self.cm.id, self.c.id)
        self.assertEqual(cm.status, COVER_REQUESTED)
        cm = self.bank.commitments.accept_cover(self.c.id, self.cm.id)
        self.assertEqual((cm.provider_id, cm.status), (self.c.id, OPEN))
        claim = self.bank.contributions.record(self.c.id, self.r.id, B, 1,
                                               commitment_id=cm.id)
        self.bank.contributions.confirm(self.r.id, claim.id)
        self.assertEqual(self.bank.commitments.get(cm.id).status, FULFILLED)
        self.assertEqual(self.bal(self.c, B, EARNED), 1)

    def test_cover_offered_to_someone_else(self):
        self.bank.commitments.request_cover(self.p.id, self.cm.id, self.c.id)
        with self.assertRaises(PermissionDenied):
            self.bank.commitments.accept_cover(self.coord.id, self.cm.id)

    def test_open_cover_request_visible_to_others(self):
        self.bank.commitments.request_cover(self.p.id, self.cm.id)
        ids = [c.id for c in self.bank.commitments.open_cover_requests(self.c.id)]
        self.assertEqual(ids, [self.cm.id])

    def test_overdue_defaults_then_cover_resolves(self):
        self.clock.advance(hours=40)
        self.bank.tick()
        self.assertEqual(self.bank.commitments.get(self.cm.id).status, DEFAULTED)
        open_defaults = self.bank.defaults.for_member(self.p.id, open_only=True)
        self.assertEqual([d.kind for d in open_defaults], [COMMITMENT_DEFAULT])
        self.bank.commitments.request_cover(self.p.id, self.cm.id)
        self.bank.commitments.accept_cover(self.c.id, self.cm.id)
        self.assertEqual(self.bank.defaults.for_member(self.p.id, open_only=True), [])

    def test_buyout(self):
        self.bank.commitments.mark_missed(self.r.id, self.cm.id)
        cm = self.bank.commitments.buyout(self.p.id, self.cm.id)
        self.assertEqual(cm.status, BOUGHT_OUT)
        entries = [e for e in self.bank.ledger.history(self.p.id) if e.kind == "buyout"]
        self.assertEqual(entries[0].meta["amount"], 300)
        self.assertEqual(self.bank.defaults.for_member(self.p.id, open_only=True), [])
        with self.assertRaises(InvalidOperation):
            self.bank.commitments.buyout(self.p.id, self.cm.id)

    def test_only_recipient_reports_missed(self):
        with self.assertRaises(PermissionDenied):
            self.bank.commitments.mark_missed(self.c.id, self.cm.id)


if __name__ == "__main__":
    unittest.main()
