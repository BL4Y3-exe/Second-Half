"""The demo switch: plants one wrong number in a draft, so the Fact-checker can be seen catching it.

A real model rarely gets a number wrong, so a demo can't count on a catch. With the switch on, the first
story of the match and every goal's first draft get one number changed on purpose before fact-checking,
and the agent trace says so.
"""

from __future__ import annotations

import random
import re

from .fact_checker import NUMBER, FactChecker
from .types import Facts

NUDGES = {0: (7, -3, 9, -5, 11, 13), 1: (2.1, -1.3, 1.3, 3.4), 2: (0.21, -0.03, 0.17, -0.05, 0.33)}  # by decimals


def plant(text: str, facts: Facts, rng: random.Random) -> tuple[str, str, str] | None:
    """The draft with one number changed to one the facts don't have: (new text, what it said, what it says
    now). None when the draft has no number to change."""
    spots = [m for m in NUMBER.finditer(text) if not _in_score(text, m.start(1), m.end(1))]
    if not spots:
        return None
    with_unit = [m for m in spots if m.group(2)]
    spot = rng.choice(with_unit or spots)
    raw = spot.group(1)
    comma = "," in raw
    decimals = len(re.split("[.,]", raw)[1]) if re.search("[.,]", raw) else 0
    value = float(raw.replace(",", "."))
    numbers = facts.numbers()
    taken = {round(v, decimals) for v in numbers.values()}
    wrongs = [round(value + nudge, decimals) for nudge in NUDGES.get(decimals, NUDGES[2])]
    wrongs = [w for w in wrongs if w > 0 and w not in taken]
    if not wrongs:
        return None

    def points_back(wrong: float) -> bool:
        """Whether the Fact-checker's "match data has ..." will name the number that was there."""
        hint = FactChecker._expected((spot.group(2) or "").strip(), wrong, numbers, decimals)
        return hint is None or hint.startswith(f"{value:.{decimals}f}")

    wrong = next((w for w in wrongs if points_back(w)), wrongs[0])
    new = f"{wrong:.{decimals}f}"
    if comma:
        new = new.replace(".", ",")
    said = spot.group(0).strip()
    return text[: spot.start(1)] + new + text[spot.end(1):], said, said.replace(raw, new, 1)


def _in_score(text: str, start: int, end: int) -> bool:
    """Whether the number is one side of a score like 2-1, which a planted slip leaves alone."""
    return bool(re.match(r"\s*[-–]\s*\d", text[end:]) or re.search(r"\d\s*[-–]\s*$", text[:start]))
