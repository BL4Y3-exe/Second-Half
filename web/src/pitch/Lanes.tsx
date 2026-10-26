import { tr } from "../i18n";
import type { Frame, HalfSpaceBall, Lang, Meta } from "../types";

const L = 105;
// The lane lines run along the sides of the penalty area and of the six-yard box (stats/lanes.py).
const EDGES = [13.84, 24.84, 43.16, 54.16];
const FINAL_THIRD = 35; // metres in from the goal line being attacked
const SHOW_S = 1.6; // wall seconds a half-space stays lit, whatever the match speed

/**
 * The half-space ball to light up at match time t: the newest one that arrived in the last second or two, until the
 * other team first touches the ball (then it stays off, so a contested ball doesn't make it flicker).
 */
export function halfSpaceNow(balls: HalfSpaceBall[], t: number, speed: number, history: Frame[]): HalfSpaceBall | null {
  const ball = balls.filter((b) => t >= b.t && t - b.t < SHOW_S * speed).at(-1) ?? null;
  if (!ball) return null;
  for (let i = history.length - 1; i >= 0 && history[i].t >= ball.t; i--) {
    const o = history[i].o;
    if (history[i].t <= t && o && (o.startsWith("h-") ? "HOME" : "AWAY") !== ball.team) return null;
  }
  return ball;
}

/** The four lines that split the pitch into wings, half-spaces and the centre. */
export function LaneLines() {
  return (
    <g className="lane-lines" aria-hidden="true">
      {EDGES.map((y) => (
        <line key={y} x1={0} y1={y} x2={L} y2={y} />
      ))}
    </g>
  );
}

/** Lights the half-space where a team just got the ball in the final third, with its name. */
export function HalfSpace({ ball, meta, lang }: { ball: HalfSpaceBall; meta: Meta; lang: Lang }) {
  const right = ball.to[0] > L / 2; // attacking the goal at x = 105
  const y0 = ball.to[1] < 34 ? EDGES[0] : EDGES[2];
  const y1 = ball.to[1] < 34 ? EDGES[1] : EDGES[3];
  const x0 = right ? L - FINAL_THIRD : 0;
  const text = `${tr(lang, ball.lane)} · ${meta.teams[ball.team].short}`;
  const w = text.length * 0.74 + 2.2;
  // The name sits at the end of the strip nearest halfway, out of the way of the box.
  const x = right ? x0 + w / 2 + 1 : FINAL_THIRD - w / 2 - 1;
  return (
    <g className="half-space" aria-hidden="true">
      <rect x={x0} y={y0} width={FINAL_THIRD} height={y1 - y0} style={{ fill: meta.teams[ball.team].colors[0] }} />
      <line x1={x0} y1={y0} x2={x0 + FINAL_THIRD} y2={y0} />
      <line x1={x0} y1={y1} x2={x0 + FINAL_THIRD} y2={y1} />
      <g className="half-space-tag" transform={`translate(${x} ${(y0 + y1) / 2})`}>
        <rect x={-w / 2} y={-1.25} width={w} height={2.5} rx={1.25} />
        <text y={0.5}>{text}</text>
      </g>
    </g>
  );
}
