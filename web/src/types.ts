export type Side = "HOME" | "AWAY";
export type XY = [number, number];

export interface Player {
  id: string;
  name: string;
  number: number;
  position: string;
}

export interface Team {
  side: Side;
  key: string;
  name: string;
  short: string;
  colors: [string, string];
  style: string;
  formation: string;
  players: Player[];
}

export interface Meta {
  match_id: string;
  seed: number;
  speed: number;
  pitch: [number, number];
  teams: Record<Side, Team>;
  model?: string; // "mock" or the Foundry deployment the agents run on
  languages?: Lang[];
  planted_slips?: boolean; // the demo switch: wrong numbers planted for the Fact-checker to catch
}

export interface Frame {
  t: number;
  period: number;
  b: XY;
  p: XY[]; // home slots 0-10 then away slots 0-10
  o: string | null;
}

export interface MatchEvent {
  id: string;
  t: number;
  period: number;
  clock: string;
  type: string;
  team?: Side;
  player?: string | null;
  [key: string]: unknown;
}

export interface Trigger {
  id: string;
  t: number;
  clock: string;
  kind: string;
  priority: number;
  team: Side | null;
  player: string | null;
  value: number;
  label: string;
  source_events: string[];
}

export interface TeamStats {
  name: string;
  short: string;
  goals: number;
  xg: number;
  shots: number;
  shots_on_target: number;
  passes: number;
  pass_completion_pct: number | null;
  possession_pct: number;
  corners: number;
  fouls: number;
  field_tilt_pct: number;
  ppda: number | null;
  counter_presses: number;
  counter_press_wins: number;
  counter_press_win_pct: number | null;
  final_third_entries: Record<Lane, number>; // passes and carries into the final third, by the lane they arrive in
  distance_km: number;
}

export type Lane = "left_wing" | "left_half_space" | "centre" | "right_half_space" | "right_wing";
export const LANES: Lane[] = ["left_wing", "left_half_space", "centre", "right_half_space", "right_wing"];

/** A pass received in a half-space in the final third, which the pitch lights up. */
export interface HalfSpaceBall {
  id: string; // the pass
  team: Side;
  t: number; // match time the ball arrived
  lane: "left_half_space" | "right_half_space";
  to: XY;
}

/** A team that lost the ball in the opponent's half and went after it: won back within 8 s, or escaped. */
export interface Press {
  id: string;
  team: Side; // the team pressing
  t: number; // match time it was decided
  lost_t: number;
  clock: string;
  period: number;
  outcome: "open" | "won" | "escaped"; // open: just lost, the 8 s are running; then a record if it was a press
  seconds: number; // from losing the ball to winning it back (or to the end of the 8 s)
  at: XY; // where the ball was then
  pressers: number;
  player: string | null; // who won it back
}

export interface Snapshot {
  t: number;
  clock: string;
  period: number;
  finished: boolean;
  score: Record<Side, number>;
  possession: Side | null;
  control_chaos: number;
  momentum: number;
  teams: Record<Side, TeamStats>;
}

/** Momentum at the start of each minute of play: -100 (away on top) to +100 (home on top). */
export interface MomentumPoint {
  minute: number; // whole minutes of match time played, stoppage time included
  momentum: number;
}

export interface Club {
  key: string;
  name: string;
  short: string;
  colors: [string, string];
  style: string;
  formation: string;
}

export type Mode = "analyst" | "casual" | "player";
export type Lang = "en" | "es";

export interface TelestratorArrow {
  kind: "pass" | "carry" | "shot";
  from: XY;
  to: XY;
  t: number; // match seconds, so a replay can draw each arrow as the play reaches it
}

export interface TelestratorZone {
  kind: "circle";
  center: XY;
  r: number;
  label?: string;
}

export interface Telestrator {
  arrows: TelestratorArrow[];
  zones: TelestratorZone[];
  highlight: string[];
  window: [number, number]; // match seconds the replay covers
}

export interface PluginInfo {
  builtin: false;
  name: string;
  author: string;
  entry: string; // URL of the plugin's page
  height_px: number;
}

export interface Overlay {
  id: string;
  moment_id: string;
  kind: string;
  clock: string;
  show_at: number;
  duration_s: number;
  priority: number;
  plugin: string;
  slot: string;
  team: Side | null;
  player: string | null;
  headline: string;
  data: Record<string, unknown>;
  telestrator: Telestrator | null;
  facts_checked: boolean;
  fallback: boolean;
  fallback_reason?: "fact_check" | "no_answer"; // why a plain stat card went out instead of a story
  plugin_info?: PluginInfo; // set for outside plugins, which run sandboxed
  story: string;
  text: Record<string, Record<Mode, string>>;
}

export interface TraceStep {
  id: string;
  t: number;
  clock: string;
  moment_id: string;
  agent: string;
  action: string;
  summary: string;
  status: "ok" | "rejected" | "retry" | "fallback" | "skipped" | "planted";
  ms: number;
  detail: Record<string, unknown>;
}
