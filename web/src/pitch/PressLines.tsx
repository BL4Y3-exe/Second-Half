import { tr } from "../i18n";
import type { Lang, Meta, Press, Side, XY } from "../types";

const L = 105;
const WINDOW_S = 8; // Rangnick's rule: win it back within 8 seconds
const CHASE_M = 10; // a player this close to the ball while the 8 seconds run is chasing it
const FADE_M = 3; // lines fade in over the last few metres, so they never pop on and off
const SHOW_S = 2.2; // wall seconds the tag stays up, whatever the match speed

export interface PressNow {
  chase: Press | null; // the window the playback is in
  chasers: number[]; // slots of the players going after the ball
  side: Side | null;
  tag: Press | null; // a counter-press just decided: won back, or played through
}

const NONE: PressNow = { chase: null, chasers: [], side: null, tag: null };

/**
 * What the counter-press layer shows at match time t. While a team that has just lost the ball in the opponent's
 * half goes after it (8 seconds at most, and only while the other team has it), lines run from each of its players
 * near the ball to the ball. When it is decided, a tag says how fast the ball came back, or that the press was
 * played through.
 */
export function pressNow(
  presses: Press[],
  t: number,
  speed: number,
  players: XY[],
  ids: string[],
  ball: XY,
  owner: string | null,
): PressNow {
  const chase = presses.filter((p) => t >= p.lost_t && t < (p.outcome === "open" ? p.lost_t + WINDOW_S : p.t)).at(-1) ?? null;
  let tag = presses.filter((p) => p.outcome !== "open" && t >= p.t && t - p.t < SHOW_S * speed).at(-1) ?? null;
  if (tag && chase && chase.lost_t > tag.t) tag = null; // a new counter-press has started: the last tag is old news
  if (!chase && !tag) return NONE;
  let chasers: number[] = [];
  const holder = owner ? ids.indexOf(owner) : -1;
  if (chase && !(holder >= 0 && (holder < 11 ? "HOME" : "AWAY") === chase.team)) {
    const first = chase.team === "HOME" ? 0 : 11;
    chasers = Array.from({ length: 10 }, (_, k) => first + 1 + k).filter(
      (i) => Math.hypot(players[i][0] - ball[0], players[i][1] - ball[1]) < CHASE_M,
    );
  }
  return { chase: chasers.length ? chase : null, chasers, side: chase?.team ?? null, tag };
}

interface Props {
  now: PressNow;
  meta: Meta;
  lang: Lang;
  players: XY[];
  ids: string[];
  ball: XY;
  owner: string | null;
}

/** Draws the counter-press: the chasers' lines to the ball, then a small tag over whoever won it (or got away). */
export function PressLines({ now, meta, lang, players, ids, ball, owner }: Props) {
  const { chase, chasers, tag } = now;
  const lines = chase
    ? chasers.map((i) => {
        const p = players[i];
        const d = Math.hypot(ball[0] - p[0], ball[1] - p[1]);
        if (d < 3) return null; // already on the ball: no room for a line
        const ux = (ball[0] - p[0]) / d;
        const uy = (ball[1] - p[1]) / d;
        // From the edge of the player's dot to just short of the ball, in a white halo so it shows on the grass;
        // fading in as they close to within 10 m.
        const ends = { x1: p[0] + ux * 1.5, y1: p[1] + uy * 1.5, x2: ball[0] - ux * 1.0, y2: ball[1] - uy * 1.0 };
        return (
          <g key={i} style={{ opacity: Math.min(1, (CHASE_M - d) / FADE_M) }}>
            <line className="halo" {...ends} />
            <line {...ends} />
          </g>
        );
      })
    : null;
  let label = null;
  if (tag) {
    const won = tag.outcome === "won";
    const who = won ? tag.player : owner;
    const slot = who ? ids.indexOf(who) : -1;
    const at = slot >= 0 ? players[slot] : ball;
    const seconds = tag.seconds.toFixed(1).replace(".", lang === "es" ? "," : ".");
    const text = won ? `${tr(lang, "won_back_in")} ${seconds} s` : tr(lang, "played_through");
    const w = text.length * 0.78 + 2.2;
    const below = at[1] < 6; // no room above a player on the far touchline
    const x = Math.min(L - w / 2, Math.max(w / 2, at[0]));
    const y = below ? at[1] + 3.4 : at[1] - 3.4;
    label = (
      <g className={`press-tag ${tag.outcome}`} transform={`translate(${x} ${y})`}>
        <rect x={-w / 2} y={-1.25} width={w} height={2.5} rx={1.25} />
        <circle cx={-w / 2 + 1.25} cy={0} r={0.45} fill={won ? meta.teams[tag.team].colors[0] : "#8a94a3"} />
        <text x={0.45} y={0.52}>
          {text}
        </text>
      </g>
    );
  }
  if (!lines && !label) return null;
  return (
    <g className="presses" aria-hidden="true">
      {lines && (
        <g className="chase" style={{ stroke: meta.teams[now.side ?? "HOME"].colors[0] }}>
          {lines}
        </g>
      )}
      {label}
    </g>
  );
}
