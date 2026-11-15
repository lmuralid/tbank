"""Scripted walkthrough: elder care and pet care in an apartment complex.

Run from the repository root:

    python3 examples/apartment/demo.py                 # in memory
    python3 examples/apartment/demo.py --store jsonl   # flat files in ./demo-data
    python3 examples/apartment/demo.py --store sqlite  # ./demo-data/tbank.db
"""

import argparse
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))

from tbank import (CommunityConfig, FixedClock, MemorySender,  # noqa: E402
                   TimeBank, open_storage)
from tbank.clock import iso  # noqa: E402

ELDER_TALK = "elder-care/companionship"
ELDER_ERRANDS = "elder-care/errands"
DOG = "pet-care/dog-walking"


def sign_in(bank, sender, phone):
    bank.auth.request_otp(phone)
    return bank.auth.verify_otp(phone, sender.last_code(phone))


def show(bank, title, *members):
    print(f"\n--- {title} ---")
    for m in members:
        t = bank.ledger.totals(m.id)
        detail = ", ".join(
            f"{label}: etd {b['etd']:g} / earned {b['earned']:g} / debt {b['debt']:g}"
            for label, b in sorted(bank.ledger.balances(m.id).items()))
        print(f"{m.name:<8} net {t['net']:>5g}h  {detail or '(nothing yet)'}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--store", default="memory", choices=["memory", "jsonl", "sqlite"])
    parser.add_argument("--data", default="demo-data")
    args = parser.parse_args()
    if args.store != "memory" and os.path.exists(args.data):
        shutil.rmtree(args.data)

    clock, sender = FixedClock(), MemorySender()
    config = CommunityConfig.load(os.path.join(HERE, "config.json"))
    bank = TimeBank(config, open_storage(args.store, args.data), clock, sender)
    print(f"Community: {config.name}  (storage: {args.store})")

    # Joining. Priya joins first and becomes coordinator.
    priya = bank.members.join(sign_in(bank, sender, "+919800000001"), "Priya",
                              etd_label=ELDER_TALK, etd_hours=3)
    ravi = bank.members.join(sign_in(bank, sender, "+919800000002"), "Ravi",
                             etd_label=DOG, etd_hours=2)
    # Mrs Rao joins without advance time: her first volunteer time is her ETD.
    rao = bank.members.join(sign_in(bank, sender, "+919800000003"), "Mrs Rao")
    arjun = bank.members.join(sign_in(bank, sender, "+919800000004"), "Arjun",
                              etd_label=DOG, etd_hours=2)
    bank.members.set_attributes(priya.id, rao.id, {"age": 78, "mobility": "limited"})
    bank.members.add_guardian(priya.id, rao.id, arjun.id)   # Arjun is her son
    show(bank, "After joining", priya, ravi, rao, arjun)

    # Ravi walks Mrs Rao's dog; her son Arjun confirms as guardian.
    c1 = bank.contributions.record(ravi.id, rao.id, DOG, 1.5, note="evening walk")
    bank.contributions.confirm(arjun.id, c1.id)
    show(bank, "Ravi walked Mrs Rao's dog (confirmed by guardian)", ravi, rao)

    # Mrs Rao keeps Priya company; it becomes her ETD (first volunteer time).
    c2 = bank.contributions.record(rao.id, priya.id, ELDER_TALK, 1)
    bank.contributions.confirm(priya.id, c2.id)
    show(bank, "Mrs Rao's first volunteer hour becomes her ETD", rao, priya)

    # Priya runs errands for Mrs Rao but nobody confirms within 48 hours.
    c3 = bank.contributions.record(priya.id, rao.id, ELDER_ERRANDS, 2)
    clock.advance(hours=49)
    bank.tick()
    print(f"\nClaim {c3.id} -> {bank.contributions.get(c3.id).status}; "
          f"open defaults for Mrs Rao: {len(bank.defaults.for_member(rao.id, True))}")
    show(bank, "Errands auto-confirmed after the window", priya, rao)

    # Mrs Rao is eligible to settle debt in money.
    entry = bank.settlements.settle_in_money(arjun.id, rao.id, ELDER_ERRANDS, 1)
    print(f"\nMoney settlement: {entry.meta['amount']:g} {entry.meta['currency']}")
    # Arjun pays off his mother's remaining dog-walking debt with his own credit.
    ravi_walk = bank.contributions.record(arjun.id, ravi.id, DOG, 0.5)
    bank.contributions.confirm(ravi.id, ravi_walk.id)
    show(bank, "Before cross-member pay-off", arjun, rao)
    owed_dog = bank.ledger.bucket(rao.id, DOG, "debt")
    if owed_dog:
        bank.settlements.pay_off_debt(arjun.id, arjun.id, rao.id, DOG,
                                      min(owed_dog, bank.ledger.bucket(arjun.id, DOG, "earned")))
    show(bank, "After settlements", rao, arjun)

    # Cover for me: Ravi promised a walk but has to travel; Arjun covers.
    due = iso(clock.advance(hours=1))
    cm = bank.commitments.create(rao.id, ravi.id, rao.id, DOG, 1, due)
    bank.commitments.request_cover(ravi.id, cm.id)
    bank.commitments.accept_cover(arjun.id, cm.id)
    walk = bank.contributions.record(arjun.id, rao.id, DOG, 1, commitment_id=cm.id)
    bank.contributions.confirm(rao.id, walk.id)  # Arjun cannot confirm his own walk
    print(f"\nCommitment {cm.id}: {bank.commitments.get(cm.id).status} "
          f"(provider now {bank.members.get(bank.commitments.get(cm.id).provider_id).name})")

    # A disputed claim settled by the coordinator.
    c4 = bank.contributions.record(arjun.id, ravi.id, DOG, 3)
    bank.contributions.reject(ravi.id, c4.id, "walk was only one hour")
    bank.contributions.resolve_dispute(priya.id, c4.id, uphold=False,
                                       note="re-record as one hour")
    print(f"Disputed claim {c4.id}: {bank.contributions.get(c4.id).status}")

    show(bank, "Final balances", priya, ravi, rao, arjun)
    bank.close()


if __name__ == "__main__":
    main()
