"""OTP sign-in on a mobile number.

One verified mobile number maps to at most one member, which limits one person
running several accounts to pass credit between them. Delivery of the OTP is
pluggable: console and file senders need no infrastructure; an SMS gateway can
implement the same ``send`` method later.
"""

import hashlib
import hmac
import os
import re
import secrets
from datetime import timedelta
from typing import List, Optional, Protocol, Tuple

from .clock import iso, parse
from .context import Context
from .errors import AuthError, ValidationError
from .repository import OTPS, SESSIONS

_PHONE = re.compile(r"^\+?\d{8,15}$")


def normalize_phone(phone: str) -> str:
    cleaned = re.sub(r"[\s\-().]", "", phone or "")
    if not _PHONE.match(cleaned):
        raise ValidationError(f"invalid mobile number {phone!r}")
    return cleaned


class OtpSender(Protocol):
    def send(self, phone: str, message: str) -> None: ...


class ConsoleSender:
    """Prints the OTP. For local testing only."""

    def send(self, phone: str, message: str) -> None:
        print(f"[OTP to {phone}] {message}")


class FileSender:
    """Appends each OTP message to a file (an 'outbox') for local testing."""

    def __init__(self, path: str):
        self.path = path

    def send(self, phone: str, message: str) -> None:
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(f"{phone}\t{message}\n")


class MemorySender:
    """Keeps messages in a list. For tests and scripted demos."""

    def __init__(self):
        self.messages: List[Tuple[str, str]] = []

    def send(self, phone: str, message: str) -> None:
        self.messages.append((phone, message))

    def last_code(self, phone: str) -> Optional[str]:
        phone = normalize_phone(phone)
        for to, message in reversed(self.messages):
            if to == phone:
                return message.rsplit(" ", 1)[-1]
        return None


def _hash(code: str, salt: str) -> str:
    return hashlib.sha256((salt + code).encode()).hexdigest()


class AuthService:
    def __init__(self, ctx: Context, sender: OtpSender):
        self.ctx = ctx
        self.sender = sender

    def request_otp(self, phone: str) -> None:
        phone = normalize_phone(phone)
        cfg = self.ctx.config
        code = "".join(secrets.choice("0123456789") for _ in range(cfg.otp_length))
        salt = os.urandom(8).hex()
        expires = self.ctx.clock.now() + timedelta(minutes=cfg.otp_ttl_minutes)
        self.ctx.repo.storage.put(OTPS, phone, {
            "phone": phone, "salt": salt, "hash": _hash(code, salt),
            "expires_at": iso(expires), "attempts": 0,
        })
        self.sender.send(phone, f"Your {cfg.name} code is {code}")

    def verify_otp(self, phone: str, code: str) -> str:
        """Check the code and return a session token for the phone."""
        phone = normalize_phone(phone)
        storage = self.ctx.repo.storage
        record = storage.get(OTPS, phone)
        if record is None or record.get("used"):
            raise AuthError("no code requested for this number")
        if self.ctx.clock.now() > parse(record["expires_at"]):
            raise AuthError("code expired")
        if record["attempts"] >= self.ctx.config.otp_max_attempts:
            raise AuthError("too many attempts; request a new code")
        if not hmac.compare_digest(record["hash"], _hash(str(code), record["salt"])):
            record["attempts"] += 1
            storage.put(OTPS, phone, record)
            raise AuthError("wrong code")
        record["used"] = True
        storage.put(OTPS, phone, record)
        token = secrets.token_urlsafe(24)
        expires = self.ctx.clock.now() + timedelta(hours=self.ctx.config.session_ttl_hours)
        member = self.ctx.repo.member_by_phone(phone)
        storage.put(SESSIONS, token, {
            "token": token, "phone": phone, "expires_at": iso(expires),
            "member_id": member.id if member else None,
        })
        return token

    def session(self, token: str) -> dict:
        record = self.ctx.repo.storage.get(SESSIONS, token or "")
        if record is None:
            raise AuthError("unknown session")
        if self.ctx.clock.now() > parse(record["expires_at"]):
            raise AuthError("session expired")
        return record

    def phone_for(self, token: str) -> str:
        return self.session(token)["phone"]

    def member_for(self, token: str) -> str:
        """Member id signed in with this token."""
        record = self.session(token)
        if record.get("member_id"):
            return record["member_id"]
        member = self.ctx.repo.member_by_phone(record["phone"])
        if member is None:
            raise AuthError("this number has not joined yet")
        record["member_id"] = member.id
        self.ctx.repo.storage.put(SESSIONS, token, record)
        return member.id
