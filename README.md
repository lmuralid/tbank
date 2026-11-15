# tbank

A time bank for communities. Members give time to one another; every hour
given is recorded and later repaid by someone else in the community.

- **Earnest Time Deposit (ETD)**: starting credit given at sign-up, either as
  advance time or as the member's first volunteer time. Its label is the one
  chosen, or the label of that first volunteer activity. Locked to the member:
  they can spend it, nobody else can.
- **Labels**: kinds of time ("nursing", "dog walking", ...) are configuration,
  never code. An hour is an hour within a label; debits stay within a label
  until equivalence groups are configured.
- **Confirmation**: the person cared for, their guardian or the pet owner
  confirms. If they do not confirm in time, the hours are committed anyway
  and a default is recorded against them.
- **Disputes** are settled by a coordinator.
- **Debt** is allowed (limit configurable later), kept separate from ETD.
  Eligible members (e.g. senior citizens with limited mobility) may settle
  debt in money. Anyone may pay off anyone's debt with earned credit.
- **Transfers** of earned credit are unlimited.
- **Cover for me / buyout** resolve a commitment a member cannot keep.
- **OTP sign-in** on a mobile number; one number per member.
- **Pluggable storage**: in memory, flat files (JSON lines) or SQLite. No
  server or other infrastructure needed for testing.

Pure Python standard library, no dependencies. Python 3.9+.

## Layout

```
tbank/                 the package
  bank.py              TimeBank facade
  ledger.py            append-only ledger, balances, spending order
  members.py           joining, ETD, guardians, roles, attributes
  contributions.py     record / confirm / dispute / auto-confirm
  commitments.py       promises, cover for me, buyout, defaults
  settlements.py       transfers, debt pay-off, money settlement
  auth.py              OTP sign-in and senders (console, file, memory)
  config.py            community configuration (all rules as data)
  eligibility.py       data-driven eligibility rules
  storage/             memory, jsonl and sqlite adapters
  cli.py               command-line tool for hand testing
examples/apartment/    sample: elder care and pet care in an apartment complex
docs/design.md         concept and domain design
tests/                 unittest suite
```

## Try it

Scripted demo (in memory, flat files or SQLite):

```bash
python3 examples/apartment/demo.py
```

```bash
python3 examples/apartment/demo.py --store jsonl --data demo-data
```

Run the tests:

```bash
python3 -m unittest discover -s tests -t tests
```

By hand with the CLI (OTP codes go to `tbank-data/otp_outbox.txt`):

```bash
export TBANK_CONFIG=examples/apartment/config.json
```

```bash
python3 -m tbank.cli otp +919800000001
```

```bash
python3 -m tbank.cli verify +919800000001 <code>
```

```bash
python3 -m tbank.cli join --as +919800000001 --name Priya --etd-label elder-care/companionship --etd-hours 3
```

```bash
python3 -m tbank.cli statement --as +919800000001
```

Run `python3 -m tbank.cli --help` for all commands. Run `tick` periodically
to auto-confirm expired claims and default overdue commitments.

## Rules for contributors

- No file may exceed 500 lines (enforced by `tests/test_rules.py`).
- No care category or transaction label may appear in the package code
  (also enforced); they belong in configuration.
