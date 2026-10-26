"""Fact-checker: every number, formation and player name in a draft must match match state.

Deterministic on purpose: it reads numbers out of the text and compares them
with the Analyst's facts, at the precision the text uses. On a mismatch it
rejects with reasons the Storyteller can act on.
"""

from __future__ import annotations

import re

from .types import Facts, Verdict

# A decimal comma counts too ("0,45 xG" in Spanish).
NUMBER = re.compile(r"(?<![\w.,])(\d+(?:[.,]\d+)?)(?![\d])\s*(km/h|km|xG|m\b|%|'|difficulty)?")
# A formation ("4-2-3-1") is checked whole against the facts' strings, not read as four numbers.
FORMATION = re.compile(r"(?<![\w.,-])\d(?:-\d){2,4}(?![\w-])")
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
        names = set(_strings(facts.values))
        checked: list[str] = []
        problems: list[str] = []

        for m in FORMATION.finditer(text):
            checked.append(m.group())
            if m.group() not in names:
                problems.append(f"says {m.group()}, which isn't a shape in the match data")
        for m in NUMBER.finditer(FORMATION.sub(" ", text)):
            raw, unit = m.group(1), (m.group(2) or "").strip()
            value = float(raw.replace(",", "."))
            decimals = len(re.split("[.,]", raw)[1]) if re.search("[.,]", raw) else 0
            tol = 0.5 * 10 ** -decimals + 1e-9
            checked.append(raw + (f" {unit}" if unit else ""))
            if any(abs(value - round(v, decimals)) <= tol for v in numbers.values()):
                continue
            if "," in raw and float(raw.replace(",", "")) in numbers.values():  # "1,250" as a thousands separator
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


def _strings(value: object):
    """Every string in the facts, including inside lists and dicts (the recap's ratings and goals)."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _strings(v)
