import type { Lang, Mode } from "./types";

// Words the graphics draw themselves. The stories come translated from the Persona agent.
const WORDS = {
  goal: { en: "Goal", es: "Gol" },
  big_chance: { en: "Big chance", es: "Ocasión clara" },
  shot_speed: { en: "Rocket", es: "Cañonazo" },
  killer_pass: { en: "Killer pass", es: "Pase letal" },
  momentum_swing: { en: "Momentum", es: "Dominio" },
  sprint_speed: { en: "Top speed", es: "Velocidad punta" },
  distance_10k: { en: "10 km club", es: "Club de los 10 km" },
  half_time: { en: "Half time", es: "Descanso" },
  full_time: { en: "Full time", es: "Final" },
  xg: { en: "xG", es: "xG" },
  distance: { en: "Distance", es: "Distancia" },
  shot_speed_label: { en: "Shot speed", es: "Velocidad" },
  difficulty: { en: "Difficulty", es: "Dificultad" },
  gap: { en: "Gap", es: "Hueco" },
  the_gap: { en: "the gap", es: "el hueco" },
  shots: { en: "Shots", es: "Tiros" },
  possession: { en: "Possession", es: "Posesión" },
  goals: { en: "Goals", es: "Goles" },
  top_rated: { en: "Top rated", es: "Mejor valorados" },
  final_third: { en: "Final-third passes, last 5 min", es: "Pases en el último tercio, últimos 5 min" },
  fact_checked: { en: "Fact-checked", es: "Verificado" },
  stat_card: { en: "Plain stats: the story failed fact-checking", es: "Solo datos: la historia no pasó la verificación" },
  replay: { en: "Replay", es: "Repetición" },
  stat: { en: "Stat", es: "Dato" },
  easy: { en: "easy", es: "fácil" },
  medium: { en: "medium", es: "media" },
  hard: { en: "hard", es: "difícil" },
  very_hard: { en: "very hard", es: "muy difícil" },
} as const;

export type Word = keyof typeof WORDS;

export function tr(lang: Lang, word: Word | string): string {
  const entry = (WORDS as Record<string, Record<Lang, string>>)[word];
  return entry ? entry[lang] : word;
}

export const MODES: { id: Mode; label: Record<Lang, string> }[] = [
  { id: "analyst", label: { en: "Analyst", es: "Analista" } },
  { id: "casual", label: { en: "Casual fan", es: "Aficionado" } },
  { id: "player", label: { en: "Player focus", es: "Jugador" } },
];

export const LANGS: { id: Lang; label: string }[] = [
  { id: "en", label: "English" },
  { id: "es", label: "Español" },
];
