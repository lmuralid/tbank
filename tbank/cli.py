"""Command-line tool for trying tbank by hand with flat files or SQLite.

OTP codes are written to ``<data>/otp_outbox.txt`` (and printed) instead of
being sent by SMS. After ``verify``, the session is remembered per phone in
``<data>/sessions.json`` so later commands take ``--as PHONE``.

    python3 -m tbank.cli --config community.json otp +919800000001
    python3 -m tbank.cli --config ... verify +919800000001 123456
    python3 -m tbank.cli --config ... join --as +919800000001 --name Priya \\
        --etd-label some/label --etd-hours 3
    python3 -m tbank.cli --config ... statement --as +919800000001
"""

import argparse
import json
import os
import sys
from typing import Any, Dict

from .auth import FileSender, normalize_phone
from .bank import TimeBank
from .errors import TBankError


class Cli:
    def __init__(self, args):
        self.args = args
        os.makedirs(args.data, exist_ok=True)
        self.sessions_path = os.path.join(args.data, "sessions.json")
        sender = _TeeSender(os.path.join(args.data, "otp_outbox.txt"))
        self.bank = TimeBank.open(args.config, args.store, args.data, otp_sender=sender)

    # ----- session helpers ----------------------------------------------
    def _sessions(self) -> Dict[str, str]:
        if not os.path.exists(self.sessions_path):
            return {}
        with open(self.sessions_path, encoding="utf-8") as fh:
            return json.load(fh)

    def _token(self, phone: str) -> str:
        token = self._sessions().get(normalize_phone(phone))
        if not token:
            raise TBankError(f"{phone} is not signed in; run otp and verify first")
        return token

    def actor(self) -> str:
        if not self.args.as_phone:
            raise TBankError("--as PHONE is required for this command")
        return self.bank.auth.member_for(self._token(self.args.as_phone))

    def member(self, ref: str) -> str:
        return self.bank.members.find(ref).id

    # ----- commands -----------------------------------------------------
    def otp(self):
        self.bank.auth.request_otp(self.args.phone)

    def verify(self):
        token = self.bank.auth.verify_otp(self.args.phone, self.args.code)
        sessions = self._sessions()
        sessions[normalize_phone(self.args.phone)] = token
        with open(self.sessions_path, "w", encoding="utf-8") as fh:
            json.dump(sessions, fh, indent=2)
        return "signed in"

    def join(self):
        a = self.args
        return self.bank.members.join(self._token(a.as_phone), a.name,
                                      etd_label=a.etd_label, etd_hours=a.etd_hours)

    def members(self):
        return [{"id": m.id, "name": m.name, "phone": m.phone, "roles": m.roles,
                 "etd_label": m.etd_label} for m in self.bank.members.list()]

    def statement(self):
        target = self.member(self.args.member) if self.args.member else self.actor()
        return self.bank.statement(target)

    def record(self):
        a = self.args
        return self.bank.contributions.record(
            self.actor(), self.member(a.to), a.label, a.hours,
            note=a.note, commitment_id=a.commitment)

    def pending(self):
        return self.bank.contributions.awaiting(self.actor())

    def confirm(self):
        return self.bank.contributions.confirm(self.actor(), self.args.claim)

    def reject(self):
        return self.bank.contributions.reject(self.actor(), self.args.claim, self.args.reason)

    def disputes(self):
        return self.bank.contributions.disputed()

    def resolve(self):
        a = self.args
        return self.bank.contributions.resolve_dispute(self.actor(), a.claim,
                                                       a.decision == "uphold", a.note)

    def transfer(self):
        a = self.args
        actor = self.actor()
        return self.bank.settlements.transfer(actor, actor, self.member(a.to),
                                              a.label, a.hours, a.note)

    def payoff(self):
        a = self.args
        actor = self.actor()
        return self.bank.settlements.pay_off_debt(actor, actor, self.member(a.debtor),
                                                  a.label, a.hours)

    def settle_money(self):
        a = self.args
        return self.bank.settlements.settle_in_money(
            self.actor(), self.member(a.member), a.label, a.hours, a.amount, a.reference)

    def set_attr(self):
        attrs = dict(_parse_pair(p) for p in self.args.pairs)
        return self.bank.members.set_attributes(self.actor(), self.member(self.args.member), attrs)

    def guardian(self):
        a = self.args
        return self.bank.members.add_guardian(self.actor(), self.member(a.member),
                                              self.member(a.guardian))

    def commit(self):
        a = self.args
        return self.bank.commitments.create(
            self.actor(), self.member(a.provider), self.member(a.recipient),
            a.label, a.hours, a.due)

    def cover_request(self):
        to = self.member(self.args.to) if self.args.to else None
        return self.bank.commitments.request_cover(self.actor(), self.args.commitment, to)

    def cover_accept(self):
        return self.bank.commitments.accept_cover(self.actor(), self.args.commitment)

    def buyout(self):
        return self.bank.commitments.buyout(self.actor(), self.args.commitment, self.args.amount)

    def missed(self):
        return self.bank.commitments.mark_missed(self.actor(), self.args.commitment)

    def tick(self):
        result = self.bank.tick()
        return {k: [x.id for x in v] for k, v in result.items()}


class _TeeSender(FileSender):
    def send(self, phone: str, message: str) -> None:
        super().send(phone, message)
        print(f"[OTP to {phone}] {message}  (also in {self.path})")


def _parse_pair(text: str):
    key, _, raw = text.partition("=")
    try:
        return key, json.loads(raw)
    except json.JSONDecodeError:
        return key, raw


def _jsonable(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tbank", description="Community time bank")
    p.add_argument("--config", default=os.environ.get("TBANK_CONFIG"), required=
                   "TBANK_CONFIG" not in os.environ, help="community config JSON")
    p.add_argument("--store", default="jsonl", choices=["jsonl", "sqlite"])
    p.add_argument("--data", default="tbank-data", help="data directory")
    sub = p.add_subparsers(dest="command", required=True)

    def cmd(name, *, actor=False, **_):
        sp = sub.add_parser(name)
        if actor:
            sp.add_argument("--as", dest="as_phone", required=True, metavar="PHONE")
        else:
            sp.set_defaults(as_phone=None)
        return sp

    cmd("otp").add_argument("phone")
    sp = cmd("verify"); sp.add_argument("phone"); sp.add_argument("code")
    sp = cmd("join", actor=True); sp.add_argument("--name", required=True)
    sp.add_argument("--etd-label"); sp.add_argument("--etd-hours", type=float)
    cmd("members")
    sp = cmd("statement"); sp.add_argument("--as", dest="as_phone")
    sp.add_argument("--member", help="id or phone (default: yourself)")
    sp = cmd("record", actor=True); sp.add_argument("--to", required=True)
    sp.add_argument("--label", required=True); sp.add_argument("--hours", type=float, required=True)
    sp.add_argument("--note", default=""); sp.add_argument("--commitment")
    cmd("pending", actor=True)
    cmd("confirm", actor=True).add_argument("claim")
    sp = cmd("reject", actor=True); sp.add_argument("claim"); sp.add_argument("--reason", required=True)
    cmd("disputes")
    sp = cmd("resolve", actor=True); sp.add_argument("claim")
    sp.add_argument("decision", choices=["uphold", "dismiss"]); sp.add_argument("--note", default="")
    for name, who in (("transfer", "--to"), ("payoff", "--debtor")):
        sp = cmd(name, actor=True); sp.add_argument(who, required=True)
        sp.add_argument("--label", required=True); sp.add_argument("--hours", type=float, required=True)
        if name == "transfer":
            sp.add_argument("--note", default="")
    sp = cmd("settle-money", actor=True); sp.add_argument("--member", required=True)
    sp.add_argument("--label", required=True); sp.add_argument("--hours", type=float, required=True)
    sp.add_argument("--amount", type=float); sp.add_argument("--reference", default="")
    sp = cmd("set-attr", actor=True); sp.add_argument("member"); sp.add_argument("pairs", nargs="+")
    sp = cmd("guardian", actor=True); sp.add_argument("member"); sp.add_argument("guardian")
    sp = cmd("commit", actor=True)
    for flag in ("--provider", "--recipient", "--label", "--due"):
        sp.add_argument(flag, required=True)
    sp.add_argument("--hours", type=float, required=True)
    sp = cmd("cover-request", actor=True); sp.add_argument("commitment"); sp.add_argument("--to")
    cmd("cover-accept", actor=True).add_argument("commitment")
    sp = cmd("buyout", actor=True); sp.add_argument("commitment"); sp.add_argument("--amount", type=float)
    cmd("missed", actor=True).add_argument("commitment")
    cmd("tick")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cli = Cli(args)
        result = getattr(cli, args.command.replace("-", "_"))()
    except TBankError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if result is not None:
        print(json.dumps(_jsonable(result), indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
