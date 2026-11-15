"""Shared test fixtures. Labels here are test data, not package code."""

import unittest

from tbank import CommunityConfig, FixedClock, MemorySender, MemoryStorage, TimeBank

A, B = "skill/a", "skill/b"


def make_config(**overrides) -> CommunityConfig:
    data = {
        "name": "Test Community",
        "labels": {A: {}, B: {}, "skill/c": {}},
        "confirmation_window_hours": 48,
        "commitment_grace_hours": 24,
        "etd_default_hours": 2,
        "money": {
            "currency": "INR",
            "default_rate": 100,
            "rates": {B: 300},
            "eligibility": {"all": [
                {"attr": "age", "op": ">=", "value": 60},
                {"attr": "mobility", "op": "==", "value": "limited"},
            ]},
        },
    }
    data.update(overrides)
    return CommunityConfig.from_dict(data)


class BankTestCase(unittest.TestCase):
    config_overrides: dict = {}

    def setUp(self):
        self.clock = FixedClock()
        self.sender = MemorySender()
        self.bank = self.make_bank(MemoryStorage())

    def make_bank(self, storage):
        return TimeBank(make_config(**self.config_overrides), storage,
                        self.clock, self.sender)

    def sign_in(self, phone: str) -> str:
        self.bank.auth.request_otp(phone)
        return self.bank.auth.verify_otp(phone, self.sender.last_code(phone))

    def join(self, name: str, phone: str, label=A, hours=2):
        return self.bank.members.join(self.sign_in(phone), name,
                                      etd_label=label, etd_hours=hours)

    def give(self, provider, recipient, label, hours, confirmer=None):
        claim = self.bank.contributions.record(provider.id, recipient.id, label, hours)
        return self.bank.contributions.confirm((confirmer or recipient).id, claim.id)

    def bal(self, member, label, bucket):
        return self.bank.ledger.bucket(member.id, label, bucket)
