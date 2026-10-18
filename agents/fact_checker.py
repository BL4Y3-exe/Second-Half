"""Fact-checker: every number and player name in a draft must match match state.

Deterministic on purpose: it reads numbers out of the text and compares them
with the Analyst's facts, at the precision the text uses. On a mismatch it
rejects with reasons the Storyteller can act on.
"""

from __future__ import annotations

import re

from .types import Facts, Verdict

NUMBER = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(?![\d])\s*(km/h|km|xG|m\b|%|'|difficulty)?")
# What kind of fact a number with this unit should match (by fact-name suffix or substring).
UNIT_KEYS = {"km/h": ("_kmh",), "km": ("_km",), "xG": ("xg",), "m": ("_m",), "%": ("pct", "tilt", "completion", "poss"),
             "'": ("minute",), "difficulty": ("difficulty",)}


class FactChecker:
    name = "fact_checker"

    def __init__(self, roster: dict[str, dict]):
        # last name -> full names of every player in the match
        self.by_last: dict[str, set[str]] = {}
        for info in roster.values():
            self.by_last.setdefault(info["name"].split()[-1], set()).add(info["name"])

    def check(self, text: str, facts: Facts) -> Verdict:
        numbers = facts.numbers()
        names = {v for v in facts.values.values() if isinstance(v, str)}
        checked: list[str] = []
        problems: list[str] = []

        for m in NUMBER.finditer(text):
            raw, unit = m.group(1), (m.group(2) or "").strip()
            value = float(raw)
            decimals = len(raw.split(".")[1]) if "." in raw else 0
            tol = 0.5 * 10 ** -decimals + 1e-9
            checked.append(raw + (f" {unit}" if unit else ""))
            if any(abs(value - round(v, decimals)) <= tol for v in numbers.values()):
                continue
            expected = self._expected(unit, value, numbers, decimals)
            problems.append(f"says {raw}{' ' + unit if unit else ''}, but match data has "
                            f"{expected}" if expected else f"says {raw}, which isn't in the match data")

        for last, full_names in self.by_last.items():
            if re.search(rf"\b{re.escape(last)}\b", text):
                checked.append(last)
                if not full_names & names:
                    problems.append(f"mentions {last}, who isn't part of this moment")
        return Verdict(not problems, checked, problems)

    @staticmethod
    def _expected(unit: str, value: float, numbers: dict[str, float], decimals: int) -> str | None:
        """The fact the writer most likely meant: same unit, closest value."""
        keys = UNIT_KEYS.get(unit, ())
        candidates = [(k, v) for k, v in numbers.items()
                      if any(k.endswith(part) if part.startswith("_") else part in k for part in keys)]
        if not candidates:
            return None
        k, v = min(candidates, key=lambda kv: abs(kv[1] - value))
        return f"{v:.{decimals}f}{' ' + unit if unit and unit != chr(39) else ''} ({k})"
