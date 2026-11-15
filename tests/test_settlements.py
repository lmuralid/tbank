import unittest

from tbank import InvalidOperation, PermissionDenied
from tbank.models import DEBT, EARNED, ETD

from helpers import A, B, BankTestCase


class SettlementTests(BankTestCase):
    def setUp(self):
        super().setUp()
        self.coord = self.join("Coord", "+919800000001", label=A, hours=2)
        self.x = self.join("X", "+919800000002", label=A, hours=2)
        self.y = self.join("Y", "+919800000003", label=A, hours=2)
        self.give(self.x, self.coord, B, 3)       # x earns 3 in B

    def test_transfer_earned_credit(self):
        self.bank.settlements.transfer(self.x.id, self.x.id, self.y.id, B, 3)
        self.assertEqual(self.bal(self.x, B, EARNED), 0)
        self.assertEqual(self.bal(self.y, B, EARNED), 3)

    def test_etd_cannot_be_transferred(self):
        with self.assertRaises(InvalidOperation):
            self.bank.settlements.transfer(self.x.id, self.x.id, self.y.id, A, 1)
        self.assertEqual(self.bal(self.x, A, ETD), 2)

    def test_transfer_needs_permission(self):
        with self.assertRaises(PermissionDenied):
            self.bank.settlements.transfer(self.y.id, self.x.id, self.y.id, B, 1)

    def test_cross_member_debt_payoff(self):
        self.give(self.coord, self.y, B, 2)       # y owes 2 in B
        self.bank.settlements.pay_off_debt(self.x.id, self.x.id, self.y.id, B, 2)
        self.assertEqual(self.bal(self.y, B, DEBT), 0)
        self.assertEqual(self.bal(self.x, B, EARNED), 1)

    def test_payoff_cannot_exceed_debt_or_credit(self):
        self.give(self.coord, self.y, B, 5)
        with self.assertRaises(InvalidOperation):
            self.bank.settlements.pay_off_debt(self.x.id, self.x.id, self.y.id, B, 4)
        with self.assertRaises(InvalidOperation):
            self.bank.settlements.pay_off_debt(self.x.id, self.x.id, self.y.id, B, 6)

    def test_money_settlement_for_eligible_member(self):
        self.give(self.x, self.y, B, 1)           # y owes 1 in B
        with self.assertRaises(PermissionDenied):
            self.bank.settlements.settle_in_money(self.y.id, self.y.id, B, 1)
        self.bank.members.set_attributes(self.coord.id, self.y.id,
                                         {"age": 70, "mobility": "limited"})
        entry = self.bank.settlements.settle_in_money(self.y.id, self.y.id, B, 1)
        self.assertEqual(entry.meta["amount"], 300)
        self.assertEqual(self.bal(self.y, B, DEBT), 0)

    def test_age_alone_is_not_eligible(self):
        self.bank.members.set_attributes(self.coord.id, self.y.id, {"age": 70})
        self.assertFalse(self.bank.settlements.is_money_eligible(self.y.id))


if __name__ == "__main__":
    unittest.main()
