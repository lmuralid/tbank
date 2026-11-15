import unittest

from tbank import InvalidOperation
from tbank.models import DEBT, EARNED, ETD

from helpers import A, B, BankTestCase


class SpendingOrderTests(BankTestCase):
    def setUp(self):
        super().setUp()
        self.p = self.join("Provider", "+919800000001", label=A, hours=1)
        self.r = self.join("Recipient", "+919800000002", label=A, hours=2)

    def test_earned_then_etd_then_debt(self):
        self.give(self.r, self.p, A, 1)           # recipient earns 1 in A
        self.give(self.p, self.r, A, 4)           # recipient receives 4 in A
        self.assertEqual(self.bal(self.r, A, EARNED), 0)
        self.assertEqual(self.bal(self.r, A, ETD), 0)
        self.assertEqual(self.bal(self.r, A, DEBT), 1)

    def test_debit_stays_within_label(self):
        self.give(self.p, self.r, B, 1)
        self.assertEqual(self.bal(self.r, A, ETD), 2)   # A credit untouched
        self.assertEqual(self.bal(self.r, B, DEBT), 1)

    def test_earning_repays_debt_first(self):
        self.give(self.p, self.r, B, 2)
        self.give(self.r, self.p, B, 3)
        self.assertEqual(self.bal(self.r, B, DEBT), 0)
        self.assertEqual(self.bal(self.r, B, EARNED), 1)

    def test_debt_is_unlimited_by_default(self):
        self.give(self.p, self.r, B, 8)
        self.give(self.p, self.r, B, 8)
        self.assertEqual(self.bal(self.r, B, DEBT), 16)

    def test_totals(self):
        self.give(self.p, self.r, B, 3)
        totals = self.bank.ledger.totals(self.r.id)
        self.assertEqual(totals, {ETD: 2, EARNED: 0, DEBT: 3, "net": -1})


class EquivalenceTests(BankTestCase):
    config_overrides = {"equivalence_groups": [[A, B]]}

    def test_debit_crosses_labels_in_group(self):
        p = self.join("Provider", "+919800000001", label=A, hours=1)
        r = self.join("Recipient", "+919800000002", label=A, hours=2)
        self.give(p, r, B, 2)
        self.assertEqual(self.bal(r, A, ETD), 0)
        self.assertEqual(self.bal(r, B, DEBT), 0)


class DebtLimitTests(BankTestCase):
    config_overrides = {"debt_limit": {"type": "etd_multiple", "value": 2}}

    def test_limit_as_multiple_of_etd(self):
        p = self.join("Provider", "+919800000001", label=A, hours=1)
        r = self.join("Recipient", "+919800000002", label=A, hours=1)
        self.give(p, r, B, 2)                # 2 debt == 2 x ETD, allowed
        with self.assertRaises(InvalidOperation):
            self.give(p, r, B, 0.5)


class HoursLimitTests(BankTestCase):
    config_overrides = {"debt_limit": {"type": "hours", "value": 1}}

    def test_limit_in_hours(self):
        p = self.join("Provider", "+919800000001")
        r = self.join("Recipient", "+919800000002")
        with self.assertRaises(InvalidOperation):
            self.give(p, r, B, 1.5)


if __name__ == "__main__":
    unittest.main()
