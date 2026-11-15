import unittest

from tbank import AuthError, InvalidOperation, PermissionDenied, ValidationError
from tbank.models import COORDINATOR, ETD

from helpers import A, B, BankTestCase


class AuthTests(BankTestCase):
    def test_wrong_code_rejected_and_attempts_limited(self):
        self.bank.auth.request_otp("+919800000001")
        for _ in range(self.bank.config.otp_max_attempts):
            with self.assertRaises(AuthError):
                self.bank.auth.verify_otp("+919800000001", "not-it")
        code = self.sender.last_code("+919800000001")
        with self.assertRaises(AuthError):
            self.bank.auth.verify_otp("+919800000001", code)

    def test_code_expires(self):
        self.bank.auth.request_otp("+919800000001")
        self.clock.advance(minutes=11)
        with self.assertRaises(AuthError):
            self.bank.auth.verify_otp("+919800000001",
                                      self.sender.last_code("+919800000001"))

    def test_code_single_use(self):
        phone = "+919800000001"
        self.bank.auth.request_otp(phone)
        code = self.sender.last_code(phone)
        self.bank.auth.verify_otp(phone, code)
        with self.assertRaises(AuthError):
            self.bank.auth.verify_otp(phone, code)

    def test_invalid_phone(self):
        with self.assertRaises(ValidationError):
            self.bank.auth.request_otp("12ab")

    def test_session_maps_to_member(self):
        token = self.sign_in("+91 98000-00001")
        member = self.bank.members.join(token, "Asha")
        self.assertEqual(self.bank.auth.member_for(token), member.id)


class MemberTests(BankTestCase):
    def test_one_member_per_phone(self):
        self.join("Asha", "+919800000001")
        with self.assertRaises(InvalidOperation):
            self.join("Asha again", "+919800000001")

    def test_first_member_is_coordinator(self):
        first = self.join("Asha", "+919800000001")
        second = self.join("Bala", "+919800000002")
        self.assertIn(COORDINATOR, first.roles)
        self.assertNotIn(COORDINATOR, second.roles)

    def test_advance_etd_with_chosen_label(self):
        m = self.join("Asha", "+919800000001", label=B, hours=3)
        self.assertEqual(m.etd_label, B)
        self.assertEqual(self.bal(m, B, ETD), 3)

    def test_default_etd_hours(self):
        m = self.bank.members.join(self.sign_in("+919800000001"), "Asha", etd_label=A)
        self.assertEqual(self.bal(m, A, ETD), self.bank.config.etd_default_hours)

    def test_etd_only_once(self):
        m = self.join("Asha", "+919800000001")
        with self.assertRaises(InvalidOperation):
            self.bank.members.grant_etd(m.id, m.id, A, 1)

    def test_first_volunteer_time_becomes_etd(self):
        a = self.join("Asha", "+919800000001")
        b = self.bank.members.join(self.sign_in("+919800000002"), "Bala")
        self.assertIsNone(b.etd_label)
        self.give(b, a, B, 1.5)
        b = self.bank.members.get(b.id)
        self.assertEqual(b.etd_label, B)
        self.assertEqual(self.bal(b, B, ETD), 1.5)
        self.give(b, a, B, 1)  # later time is earned credit, not ETD
        self.assertEqual(self.bal(b, B, ETD), 1.5)
        self.assertEqual(self.bal(b, B, "earned"), 1)

    def test_only_coordinator_sets_attributes(self):
        coord = self.join("Asha", "+919800000001")
        other = self.join("Bala", "+919800000002")
        with self.assertRaises(PermissionDenied):
            self.bank.members.set_attributes(other.id, other.id, {"age": 90})
        self.bank.members.set_attributes(coord.id, other.id, {"age": 90})
        self.assertEqual(self.bank.members.get(other.id).attributes["age"], 90)

    def test_unknown_label_rejected(self):
        with self.assertRaises(ValidationError):
            self.join("Asha", "+919800000001", label="not/configured")


if __name__ == "__main__":
    unittest.main()
