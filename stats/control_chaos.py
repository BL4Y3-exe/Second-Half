"""Control vs Chaos: a rolling 0 to 100 read on how settled the game is.

100 means long, clean possessions; 0 means turnovers and duels everywhere.
"""

from __future__ import annotations

from collections import deque

WINDOW_S = 300.0
DUELS = {"tackle", "foul", "interception"}


class ControlChaos:
    def __init__(self, window_s: float = WINDOW_S) -> None:
        self.window = window_s
        self.passes: deque[tuple[float, bool]] = deque()
        self.turnovers: deque[float] = deque()
        self.duels: deque[float] = deque()
        self.sequences: deque[tuple[float, int]] = deque()  # (end time, passes in sequence)
        self._seq_passes = 0

    def update(self, ev: dict) -> None:
        t, typ = ev["t"], ev["type"]
        if typ == "pass":
            ok = ev["outcome"] == "complete"
            self.passes.append((t, ok))
            if ok:
                self._seq_passes += 1
        elif typ == "possession_change":
            self.turnovers.append(t)
            self.sequences.append((t, self._seq_passes))
            self._seq_passes = 0
        elif typ in ("kickoff", "goal"):
            self._seq_passes = 0
        if typ in DUELS:
            self.duels.append(t)
        self._trim(t)

    def _trim(self, now: float) -> None:
        cut = now - self.window
        for q in (self.passes, self.sequences):
            while q and q[0][0] < cut:
                q.popleft()
        for q in (self.turnovers, self.duels):
            while q and q[0] < cut:
                q.popleft()

    def index(self) -> float:
        minutes = self.window / 60
        completion = sum(ok for _t, ok in self.passes) / len(self.passes) if self.passes else 0.75
        seqs = [n for _t, n in self.sequences] + [self._seq_passes]
        avg_seq = sum(seqs) / len(seqs)
        turnover_rate = len(self.turnovers) / minutes  # per minute
        duel_rate = len(self.duels) / minutes
        score = (0.3 * min(1.0, max(0.0, (completion - 0.55) / 0.35))
                 + 0.3 * min(1.0, avg_seq / 8.0)
                 + 0.2 * (1.0 - min(1.0, turnover_rate / 3.0))
                 + 0.2 * (1.0 - min(1.0, duel_rate / 3.0)))
        return round(100 * score, 1)
