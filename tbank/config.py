"""Community configuration. Everything community-specific is data, not code.

Labels, equivalence groups, time windows, debt limits, money rates and
eligibility rules are all loaded from a JSON file (or a dict).
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from . import eligibility
from .errors import ValidationError

DEBT_LIMIT_TYPES = ("etd_multiple", "hours")


@dataclass
class MoneyConfig:
    """How eligible members may settle debt in money."""

    currency: str = "INR"
    default_rate: float = 0.0
    rates: Dict[str, float] = field(default_factory=dict)
    eligibility: Optional[Dict[str, Any]] = None

    def rate(self, label: str) -> float:
        return float(self.rates.get(label, self.default_rate))


@dataclass
class CommunityConfig:
    """Rules for one community's time bank."""

    name: str
    labels: Dict[str, Dict[str, Any]]
    equivalence_groups: List[List[str]] = field(default_factory=list)
    confirmation_window_hours: float = 48.0
    commitment_grace_hours: float = 24.0
    etd_default_hours: float = 2.0
    debt_limit: Optional[Dict[str, Any]] = None
    auto_repay_debt: bool = True
    max_hours_per_claim: Optional[float] = None
    otp_length: int = 6
    otp_ttl_minutes: int = 10
    otp_max_attempts: int = 5
    session_ttl_hours: int = 24 * 30
    money: MoneyConfig = field(default_factory=MoneyConfig)

    def __post_init__(self):
        self.validate()

    # ----- construction -------------------------------------------------
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CommunityConfig":
        data = dict(data)
        money = MoneyConfig(**data.pop("money", {}))
        labels = data.pop("labels", {})
        if isinstance(labels, list):
            labels = {name: {} for name in labels}
        try:
            return cls(labels=labels, money=money, **data)
        except TypeError as exc:
            raise ValidationError(f"bad configuration: {exc}") from None

    @classmethod
    def load(cls, path: str) -> "CommunityConfig":
        with open(path, "r", encoding="utf-8") as fh:
            return cls.from_dict(json.load(fh))

    # ----- validation ---------------------------------------------------
    def validate(self) -> None:
        if not self.name:
            raise ValidationError("community name is required")
        if not self.labels:
            raise ValidationError("at least one label must be configured")
        seen = set()
        for group in self.equivalence_groups:
            for label in group:
                self.require_label(label)
                if label in seen:
                    raise ValidationError(f"label {label!r} is in two groups")
                seen.add(label)
        if self.debt_limit is not None:
            kind = self.debt_limit.get("type")
            if kind not in DEBT_LIMIT_TYPES:
                raise ValidationError(f"debt_limit.type must be one of {DEBT_LIMIT_TYPES}")
            if float(self.debt_limit.get("value", -1)) < 0:
                raise ValidationError("debt_limit.value must be zero or more")
        for label in self.money.rates:
            self.require_label(label)
        eligibility.validate(self.money.eligibility)
        if self.confirmation_window_hours <= 0:
            raise ValidationError("confirmation_window_hours must be positive")

    def require_label(self, label: str) -> str:
        if label not in self.labels:
            raise ValidationError(f"unknown label {label!r}")
        return label

    # ----- rules --------------------------------------------------------
    def spendable_labels(self, label: str) -> List[str]:
        """Labels whose credit may pay for ``label``: itself first, then its group."""
        self.require_label(label)
        for group in self.equivalence_groups:
            if label in group:
                return [label] + [x for x in group if x != label]
        return [label]

    def debt_limit_hours(self, etd_hours: float) -> Optional[float]:
        """Maximum total debt for a member, or None when unlimited."""
        if self.debt_limit is None:
            return None
        value = float(self.debt_limit["value"])
        if self.debt_limit["type"] == "etd_multiple":
            return value * etd_hours
        return value

    def is_money_eligible(self, attributes: Dict[str, Any]) -> bool:
        return eligibility.evaluate(self.money.eligibility, attributes)
