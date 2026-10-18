"""What the agents hand to each other."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Moment:
    """A candidate key moment flagged by the Spotter."""

    id: str
    kind: str  # goal, big_chance, shot_speed, killer_pass, momentum_swing, sprint_speed, distance_10k, recap
    t: float
    clock: str
    priority: int  # 1 must show, 2 worth showing, 3 filler
    team: str | None
    player: str | None
    label: str
    trigger: dict
    source_events: list[str] = field(default_factory=list)


@dataclass
class Facts:
    """Numbers and names the Analyst pulled from match state. The only things a story may claim."""

    moment_id: str
    values: dict[str, float | int | str]
    sequence: list[dict] = field(default_factory=list)  # events that led up to the moment
    tool_calls: list[str] = field(default_factory=list)

    def numbers(self) -> dict[str, float]:
        return {k: float(v) for k, v in self.values.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}

    def for_model(self) -> dict:
        """The facts as a model sees them: without the helpers the scripted templates use (plural words,
        Spanish snippets, flattened copies of the recap lists), which only add noise to a prompt."""
        helper_prefixes = ("goals_line", "rating_", "goal_minute_", "goal_scorer_")
        return {k: v for k, v in self.values.items()
                if not k.endswith(("_word", "_es")) and not k.startswith(helper_prefixes)}


@dataclass
class Draft:
    moment_id: str
    text: str
    attempt: int
    headline: str = ""


@dataclass
class Verdict:
    approved: bool
    checked: list[str]  # the numbers and names that were checked
    problems: list[str]  # human-readable reasons for a rejection


@dataclass
class TraceStep:
    """One handoff, for the agent trace panel."""

    id: str
    t: float
    clock: str
    moment_id: str
    agent: str
    action: str
    summary: str
    status: str = "ok"  # ok, rejected, retry, fallback, skipped
    ms: float = 0.0
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)
