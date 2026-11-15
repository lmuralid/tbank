# Changelog

## Versioning

Versions use the format **`MAJOR.MINOR.YYMM`** and are tagged `vMAJOR.MINOR.YYMM`:

- **MAJOR**: changes that break existing data, configuration or the public API.
- **MINOR**: new features that stay compatible.
- **YYMM**: year and month of the release (e.g. `2611` = November 2026).

Example: `v1.0.2611` is the first 1.0 release, made in November 2026.

---

## v1.0.2611 (November 2026)

First release of **tbank**, a time bank for communities. Members give time to
one another; every hour given is recorded and later repaid by someone else in
the community.

### Highlights

- **Earnest Time Deposit (ETD)**: starting credit at sign-up, given as advance
  time or as the member's first volunteer time. Labelled with the label the
  member chooses, or the label of that first activity. The member can spend
  it, but it cannot be transferred. Kept separate from debt.
- **Labels as configuration**: kinds of time (e.g. nursing, dog walking) live
  in a config file, never in code. An hour is an hour within a label; debits
  stay within a label until equivalence groups are configured.
- **Confirmation by the person cared for**, their guardian or the pet owner.
  If nobody confirms within the window (48 hours in the sample), the hours
  are committed and a default is recorded against the confirmer.
- **Disputes** settled by a coordinator who is not a party to them.
- **Debt** allowed, with an optional limit as a multiple of ETD or a number
  of hours.
- **Paying back**: unlimited transfers of earned credit, paying off another
  member's debt, and money settlement for eligible members (data-driven
  rule, e.g. senior citizens with limited mobility).
- **Commitments**: "cover for me" hand-over to another member, buyout, and
  automatic default when overdue.
- **OTP sign-in** on a mobile number, one number per member.

### Storage and tools

- Pluggable storage: in-memory, flat files (JSON lines) and SQLite. No server
  or other infrastructure needed.
- Command-line tool (`python3 -m tbank.cli`) for trying it by hand. OTP codes
  are written to a local outbox file instead of being sent by SMS.
- Sample app: elder care and pet care in an apartment complex
  (`examples/apartment/`).
- Python 3.9+, standard library only, no dependencies.

### Rules enforced by tests

- No file over 500 lines.
- No care category written into package code.

### Known limitations

- Money settlements and buyouts are recorded; no payment is processed.
- Flat-file storage assumes one user at a time.
- Time-based rules (auto-confirm, overdue defaults) run only when `tick` is
  called, so real use needs it on a schedule.
- The CLI keeps sign-in sessions in a plain file in the data folder; for
  testing only.
- Swapping hours across labels (equivalence with rates) is not designed yet.
