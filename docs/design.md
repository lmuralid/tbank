# tbank — Concept and Domain Design

Status: draft for review. No code yet.

## 1. Purpose

tbank is a reusable software package for recording and settling **time-based
exchanges inside a social setting**, such as a community, an apartment complex
or a social network. A member gives time to another member and earns credit.
That credit is later repaid by *someone else* in the community, not
necessarily the person who was helped.

A sample application will show the package in use: an **apartment complex**
where residents exchange **elder care** and **pet care**.

## 2. Glossary

| Term | Meaning |
|---|---|
| Member | A person in a community, identified by a verified mobile number. |
| Community | A group of members sharing one ledger and one configuration (e.g. one apartment complex). |
| Guardian | A member allowed to act for another member (e.g. a family member of a senior). |
| Label | A configurable tag for a kind of time, such as "nursing" or "dog walking". Never hard-coded. |
| Equivalence group | (Future) A rule that lets hours under different labels be swapped. |
| ETD | Earnest Time Deposit: starting credit given when a member joins. |
| Earned credit | Hours a member has received for confirmed contributions, held per label. |
| Debt | Hours a member has used beyond what they had in credit. Kept separate from ETD. |
| Confirmer | The member who confirms a contribution: the person who received care, their guardian, or the pet owner. |
| Default | A duty that was not met, such as a confirmation not given in time or a promised session not delivered. |
| Cover for me | Passing a defaulted duty to another member who fulfils it. |
| Buyout | Clearing a defaulted duty or a debt with money instead of time. |

## 3. Core rules

### 3.1 Time
- **One hour is one hour** within a label. An hour of dog walking equals any
  other hour of dog walking.
- Hours under **different labels are not swapped** until the community
  defines an equivalence group. Then, debits may cross labels within that group.

### 3.2 Earnest Time Deposit (ETD)
- Created when a member joins, either as advance time given at sign-up or
  from their first volunteer time.
- The ETD is **starting credit**. It is **locked to the member**: they can
  spend it on their own needs, but it **cannot be transferred** to anyone else.
- ETD is tracked **separately from debt**. ETD is the start, debt is ongoing.

### 3.3 Balances
- A member holds **one balance, made of labelled parts**:
  - ETD (starting credit)
  - Earned credit, per label
  - Debt, per label
- **Debits stay within a label** for now. When a member receives an hour of
  nursing, it is paid from nursing credit only. Once equivalence is set, the
  debit can reach across labels in the same group.

### 3.4 Debt
- Members **may go into debt**. There is **no limit** in the first version.
- The debt limit is configuration for later, expressed as a multiple of the
  ETD or as a fixed number of hours.
- Debt is **never funded from another member's ETD**. It is recorded against
  the member who owes it.

### 3.5 Money settlement
- **Eligible members** may settle debt in money instead of time, for example
  senior citizens with limited mobility.
- Who is eligible is a **configurable rule**, not code.
- The money value of an hour is set in configuration.

### 3.6 Transfers
- Earned credit can be **transferred to any member without limit**, for
  example a child giving credits to an elderly parent.
- ETD cannot be transferred (see 3.2).

## 4. Transaction lifecycle

```
  claimed ──► pending confirmation ──► confirmed ──► posted to ledger
                    │
                    ├──► rejected (disputed)
                    │
                    └──► not confirmed in time ──► default on the confirmer
```

1. The **provider** records time given: who received it, label, hours, when.
2. The **confirmer** (the recipient, their guardian, or the pet owner)
   confirms it.
3. On confirmation, the provider is credited and the recipient is debited
   within that label.
4. **Confirming is the confirmer's duty.** Not confirming within the allowed
   window is a **default** recorded against the confirmer.

### 4.1 Resolving a default
- **Cover for me**: the defaulting member passes the duty to another member,
  who fulfils it.
- **Buyout**: the duty is cleared with money.
- More mechanisms can be added as configuration.

## 5. Transaction types

All are generic. None are tied to a care category.

| Type | Effect |
|---|---|
| ETD grant | Opens a member's starting credit. |
| Contribution | Time given by one member to another under a label. Needs confirmation. |
| Transfer | Moves earned credit from one member to another. |
| Settlement | Clears debt, in time or (for eligible members) money. |
| Cover | Passes a defaulted duty from one member to another. |
| Buyout | Clears a defaulted duty with money. |

The ledger is **append-only**. Balances are always computed from the entries,
never edited directly. Corrections are new reversing entries.

## 6. Identity and fraud control

- Members sign in with a **one-time password (OTP) sent to their mobile**.
- **One verified mobile number per member** limits one person running several
  accounts to pass credit between themselves.
- Guardians are linked to the members they act for and may confirm for them.
- The OTP sender is **pluggable**. For testing, the OTP is written to the
  console or a file. A real SMS provider is plugged in later.

## 7. Storage

- All storage goes through **one storage interface**. The package never talks
  to a specific database directly.
- First adapters, needing no infrastructure:
  - **Flat file**: an append-only file of ledger entries plus configuration files.
  - **SQLite**: a single local database file.
- Later adapters (PostgreSQL, a hosted service and so on) implement the same
  interface without changes to the core.

## 8. Configuration as data

Everything community-specific lives in configuration, not code:

- Labels and (later) equivalence groups
- Confirmation window and default handling
- Eligibility rules for money settlement
- Money value of an hour
- Debt limit (when introduced)
- ETD amount or rule for new members

The sample app's "elder care" and "pet care" are just labels in a
configuration file.

## 9. Engineering constraints

- **No file may exceed 500 lines.**
- **No transaction type, label or category is hard-coded.**
- Storage, OTP delivery and notifications are pluggable interfaces.

## 10. Sample application: apartment complex

- Residents join with their mobile number and an ETD.
- Labels (from configuration): e.g. `elder-care/companionship`,
  `elder-care/errands`, `pet-care/dog-walking`, `pet-care/feeding`.
- A working resident walks a senior's dog. The senior or their guardian
  confirms. The resident earns dog-walking credit.
- A senior with limited mobility who runs into debt may settle it in money.
- A resident who cannot keep a commitment asks a neighbour to cover for them.

## 11. Language recommendation

**Python** for the core package:
- Flat file and SQLite support are built in, so testing needs no extra infrastructure.
- Clear, readable domain code suits a rules-heavy ledger.
- A small web API can be added on top later for a mobile or web sample app,
  which can then be written in any language.

Alternative: **TypeScript**, if one language across the package, the API and a
mobile app (React Native) matters more than quick standalone testing.

## 12. Open questions

1. **Spending order**: when a member receives time, is it paid from earned
   credit first, then ETD, then debt? (Assumed.)
2. **ETD label**: is ETD unlabelled, and so spendable under any label? (Assumed.)
3. **Default meaning**: does "default" cover both a missed confirmation and a
   promised session not delivered? (Assumed both.)
4. **Missed confirmation outcome**: after the window ends, is the hour posted
   to the provider anyway, or does it stay pending?
5. **Disputes**: who settles a rejected contribution — a coordinator, or no
   one for now?
6. **Can debt be transferred** (another member pays it off with their credit)?

## 13. Later

- Cross-label equivalence groups and debiting across labels.
- Debt limits.
- Asset time: sharing and renting equipment or infrastructure in hours, with
  deposits and wear and tear.
