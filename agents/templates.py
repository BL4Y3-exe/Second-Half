"""Scripted text for mock mode, in English and Spanish.

Every number in these templates comes from the Analyst's facts, so the
Fact-checker can verify it. A real model gets the same facts in its prompt.
"""

from __future__ import annotations

import random
import string
from collections.abc import Callable

Facts = dict
Rule = tuple[Callable[[Facts], bool], str]

ALWAYS: Callable[[Facts], bool] = lambda f: True  # noqa: E731


def has(*keys: str) -> Callable[[Facts], bool]:
    return lambda f: all(f.get(k) not in (None, "", 0) for k in keys)


# ---------------------------------------------------------------------------
# Storyteller: one "why it matters" line per moment (English, analyst-neutral)

STORY: dict[str, list[Rule]] = {
    "goal": [
        (has("assist", "passes"), "{assist} picks out {player}, who finishes from {distance_m} m. A {passes}-pass move "
                                  "worth {xg:.2f} xG, and it's {home_short} {score_home}-{score_away} {away_short}."),
        (has("assist"), "{player} converts {assist}'s pass from {distance_m} m, a {xg:.2f} xG chance struck at "
                        "{shot_speed_kmh} km/h. {home_short} {score_home}-{score_away} {away_short}."),
        (ALWAYS, "{player} scores from {distance_m} m at {shot_speed_kmh} km/h. The chance was worth {xg:.2f} xG; "
                 "{home_short} {score_home}-{score_away} {away_short}."),
    ],
    "big_chance": [
        (has("passes"), "{player} should score: a {xg:.2f} xG chance from {distance_m} m at the end of a move of "
                        "{passes} passes, but it's {outcome_text}."),
        (ALWAYS, "Huge chance for {player}, {distance_m} m out and worth {xg:.2f} xG, but it's {outcome_text}."),
    ],
    "shot_speed": [
        (ALWAYS, "{player} hits it at {shot_speed_kmh} km/h from {distance_m} m, {outcome_text}."),
        (ALWAYS, "Pure power from {player}: {shot_speed_kmh} km/h from {distance_m} m out, {outcome_text}."),
    ],
    "killer_pass": [
        (lambda f: f.get("lane_gap_m", 0) >= 1.0 and f.get("progress_m", 0) > 0,
         "{passer} threads a {difficulty_label} pass ({difficulty:.2f} difficulty) to {receiver} through a "
         "{lane_gap_m} m gap, gaining {progress_m} m."),
        (lambda f: f.get("progress_m", 0) > 0,  # a pass that splits a defence can still go sideways or back
         "{passer} slips a {difficulty_label} pass past the defender to {receiver}, gaining {progress_m} m."),
        (ALWAYS, "Defence split: {passer} finds {receiver} with a {distance_m} m pass rated {difficulty:.2f} "
                 "for difficulty."),
    ],
    "momentum_swing": [
        (has("final_third_recent"), "{team} are on top: {final_third_recent} passes into the final third in the "
                                    "last 5 minutes, and {tilt_recent}% of the field tilt."),
        (ALWAYS, "The game has turned towards {team}, who own {tilt_recent}% of the final-third passes over the last "
                 "5 minutes."),
    ],
    "sprint_speed": [
        (ALWAYS, "{player} clocks {top_speed_kmh} km/h, the fastest sprint of the match so far."),
    ],
    "distance_10k": [
        (ALWAYS, "{player} has now covered {distance_km} km, one of the first past {milestone_km} km today."),
    ],
}

# Stat-only text the Director falls back to when a story fails fact-checking twice.
FALLBACK: dict[str, str] = {
    "goal": "GOAL {player}. {home_short} {score_home}-{score_away} {away_short}. xG {xg:.2f}.",
    "big_chance": "{player}: {xg:.2f} xG chance from {distance_m} m.",
    "shot_speed": "{player}: shot at {shot_speed_kmh} km/h.",
    "killer_pass": "{passer} to {receiver}: pass difficulty {difficulty:.2f}.",
    "momentum_swing": "{team}: {tilt_recent}% field tilt, last 5 minutes.",
    "sprint_speed": "{player}: {top_speed_kmh} km/h.",
    "distance_10k": "{player}: {distance_km} km covered.",
    "recap": "{home_short} {score_home}-{score_away} {away_short}. xG {home_xg:.2f} - {away_xg:.2f}.",
}
FALLBACK_ES: dict[str, str] = {
    "goal": "GOL de {player}. {home_short} {score_home}-{score_away} {away_short}. xG {xg:.2f}.",
    "big_chance": "{player}: ocasión de {xg:.2f} xG desde {distance_m} m.",
    "shot_speed": "{player}: disparo a {shot_speed_kmh} km/h.",
    "killer_pass": "{passer} a {receiver}: dificultad del pase {difficulty:.2f}.",
    "momentum_swing": "{team}: {tilt_recent}% de dominio territorial, últimos 5 minutos.",
    "sprint_speed": "{player}: {top_speed_kmh} km/h.",
    "distance_10k": "{player}: {distance_km} km recorridos.",
    "recap": FALLBACK["recap"],
}

# ---------------------------------------------------------------------------
# Persona: the same moment for each viewer mode, in each language

PERSONA: dict[str, dict[str, dict[str, list[Rule]]]] = {
    "en": {
        "casual": {
            "goal": [(has("assist"), "GOAL! {assist} sets it up and {player} finishes it off. "
                                     "{home_short} {score_home}-{score_away} {away_short}!"),
                     (ALWAYS, "GOAL! {player} scores for {team}! "
                              "{home_short} {score_home}-{score_away} {away_short}.")],
            "big_chance": [(ALWAYS, "So close! {player} had a great chance there, but it's {outcome_text}.")],
            "shot_speed": [(ALWAYS, "What a hit from {player}! {shot_speed_kmh} km/h!")],
            "killer_pass": [(ALWAYS, "Lovely pass from {passer} to set {receiver} free.")],
            "momentum_swing": [(ALWAYS, "{team} are pushing hard now.")],
            "sprint_speed": [(ALWAYS, "Look at {player} go! {top_speed_kmh} km/h, nobody has been faster today.")],
            "distance_10k": [(ALWAYS, "{player} has run over {milestone_km} km already!")],
        },
        "player": {
            "goal": [(ALWAYS, "{player} today: {player_goals} {goals_word} from {player_shots} {shots_word}, "
                              "{player_xg:.2f} xG.")],
            "big_chance": [(ALWAYS, "{player} today: {player_shots} {shots_word}, {player_xg:.2f} xG, "
                                    "{player_goals} {goals_word}.")],
            "shot_speed": [(ALWAYS, "{player} today: {player_shots} {shots_word}, hardest at {shot_speed_kmh} km/h.")],
            "killer_pass": [(ALWAYS, "{passer} today: {passer_passes} passes, {passer_completion}% completed.")],
            "momentum_swing": [(ALWAYS, "{team}: {team_shots} shots, {team_xg:.2f} xG so far.")],
            "sprint_speed": [(ALWAYS, "{player} today: {distance_km} km run, top speed {top_speed_kmh} km/h.")],
            "distance_10k": [(ALWAYS, "{player} today: {distance_km} km run, top speed {top_speed_kmh} km/h.")],
        },
    },
    "es": {
        "casual": {
            "goal": [(has("assist"), "¡GOL! {assist} la pone y {player} define. "
                                     "{home_short} {score_home}-{score_away} {away_short}."),
                     (ALWAYS, "¡GOL de {player}! {home_short} {score_home}-{score_away} {away_short}.")],
            "big_chance": [(ALWAYS, "¡Qué ocasión! {player} la tuvo, pero {outcome_text_es}.")],
            "shot_speed": [(ALWAYS, "¡Vaya disparo de {player}! {shot_speed_kmh} km/h.")],
            "killer_pass": [(ALWAYS, "Gran pase de {passer} para dejar solo a {receiver}.")],
            "momentum_swing": [(ALWAYS, "{team} aprieta ahora.")],
            "sprint_speed": [(ALWAYS, "¡Cómo corre {player}! {top_speed_kmh} km/h, nadie ha ido más rápido hoy.")],
            "distance_10k": [(ALWAYS, "¡{player} ya ha corrido más de {milestone_km} km!")],
        },
        "analyst": {
            "goal": [(has("assist"), "{assist} asiste y {player} marca desde {distance_m} m: una ocasión de "
                                     "{xg:.2f} xG a {shot_speed_kmh} km/h. "
                                     "{home_short} {score_home}-{score_away} {away_short}."),
                     (ALWAYS, "{player} marca desde {distance_m} m a {shot_speed_kmh} km/h, una ocasión de {xg:.2f} "
                              "xG. {home_short} {score_home}-{score_away} {away_short}.")],
            "big_chance": [(ALWAYS, "Ocasión clarísima de {player}: {xg:.2f} xG desde {distance_m} m, "
                                    "pero {outcome_text_es}.")],
            "shot_speed": [(ALWAYS, "{player} dispara a {shot_speed_kmh} km/h desde {distance_m} m.")],
            "killer_pass": [(lambda f: f.get("progress_m", 0) > 0,
                             "{passer} encuentra a {receiver} con un pase de dificultad {difficulty:.2f} "
                             "que gana {progress_m} m."),
                            (ALWAYS, "{passer} encuentra a {receiver} con un pase de {distance_m} m y dificultad "
                                     "{difficulty:.2f}.")],
            "momentum_swing": [(ALWAYS, "{team} domina: {tilt_recent}% de los pases al último tercio en los últimos "
                                        "5 minutos.")],
            "sprint_speed": [(ALWAYS, "{player} alcanza {top_speed_kmh} km/h, el sprint más rápido del partido.")],
            "distance_10k": [(ALWAYS, "{player} ya suma {distance_km} km recorridos.")],
        },
        "player": {
            "goal": [(ALWAYS, "{player} hoy: {player_goals} {goals_word_es}, {player_shots} {shots_word_es}, "
                              "{player_xg:.2f} xG.")],
            "big_chance": [(ALWAYS, "{player} hoy: {player_shots} {shots_word_es}, {player_xg:.2f} xG.")],
            "shot_speed": [(ALWAYS, "{player} hoy: {player_shots} {shots_word_es}, el más fuerte a "
                                    "{shot_speed_kmh} km/h.")],
            "killer_pass": [(ALWAYS, "{passer} hoy: {passer_passes} pases, {passer_completion}% completados.")],
            "momentum_swing": [(ALWAYS, "{team}: {team_shots} tiros y {team_xg:.2f} xG hasta ahora.")],
            "sprint_speed": [(ALWAYS, "{player} hoy: {distance_km} km recorridos, punta de {top_speed_kmh} km/h.")],
            "distance_10k": [(ALWAYS, "{player} hoy: {distance_km} km recorridos, punta de {top_speed_kmh} km/h.")],
        },
    },
}

RECAP: dict[str, str] = {
    "en": ("{label}: {home} {score_home}-{score_away} {away}. xG {home_xg:.2f} to {away_xg:.2f}, shots "
           "{home_shots} to {away_shots}, possession {home_poss}% to {away_poss}%.{goals_line} "
           "Top rated: {best_player} ({best_rating:.1f})."),
    "es": ("{label_es}: {home} {score_home}-{score_away} {away}. xG {home_xg:.2f} a {away_xg:.2f}, tiros "
           "{home_shots} a {away_shots}, posesión {home_poss}% a {away_poss}%.{goals_line_es} "
           "Mejor valorado: {best_player} ({best_rating:.1f})."),
}


# ---------------------------------------------------------------------------
# rendering


def fields(template: str) -> list[str]:
    return [name for _lit, name, _spec, _conv in string.Formatter().parse(template) if name]


def pick(rules: list[Rule], facts: Facts, rng: random.Random) -> str:
    usable = [tpl for cond, tpl in rules if cond(facts) and all(k in facts for k in fields(tpl))]
    if not usable:
        raise KeyError("no template fits these facts")
    return rng.choice(usable[:2]) if len(usable) > 1 else usable[0]


def render(template: str, facts: Facts) -> str:
    return template.format_map(facts)


def mutate(facts: Facts, template: str, rng: random.Random) -> Facts:
    """Get one number in the template wrong, the way a model sometimes does."""
    numeric = [k for k in fields(template) if isinstance(facts.get(k), (int, float)) and not k.startswith("score")
               and k not in ("minute",)]
    if not numeric:
        return facts
    key = rng.choice(numeric)
    value = facts[key]
    taken = {round(float(v), 2) for v in facts.values() if isinstance(v, (int, float))}
    if isinstance(value, float) and value < 1.5:
        candidates = [round(value + d, 2) for d in (0.17, 0.21, -0.11, 0.33)]
    elif isinstance(value, float):
        candidates = [round(value + d, 1) for d in (1.3, 2.1, -1.4)]
    else:
        candidates = [value + d for d in (9, 13, -7, 21)]
    candidates = [c for c in candidates if c > 0 and round(float(c), 2) not in taken]
    if not candidates:
        return facts
    wrong = dict(facts)
    wrong[key] = candidates[0] if isinstance(value, float) else int(candidates[0])
    return wrong


def story(context: dict, rng: random.Random, allow_mistake: bool = False) -> str:
    facts, kind = context["facts"], context["kind"]
    tpl = pick(STORY[kind], facts, rng)
    if allow_mistake:
        return render(tpl, mutate(facts, tpl, rng))
    return render(tpl, facts)


def persona(context: dict, rng: random.Random) -> str:
    facts, kind, mode, lang = context["facts"], context["kind"], context["mode"], context["lang"]
    if lang == "en" and mode == "analyst":
        return context["approved"]
    rules = PERSONA.get(lang, {}).get(mode, {}).get(kind)
    if not rules:
        return context["approved"]
    return render(pick(rules, facts, rng), facts)


def recap(context: dict, rng: random.Random) -> str:
    return render(RECAP[context["lang"]], context["facts"])


def fallback(kind: str, facts: Facts, lang: str = "en") -> str:
    tpl = (FALLBACK_ES if lang == "es" else FALLBACK).get(kind)
    if tpl is None or not all(k in facts for k in fields(tpl)):
        return facts.get("label", "")
    return render(tpl, facts)
