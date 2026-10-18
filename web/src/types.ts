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
  distance_km: number;
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

export interface Club {
  key: string;
  name: string;
  short: string;
  colors: [string, string];
  style: string;
  formation: string;
}
