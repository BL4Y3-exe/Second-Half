"""Fictional clubs and players.

Rosters are generated from a fixed per-club seed, so every run of the
simulator sees exactly the same squads. No real clubs, players or crests.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass

from .tactics import FORMATIONS, role_group

FIRST_NAMES = [
    "Ade", "Bruno", "Cal", "Dario", "Eli", "Femi", "Gus", "Hugo", "Ivo", "Jonah",
    "Kofi", "Luca", "Mateo", "Nico", "Omar", "Pavel", "Quinn", "Rafa", "Sami", "Tomas",
    "Umar", "Vik", "Wes", "Xavi", "Yann", "Zeke", "Arlo", "Bas", "Cyrus", "Dev",
    "Emil", "Finn", "Gael", "Hal", "Isak", "Jude", "Kai", "Leon", "Milo", "Noah",
]
LAST_NAMES = [
    "Achterberg", "Bellamy", "Castell", "Dunmore", "Eckhart", "Faraday", "Galloway",
    "Hartigan", "Ilesanmi", "Jaskolka", "Kerrigan", "Lindqvist", "Marchetti", "Novak",
    "Okonkwo", "Pellegrini", "Quarshie", "Rosales", "Strand", "Tamura", "Underhill",
    "Valdivia", "Whitlock", "Yarrow", "Zabala", "Ashworth", "Brannigan", "Corvin",
    "Delacroix", "Esposito", "Fairweather", "Grimaldi", "Holloway", "Iwobi", "Kestrel",
    "Lombardi", "Mbeki", "Oyelaran", "Petrakis", "Renwick",
]

# Preferred shirt numbers per position code.
SHIRT_NUMBERS = {
    "GK": [1, 13, 31], "RB": [2, 22], "LB": [3, 23], "CB": [4, 5, 6, 15],
    "DM": [6, 16, 8], "CM": [8, 14, 18], "AM": [10, 20], "LM": [11, 17],
    "RM": [7, 17], "LW": [11, 17], "RW": [7, 19], "ST": [9, 19, 21],
}

# Attribute baselines by role group (pace, passing, finishing, stamina,
# pressing, defending, dribbling, goalkeeping).
PROFILES = {
    "GK": dict(pace=45, passing=55, finishing=10, stamina=60, pressing=20, defending=30, dribbling=25, goalkeeping=78),
    "DEF": dict(pace=68, passing=62, finishing=30, stamina=72, pressing=66, defending=76, dribbling=52, goalkeeping=10),
    "MID": dict(pace=68, passing=76, finishing=55, stamina=78, pressing=70, defending=60, dribbling=68, goalkeeping=10),
    "FWD": dict(pace=80, passing=64, finishing=76, stamina=68, pressing=60, defending=35, dribbling=76, goalkeeping=10),
}

BENCH_POSITIONS = ["GK", "CB", "CM", "LW", "ST"]


@dataclass(frozen=True)
class Player:
    id: str
    name: str
    number: int
    position: str
    pace: int
    passing: int
    finishing: int
    stamina: int
    pressing: int
    defending: int
    dribbling: int
    goalkeeping: int

    @property
    def group(self) -> str:
        return role_group(self.position)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ClubSpec:
    key: str
    name: str
    short: str
    colors: tuple[str, str]
    style: str
    formation: str
    quality: int


@dataclass(frozen=True)
class Team:
    side: str  # "HOME" or "AWAY"
    key: str
    name: str
    short: str
    colors: tuple[str, str]
    style: str
    formation: str
    players: tuple[Player, ...]  # first 11 are the starters, in formation slot order

    @property
    def starters(self) -> tuple[Player, ...]:
        return self.players[:11]

    @property
    def bench(self) -> tuple[Player, ...]:
        return self.players[11:]

    def to_dict(self) -> dict:
        return {
            "side": self.side,
            "key": self.key,
            "name": self.name,
            "short": self.short,
            "colors": list(self.colors),
            "style": self.style,
            "formation": self.formation,
            "players": [p.to_dict() for p in self.players],
        }


CLUBS: dict[str, ClubSpec] = {
    c.key: c
    for c in [
        ClubSpec("harbourside", "Harbourside Athletic", "HAR", ("#1f6feb", "#ffffff"), "high_press", "4-3-3", 74),
        ClubSpec("kingsmere", "Kingsmere Rovers", "KMR", ("#d62828", "#fcbf49"), "possession", "4-2-3-1", 73),
        ClubSpec("ashford", "Ashford Vale", "ASV", ("#2a9d8f", "#e9c46a"), "counter", "4-4-2", 71),
        ClubSpec("northgate", "Northgate City", "NGC", ("#6a4c93", "#f1faee"), "possession", "4-3-3", 72),
    ]
}


def _clamp_attr(v: float) -> int:
    return int(max(20, min(97, round(v))))


def build_team(club_key: str, side: str) -> Team:
    """Build a club's 16-player squad (11 starters + 5 bench) for one side."""
    if club_key not in CLUBS:
        raise KeyError(f"Unknown club {club_key!r}; choose from {sorted(CLUBS)}")
    if side not in ("HOME", "AWAY"):
        raise ValueError("side must be HOME or AWAY")
    spec = CLUBS[club_key]
    rng = random.Random(f"club-{club_key}")
    prefix = "h" if side == "HOME" else "a"

    positions = [code for code, _x, _y in FORMATIONS[spec.formation]] + BENCH_POSITIONS
    used_numbers: set[int] = set()
    used_last: set[str] = set()
    players = []
    for i, code in enumerate(positions):
        number = next((n for n in SHIRT_NUMBERS.get(code, []) if n not in used_numbers), None)
        if number is None:
            number = rng.choice([n for n in range(12, 40) if n not in used_numbers])
        used_numbers.add(number)

        last = rng.choice([n for n in LAST_NAMES if n not in used_last])
        used_last.add(last)
        name = f"{rng.choice(FIRST_NAMES)} {last}"

        base = PROFILES[role_group(code)]
        # Starters are a touch better than the bench; quality shifts the whole club.
        lift = spec.quality - 72 + (0 if i < 11 else -3)
        attrs = {k: _clamp_attr(v + lift + rng.gauss(0, 6)) for k, v in base.items()}
        if role_group(code) != "GK":
            attrs["goalkeeping"] = 10
        players.append(Player(id=f"{prefix}-{number:02d}", name=name, number=number, position=code, **attrs))

    return Team(
        side=side,
        key=spec.key,
        name=spec.name,
        short=spec.short,
        colors=spec.colors,
        style=spec.style,
        formation=spec.formation,
        players=tuple(players),
    )
