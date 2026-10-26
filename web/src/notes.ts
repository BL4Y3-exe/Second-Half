import type { Lang, Mode } from "./types";

// What each control and number on the page does, in a sentence. Hover or focus anything with a note to read it;
// the viewer bar also spells out the current choice, in the viewer's language.

export const MODE_NOTES: Record<Mode, Record<Lang, string>> = {
  analyst: {
    en: "For fans who love tactics and numbers. The pitch draws each side's shape and marks every counter-press, and each story keeps the sharpest stats, three at most, and says what they show.",
    es: "Para quien disfruta de la táctica y los números. El campo dibuja la estructura de cada equipo y marca cada contrapresión, y cada historia se queda con los datos más reveladores, tres como mucho, y explica qué muestran.",
  },
  casual: {
    en: "For watching with friends. Warm, simple lines with one number at most, and graphics without stat chips or jargon like xG.",
    es: "Para ver el partido con amigos. Frases cercanas y sencillas, con un número como mucho, y gráficos sin cifras sueltas ni jerga como xG.",
  },
  player: {
    en: "Every story follows the player in it: their goals, shots, speed and distance so far.",
    es: "Cada historia sigue al jugador protagonista: sus goles, tiros, velocidad y distancia hasta ahora.",
  },
};

export const LANG_NOTES: Record<Lang, Record<Lang, string>> = {
  en: {
    en: "Stories and graphics in English.",
    es: "Historias y gráficos en inglés.",
  },
  es: {
    en: "The Persona agent rewrites every story in Spanish, and the Fact-checker checks it again.",
    es: "El agente Persona reescribe cada historia en español y el Fact-checker la comprueba de nuevo.",
  },
};

/** What supporting a club does; `other` is the club whose minor graphics are skipped, null for neutral. */
export function favouriteNote(lang: Lang, other: string | null): string {
  if (!other) {
    return lang === "es"
      ? "Sin bando, así que sale al aire cada gráfico que programa el Director."
      : "No side taken, so every graphic the Director schedules goes on air.";
  }
  return lang === "es"
    ? `Los goles y los resúmenes salen para los dos equipos, pero se omiten los demás gráficos sobre el ${other}.`
    : `Goals and recaps still show for both sides, but other graphics about ${other} are skipped.`;
}

export const VIEWER_GROUPS: Record<"mode" | "lang" | "favourite", Record<Lang, string>> = {
  mode: { en: "Who's watching", es: "Quién mira" },
  lang: { en: "Language", es: "Idioma" },
  favourite: { en: "Supporting", es: "Con quién va" },
};

export const NOTES = {
  watch: "The match as a TV broadcast, with each viewer's own graphics and the agents behind them along the bottom.",
  analysis:
    "Everything behind the broadcast: momentum over the whole match, each agent's work on every moment, every version of each story, and the team numbers.",
  setup: "Pick the clubs and kick off a new match. The address bar keeps its number, so the link replays it.",
  pause: "Stop the picture on this moment to study it (or press Space). The match keeps going for everyone else.",
  resume: "Jump back to the live match, which kept playing while your picture was stopped (or press Space).",
  profile: "How this viewer watches: how much detail, which language and which club they support.",
  addViewer: "Add a guest with their own mode, language and club. Their screen plays in the corner.",
  behind:
    "Second Half is a multi-agent system: seven AI agents work every moment as a team. This strip shows the ones that made the graphic on screen (or the last one), in the order they handed it on.",
  program: "The live picture with the graphics the Director puts on air, as your viewer settings show them.",
  follow: "Keep showing whichever moment is on air now.",
  versions: "The Persona agent rewrites each approved story for every viewer mode and language, and each version is checked again.",
  home: "The home club. Clubs, players and matches are synthetic, so no real data is used.",
  away: "The away club. Clubs, players and matches are synthetic, so no real data is used.",
  kickOff: "Start a new match between these clubs at the speed you picked.",
  speed:
    "The match plays at 8x, so the clock ticks over a match minute every 7 seconds and a whole match takes about 12 minutes.",
  plant:
    "Demo switch: changes one number in the first story and in every goal's first draft, so you can watch the Fact-checker catch it. The agent trace marks each one. Takes effect at kick off.",
  model: "The model writing the stories: a Microsoft Foundry deployment, or mock for the built-in scripted writer.",
  momentum:
    "Which team is on top right now, from shots, chances, corners and passes into the final third. Recent play counts most.",
  controlChaos:
    "How settled the last 5 minutes have been: long passing spells push it towards Control, turnovers and duels towards Chaos.",
  replay: "The Telestrator is redrawing the move that led to this moment, from the real event positions.",
  factChecked: "Every number and name in this graphic matched the match data.",
  live: {
    connecting: "Connecting to the match server.",
    live: "The match is being played and commented on right now.",
    finished: "The match is over. Press Kick off to play it again.",
    error: "Can't reach the match server. It retries on its own; Kick off starts a fresh connection.",
  },
} as const;

export const STAT_NOTES: Record<string, string> = {
  xG: "Expected goals: how many goals these chances would usually produce. A 0.30 xG chance is scored about 3 times in 10.",
  Shots: "Every attempt at goal, blocked and off target included.",
  "On target": "Shots that would have gone in without a save.",
  Possession: "Share of the match each team has had the ball.",
  "Pass accuracy": "Share of passes that reached a teammate.",
  "Field tilt": "Share of the passes into the final third: which team is camped in the other half.",
  "Counter-press wins":
    "Balls a team lost in the opponent's half and won back within 8 seconds, Rangnick's rule for counter-pressing.",
  "Pressing (PPDA)":
    "Passes per defensive action: how many passes a team lets the opponent make in the opponent's own 60% of the pitch for each tackle, interception or foul it makes there. Lower means harder pressing: 10 or under is a high press, over 15 a team that sits deep.",
  "Attacks by lane":
    "Where each team gets the ball into the final third, from its own left wing to its right. The half-spaces are the strips between the wings and the centre, along the sides of the penalty area: from there a player can shoot, pass inside or go wide.",
  Corners: "Corner kicks won.",
  "Distance (km)": "How far the whole team has run.",
};

export const AGENT_NOTES: Record<string, string> = {
  spotter: "Watches the live stats and flags moments worth a graphic.",
  analyst: "Looks up the numbers for a moment through the match tools, the same ones the MCP server offers.",
  storyteller: "Writes why the moment matters, using only the Analyst's facts.",
  fact_checker: "Checks every number and name in a draft against the match data. It's plain code, not a model.",
  director: "Sends busy stories back, picks the graphic and its slot, draws the Telestrator, and keeps the screen uncluttered.",
  persona: "Rewrites the approved story for each viewer mode and language.",
  recap: "Writes the half-time and full-time summaries.",
  test: "Not an agent: the demo switch, which changed a number on purpose to show the Fact-checker at work.",
};

export const TOTAL_NOTES: Record<string, string> = {
  moments: "Moments the Spotter flagged for a graphic.",
  "approved first time": "Stories whose first draft passed the Fact-checker.",
  "wrong numbers caught": "Drafts the Fact-checker sent back because a number or name didn't match the match data.",
  "stat-card fallbacks": "Stories that failed fact-checking twice or got no answer from the model, so a plain stat card went out.",
  "held back": "Moments passed over or dropped to keep the screen clear, or because they were no longer news.",
  "planted by the demo switch": "Wrong numbers the demo switch put into drafts on purpose. Each one is also counted as caught.",
};
