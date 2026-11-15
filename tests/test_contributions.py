import unittest

from tbank import InvalidOperation, PermissionDenied, ValidationError
from tbank.models import (AUTO_CONFIRMED, CONFIRMATION_DEFAULT, DEBT, DISMISSED,
                          DISPUTED, EARNED, PENDING, UPHELD)

from helpers import A, B, BankTestCase


class ContributionTests(BankTestCase):
    def setUp(self):
        super().setUp()
        self.coord = self.join("Coord", "+919800000001")
        self.p = self.join("Provider", "+919800000002")
        self.r = self.join("Recipient", "+919800000003")
        self.g = self.join("Guardian", "+919800000004")
        self.bank.members.add_guardian(self.coord.id, self.r.id, self.g.id)

    def record(self, hours=1, label=B):
        return self.bank.contributions.record(self.p.id, self.r.id, label, hours)

    def test_nothing_posted_until_confirmed(self):
        claim = self.record()
        self.assertEqual(claim.status, PENDING)
        self.assertEqual(self.bal(self.p, B, EARNED), 0)

    def test_guardian_can_confirm(self):
        claim = self.record()
        self.bank.contributions.confirm(self.g.id, claim.id)
        self.assertEqual(self.bal(self.p, B, EARNED), 1)
        self.assertEqual(self.bal(self.r, B, DEBT), 1)

    def test_provider_and_strangers_cannot_confirm(self):
        claim = self.record()
        with self.assertRaises(PermissionDenied):
            self.bank.contributions.confirm(self.p.id, claim.id)
        with self.assertRaises(PermissionDenied):
            self.bank.contributions.confirm(self.coord.id, claim.id)

    def test_cannot_confirm_twice(self):
        claim = self.record()
        self.bank.contributions.confirm(self.r.id, claim.id)
        with self.assertRaises(InvalidOperation):
            self.bank.contributions.confirm(self.r.id, claim.id)

    def test_window_expiry_commits_and_records_default(self):
        claim = self.record(hours=2)
        self.clock.advance(hours=47)
        self.assertEqual(self.bank.tick()["auto_confirmed"], [])
        self.clock.advance(hours=2)
        done = self.bank.tick()["auto_confirmed"]
        self.assertEqual([c.id for c in done], [claim.id])
        self.assertEqual(self.bank.contributions.get(claim.id).status, AUTO_CONFIRMED)
        self.assertEqual(self.bal(self.p, B, EARNED), 2)
        defaults = self.bank.defaults.for_member(self.r.id)
        self.assertEqual([(d.kind, d.ref) for d in defaults],
                         [(CONFIRMATION_DEFAULT, claim.id)])

    def test_dispute_upheld_by_coordinator(self):
        claim = self.record()
        self.bank.contributions.reject(self.r.id, claim.id, "did not happen")
        self.assertEqual(self.bank.contributions.get(claim.id).status, DISPUTED)
        self.clock.advance(hours=100)
        self.bank.tick()  # disputed claims are not auto-confirmed
        self.assertEqual(self.bal(self.p, B, EARNED), 0)
        self.bank.contributions.resolve_dispute(self.coord.id, claim.id, uphold=True)
        self.assertEqual(self.bank.contributions.get(claim.id).status, UPHELD)
        self.assertEqual(self.bal(self.p, B, EARNED), 1)

    def test_dispute_dismissed(self):
        claim = self.record()
        self.bank.contributions.reject(self.r.id, claim.id, "too long")
        self.bank.contributions.resolve_dispute(self.coord.id, claim.id, uphold=False)
        self.assertEqual(self.bank.contributions.get(claim.id).status, DISMISSED)
        self.assertEqual(self.bal(self.p, B, EARNED), 0)

    def test_only_uninvolved_coordinator_resolves(self):
        claim = self.record()
        self.bank.contributions.reject(self.r.id, claim.id, "no")
        with self.assertRaises(PermissionDenied):
            self.bank.contributions.resolve_dispute(self.p.id, claim.id, True)
        own = self.bank.contributions.record(self.coord.id, self.r.id, A, 1)
        self.bank.contributions.reject(self.r.id, own.id, "no")
        with self.assertRaises(PermissionDenied):
            self.bank.contributions.resolve_dispute(self.coord.id, own.id, True)

    def test_validation(self):
        with self.assertRaises(ValidationError):
            self.bank.contributions.record(self.p.id, self.p.id, B, 1)
        with self.assertRaises(ValidationError):
            self.record(hours=0)
        with self.assertRaises(ValidationError):
            self.record(label="unknown")

    def test_awaiting_lists_wards(self):
        claim = self.record()
        self.assertEqual([c.id for c in self.bank.contributions.awaiting(self.g.id)],
                         [claim.id])
        self.assertEqual(self.bank.contributions.awaiting(self.p.id), [])


if __name__ == "__main__":
    unittest.main()
