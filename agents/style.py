"""House style for on-screen lines, checked in code the way the facts are.

A graphic is read in a few seconds, so it carries few numbers, and a casual
viewer gets plain words. The Director sends a busy story back once; the
Persona redrafts a version once, then uses the scripted line.
"""

from __future__ import annotations

import re

NUMBER = re.compile(r"(?<![\w.,])\d+(?:[.,]\d+)?(?!\d)")
# A score ("2-1") reads as one thing and doesn't count against the limit.
SCORE = re.compile(r"(?<![\w.,])\d+\s*[-–]\s*\d+(?![.,]?\d)")
MAX_NUMBERS = {"casual": 1}
DEFAULT_MAX = 3
# Words a casual viewer won't know, in English and Spanish.
JARGON = re.compile(r"\b(xG|expected goals|goles esperados|field tilt|tilt|inclinación|lanes?|carril(?:es)?|"
                    r"half-spaces?|difficulty|dificultad)\b", re.IGNORECASE)


def count_numbers(text: str) -> int:
    return len(NUMBER.findall(SCORE.sub(" ", text)))


def problems(text: str, mode: str = "analyst") -> list[str]:
    """What a line breaks of the house style, worded so a writer can fix it."""
    out: list[str] = []
    n, most = count_numbers(text), MAX_NUMBERS.get(mode, DEFAULT_MAX)
    if n > most and mode == "casual":
        out.append(f"has {n} numbers, but a casual viewer gets one at most; keep the one that matters most")
    elif n > most:
        out.append(f"has {n} numbers, too many for one graphic; keep the {most} that matter most")
    if mode == "casual":
        words = sorted({m.group(0) for m in JARGON.finditer(text)}, key=str.lower)
        if words:
            out.append(f"uses {', '.join(words)}, which a casual viewer won't know; say it in plain words")
    return out
