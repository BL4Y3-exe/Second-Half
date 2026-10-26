import type { Lang, Mode } from "./types";

// Words the graphics draw themselves. The stories come translated from the Persona agent.
const WORDS = {
  goal: { en: "Goal", es: "Gol" },
  big_chance: { en: "Big chance", es: "Ocasión clara" },
  shot_speed: { en: "Rocket", es: "Cañonazo" },
  killer_pass: { en: "Killer pass", es: "Pase letal" },
  counter_press: { en: "Counter-press", es: "Contrapresión" },
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
  shape_title: { en: "Team shape", es: "Forma del equipo" },
  with_ball: { en: "With the ball", es: "Con balón" },
  without_ball: { en: "Without the ball", es: "Sin balón" },
  attacking: { en: "Attacking", es: "Atacando" },
  back_line: { en: "back line", es: "línea defensiva" },
  see_analysis: { en: "See the match analysis", es: "Ver el análisis del partido" },
  opening_in: { en: "Opening in", es: "Se abre en" },
  final_third: { en: "Final-third passes, last 5 min", es: "Pases en el último tercio, últimos 5 min" },
  fact_checked: { en: "Fact-checked", es: "Verificado" },
  stat_card: { en: "Plain stats: the story failed fact-checking", es: "Solo datos: la historia no pasó la verificación" },
  stat_card_no_answer: { en: "Plain stats: no story in time", es: "Solo datos: sin historia a tiempo" },
  replay: { en: "Replay", es: "Repetición" },
  watching: { en: "Watching", es: "Viendo" },
  live: { en: "Live", es: "En directo" },
  ft: { en: "FT", es: "Final" },
  connecting: { en: "Connecting…", es: "Conectando…" },
  offline: { en: "Offline", es: "Sin conexión" },
  stat: { en: "Stat", es: "Dato" },
  easy: { en: "easy", es: "fácil" },
  medium: { en: "medium", es: "media" },
  hard: { en: "hard", es: "difícil" },
  very_hard: { en: "very hard", es: "muy difícil" },
  paused: { en: "Paused", es: "En pausa" },
  close: { en: "Close", es: "Cerrar" },
  triangle: { en: "Triangle", es: "Triángulo" },
  diamond: { en: "Diamond", es: "Rombo" },
  box: { en: "Box", es: "Cuadrado" },
  compact_block: { en: "Compact block", es: "Bloque compacto" },
  stretched_block: { en: "Stretched block", es: "Bloque largo" },
  won_back_in: { en: "Won back in", es: "Recuperada en" },
  left_half_space: { en: "Left half-space", es: "Carril interior izquierdo" },
  right_half_space: { en: "Right half-space", es: "Carril interior derecho" },
  played_through: { en: "Played through", es: "Superada" },
  won_back: { en: "won back", es: "recuperada" },
  to_win_it_back: { en: "to win it back", es: "para recuperarla" },
  to_the_shot: { en: "to the shot", es: "hasta el tiro" },
  press_wins: { en: "won back within 8 s", es: "recuperadas en 8 s" },
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
