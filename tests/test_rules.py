"""Project-wide rules: file length limit and no hard-coded categories."""

import os
import re
import unittest

from tbank import ValidationError
from tbank.eligibility import evaluate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_LINES = 500
SKIP_DIRS = {".git", "__pycache__", "demo-data", ".venv"}


def project_files():
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if name.endswith((".py", ".md", ".json", ".toml")):
                yield os.path.join(base, name)


class ProjectRules(unittest.TestCase):
    def test_no_file_over_500_lines(self):
        for path in project_files():
            with open(path, encoding="utf-8") as fh:
                count = sum(1 for _ in fh)
            self.assertLessEqual(count, MAX_LINES, f"{path} has {count} lines")

    def test_package_has_no_hard_coded_care_categories(self):
        pattern = re.compile(r"elder|pet[-_ ]care|dog|nursing", re.IGNORECASE)
        pkg = os.path.join(ROOT, "tbank")
        for base, _, files in os.walk(pkg):
            for name in files:
                if name.endswith(".py"):
                    with open(os.path.join(base, name), encoding="utf-8") as fh:
                        text = fh.read()
                    self.assertIsNone(pattern.search(text), f"category word in {name}")


class EligibilityTests(unittest.TestCase):
    rule = {"any": [{"attr": "age", "op": ">=", "value": 80},
                    {"not": {"attr": "mobility", "op": "==", "value": "full"}}]}

    def test_combinators(self):
        self.assertTrue(evaluate(self.rule, {"age": 85, "mobility": "full"}))
        self.assertTrue(evaluate(self.rule, {"age": 50, "mobility": "limited"}))
        self.assertFalse(evaluate(self.rule, {"age": 50, "mobility": "full"}))

    def test_empty_rule_matches_nobody(self):
        self.assertFalse(evaluate(None, {"age": 99}))

    def test_bad_operator(self):
        with self.assertRaises(ValidationError):
            evaluate({"attr": "age", "op": "~", "value": 1}, {"age": 1})


if __name__ == "__main__":
    unittest.main()
