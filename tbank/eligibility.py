"""Data-driven eligibility rules evaluated against member attributes.

A rule is plain data, for example::

    {"all": [
        {"attr": "age", "op": ">=", "value": 65},
        {"attr": "mobility", "op": "==", "value": "limited"}
    ]}

Supported combinators: ``all``, ``any``, ``not``.
Supported operators: ==, !=, >, >=, <, <=, in, contains.
A missing attribute never matches. An empty rule matches nobody.
"""

from typing import Any, Mapping

from .errors import ValidationError

_OPS = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    "in": lambda a, b: a in b,
    "contains": lambda a, b: b in a,
}


def evaluate(rule: Any, attributes: Mapping[str, Any]) -> bool:
    """Return True if ``attributes`` satisfy ``rule``."""
    if not rule:
        return False
    if not isinstance(rule, Mapping):
        raise ValidationError(f"eligibility rule must be an object: {rule!r}")
    if "all" in rule:
        return all(evaluate(r, attributes) for r in rule["all"])
    if "any" in rule:
        return any(evaluate(r, attributes) for r in rule["any"])
    if "not" in rule:
        return not evaluate(rule["not"], attributes)
    return _compare(rule, attributes)


def _compare(rule: Mapping[str, Any], attributes: Mapping[str, Any]) -> bool:
    try:
        attr, op, expected = rule["attr"], rule["op"], rule["value"]
    except KeyError as exc:
        raise ValidationError(f"rule is missing {exc}: {rule!r}") from None
    if op not in _OPS:
        raise ValidationError(f"unknown operator {op!r}")
    if attr not in attributes:
        return False
    try:
        return bool(_OPS[op](attributes[attr], expected))
    except TypeError:
        return False


def validate(rule: Any) -> None:
    """Raise ValidationError if ``rule`` is malformed."""
    evaluate(rule, {})  # structural errors surface even with no attributes
    if isinstance(rule, Mapping):
        for key in ("all", "any"):
            for sub in rule.get(key, []):
                validate(sub)
        if "not" in rule:
            validate(rule["not"])
