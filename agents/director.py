"""Director: decides what goes on screen, when, and for how long.

Picks a graphics plugin, builds the Telestrator drawing from real event
geometry, and schedules items so graphics never pile up on top of each other.
"""

from __future__ import annotations

from mcp_server import MatchTools, list_plugins

from . import templates
from .types import Facts, Moment

PLUGIN_FOR = {
    "goal": "goal-card", "big_chance": "shot-card", "shot_speed": "shot-card", "killer_pass": "pass-card",
    "counter_press": "press-card",
    "momentum_swing": "momentum-bar", "sprint_speed": "player-tag", "distance_10k": "player-tag",
    "recap": "recap-card",
}
MAX_QUEUE_S = 20.0  # wall seconds an item may wait for its slot before it is dropped (priority 2+)
MAX_LATE_S = 25.0  # wall seconds after a moment when it is no longer worth showing (priority 2+)
# What an outside plugin can ask for in its manifest's "needs", and the tool that answers it.
NEEDS = {
    "xg_race": lambda tools: tools.get_xg_race(),
    "score": lambda tools: tools.get_score(),
}


def _count(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


class Director:
    name = "director"

    def __init__(self, speed: float, tools: MatchTools | None = None):
        self.speed = speed
        self.tools = tools
        self.plugins = {p["id"]: p for p in list_plugins()}
        self.busy_until: dict[str, float] = {}  # slot -> match time it frees up
        self._n = 0

    def too_late(self, moment: Moment, now: float) -> str | None:
        """Why a moment is no longer news, or None. Goals and recaps always go out."""
        late_wall = (now - moment.t) / self.speed
        if moment.priority > 1 and late_wall > MAX_LATE_S:
            return f"too late: it happened {late_wall:.0f} s ago"
        return None

    def direct(self, moment: Moment, facts: Facts, now: float, fallback: bool) -> tuple[dict | None, str]:
        late = self.too_late(moment, now)
        if late:
            return None, late
        plugin_id = "stat-card" if fallback and moment.kind != "recap" else PLUGIN_FOR.get(moment.kind, "stat-card")
        outside = None if fallback else self._outside_plugin(moment.kind)
        if outside is not None:
            plugin_id = outside["id"]
        plugin = self.plugins[plugin_id]
        slot = plugin["slot"]
        duration = float(plugin["default_duration_s"])
        start = max(now + 0.3, self.busy_until.get(slot, 0.0))
        wait_wall = (start - now) / self.speed
        if moment.priority > 1 and wait_wall > MAX_QUEUE_S:
            return None, f"dropped: {slot} is busy for another {wait_wall:.0f} s"
        if moment.priority == 1:
            start = now + 0.3  # must-show items go straight on
        self.busy_until[slot] = start + duration * self.speed
        self._n += 1
        item = {
            "id": f"ov-{self._n:04d}",
            "moment_id": moment.id,
            "kind": moment.kind,
            "clock": moment.clock,
            "show_at": round(start, 1),
            "duration_s": duration,
            "priority": moment.priority,
            "plugin": plugin_id,
            "slot": slot,
            "team": moment.team,
            "player": moment.player,
            "headline": self._headline(moment, facts),
            "data": self._outside_data(plugin, facts) if outside else self._data(plugin_id, moment, facts),
            "telestrator": self._telestrator(moment, facts),
            "facts_checked": True,
            "fallback": fallback,
            "source_events": moment.source_events,
        }
        if outside is not None:
            item["plugin_info"] = {"builtin": False, "name": plugin["name"], "author": plugin["author"],
                                   "entry": f"/plugins/{plugin['id']}/{plugin['entry']}",
                                   "height_px": plugin.get("height_px", 150)}
        return item, f"{plugin['name']} in the {slot} slot for {duration:.0f} s" + (
            f" (plugin by {plugin['author']}, sandboxed)" if outside else "") + (
            f", Telestrator with {_count(len(item['telestrator']['arrows']), 'arrow')}" if item["telestrator"] else "")

    def _outside_plugin(self, kind: str) -> dict | None:
        """An installed third-party plugin made for this kind of moment, if its data can be supplied."""
        if self.tools is None:
            return None
        for p in self.plugins.values():
            if p.get("builtin") or not p.get("enabled", True) or kind not in p.get("moments", []):
                continue
            if all(need in NEEDS for need in p.get("needs", [])) and p.get("entry"):
                return p
        return None

    def _outside_data(self, plugin: dict, facts: Facts) -> dict:
        f = facts.values
        data = {k: f[k] for k in ("team", "team_short", "momentum", "tilt_recent", "shots_recent") if k in f}
        for need in plugin.get("needs", []):
            data[need] = NEEDS[need](self.tools)
        return data

    def _headline(self, moment: Moment, facts: Facts) -> str:
        f = facts.values
        return {
            "goal": f"GOAL · {f.get('player', '')}",
            "big_chance": "BIG CHANCE",
            "shot_speed": "ROCKET",
            "killer_pass": "KILLER PASS",
            "counter_press": f"COUNTER-PRESS · {f.get('team_short', '')}",
            "momentum_swing": f"MOMENTUM · {f.get('team_short', '')}",
            "sprint_speed": "TOP SPEED",
            "distance_10k": "10 KM CLUB",
            "recap": str(f.get("label", "")).upper(),
        }.get(moment.kind, moment.label)

    def _data(self, plugin_id: str, moment: Moment, facts: Facts) -> dict:
        f = facts.values
        keep = {
            "goal-card": ("player", "assist", "xg", "distance_m", "shot_speed_kmh", "score_home", "score_away",
                          "won_back_s", "half_space"),
            "shot-card": ("player", "xg", "shot_speed_kmh", "distance_m", "outcome_text", "outcome_text_es",
                          "won_back_s", "half_space"),
            "pass-card": ("passer", "receiver", "difficulty", "difficulty_label", "distance_m", "lane_gap_m"),
            "press-card": ("team", "player", "won_back_s", "shot_after_s", "xg", "outcome_text", "outcome_text_es",
                           "counter_press_wins", "counter_presses"),
            "momentum-bar": ("team", "team_short", "momentum", "tilt_recent", "shots_recent"),
            "player-tag": ("player", "top_speed_kmh", "distance_km"),
            "recap-card": ("score_home", "score_away", "home_xg", "away_xg", "home_shots", "away_shots",
                           "home_poss", "away_poss", "best_player", "best_rating"),
            "stat-card": (),
        }[plugin_id]
        data = {k: f[k] for k in keep if k in f}
        if plugin_id == "stat-card":
            data["line"] = templates.fallback(moment.kind, f)
            data["line_es"] = templates.fallback(moment.kind, f, "es")
        if plugin_id == "recap-card":
            data["ratings"] = f.get("ratings", [])
            data["goals"] = f.get("goals", [])
            if "shapes" in f:
                data["shapes"] = f["shapes"]
        return data

    def _telestrator(self, moment: Moment, facts: Facts) -> dict | None:
        seq = facts.sequence
        if not seq:
            return None
        arrows = []
        for ev in seq:
            if ev["type"] == "pass" and ev["outcome"] == "complete":
                arrows.append({"kind": "pass", "from": ev["from"], "to": ev["to"], "t": ev["t"]})
            elif ev["type"] == "carry":
                arrows.append({"kind": "carry", "from": ev["from"], "to": ev["to"], "t": ev["t"]})
            elif ev["type"] == "shot":
                arrows.append({"kind": "shot", "from": ev["from"], "to": ev["to"], "t": ev["t"]})
        arrows = arrows[-6:]
        zones = []
        highlight = sorted({ev["player"] for ev in seq if ev.get("player")})
        shot = next((ev for ev in seq if ev["type"] == "shot"), None)
        if shot is not None:
            zones.append({"kind": "circle", "center": shot["from"], "r": 2.5, "label": f"{facts.values['xg']:.2f} xG"})
        if moment.kind == "killer_pass" and seq:
            ps = seq[0]
            mid = [(ps["from"][0] + ps["to"][0]) / 2, (ps["from"][1] + ps["to"][1]) / 2]
            zones.append({"kind": "circle", "center": [round(mid[0], 1), round(mid[1], 1)],
                          "r": max(1.5, facts.values.get("lane_gap_m", 2.0)), "label": "the gap"})
            highlight = sorted({ps["player"], ps["receiver"]})
        regain = seq[0] if seq[0]["type"] == "possession_change" else None
        if regain is not None and (moment.kind == "counter_press" or "won_back_s" in facts.values):
            zones.append({"kind": "circle", "center": regain["at"], "r": 2.0, "label": "won back"})
        if not arrows and not zones:
            return None
        # The stretch of play the browser replays under the drawing, in match seconds.
        times = [a["t"] for a in arrows] or [seq[0]["t"]]
        window = [round(min(times) - 2.0, 1), round(max(times) + 2.0, 1)]
        return {"arrows": arrows, "zones": zones, "highlight": highlight, "window": window}
