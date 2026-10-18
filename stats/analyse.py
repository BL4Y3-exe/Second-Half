"""Run the stats engine over a whole saved match."""

from __future__ import annotations

from .state import MatchState


def analyse_match(match: dict) -> MatchState:
    """Feed a saved match (from `python -m simulator export`) through the stats engine, in time order."""
    state = MatchState(match["meta"], match["lineups"][0])
    events, frames = match["events"], match["frames"]
    i = j = 0
    while i < len(events) or j < len(frames):
        # At equal times, events go first so pass lanes use the positions just before the pass.
        if j >= len(frames) or (i < len(events) and events[i]["t"] <= frames[j]["t"]):
            state.apply_event(events[i])
            i += 1
        else:
            state.apply_frame(frames[j])
            j += 1
    return state
