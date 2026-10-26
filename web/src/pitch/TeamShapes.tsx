import { useRef } from "react";
import { tr } from "../i18n";
import type { Lang, Meta, Side, XY } from "../types";

const L = 105;
const W = 68;
const SUPPORT_RANGE = 24; // metres from the ball carrier a teammate can be and still be part of the shape
const SUPPORT_PLAYERS = 3;
const LANE_CUT = 1.8; // an opponent this close to a passing lane cuts it
const AT_THE_BALL = 15; // radius for counting numbers around the ball
const REFRESH_MS = 600; // pick the supporting players again this often, so the shape does not flicker
const COMPACT_M = 12; // gap between the back line and the next one, metres
const STRETCHED_M = 18;

interface Props {
  meta: Meta;
  players: XY[]; // home slots 0-10 then away slots 0-10
  ball: XY;
  owner: string | null;
  ids: string[]; // player id per slot, same order
  lang: Lang;
  support?: boolean; // draw the shape round the ball; off while a counter-press or a lit half-space has that space
}

const dist = (a: XY, b: XY) => Math.hypot(a[0] - b[0], a[1] - b[1]);
const team = (side: Side) => (side === "HOME" ? [0, 11] : [11, 22]);
const range = ([from, to]: number[]) => Array.from({ length: to - from }, (_, k) => from + k);
const pts = (xy: XY[]) => xy.map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join(" ");

/** How far from p the segment a-b passes, and how far along it (0 at a, 1 at b) the nearest point is. */
function toSegment(p: XY, a: XY, b: XY): [number, number] {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const u = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy || 1);
  return [Math.hypot(p[0] - (a[0] + u * dx), p[1] - (a[1] + u * dy)), u];
}

/** The outline round some points, as indices into them, anticlockwise. */
function hull(points: XY[]): number[] {
  const order = points.map((_, i) => i).sort((i, j) => points[i][0] - points[j][0] || points[i][1] - points[j][1]);
  const cross = (o: number, a: number, b: number) =>
    (points[a][0] - points[o][0]) * (points[b][1] - points[o][1]) -
    (points[a][1] - points[o][1]) * (points[b][0] - points[o][0]);
  const half = (seq: number[]) => {
    const out: number[] = [];
    for (const i of seq) {
      while (out.length >= 2 && cross(out[out.length - 2], out[out.length - 1], i) <= 0) out.pop();
      out.push(i);
    }
    out.pop();
    return out;
  };
  return [...half(order), ...half([...order].reverse())];
}

/** A formation's lines from the back, "4-2-3-1" as [4, 2, 3, 1]. */
function lineSizes(formation: string): number[] {
  const sizes = formation.split("-").map(Number);
  return sizes.reduce((s, n) => s + n, 0) === 10 && sizes.every((n) => n > 0) ? sizes : [4, 3, 3];
}

/**
 * What an analyst draws over the picture. For the side on the ball: the shape the carrier and the nearest
 * teammates make (a triangle, a diamond or a box), which passing lanes in it are open and which an opponent has
 * cut, and the numbers around the ball. For the side without it: its back line and the line in front of it, and
 * how far apart they are, which is the space an attacker can receive in between the lines.
 */
export function TeamShapes({ meta, players, ball, owner, ids, lang, support: showSupport = true }: Props) {
  const memo = useRef<{ carrier: number; support: number[]; at: number } | null>(null);
  const now = performance.now();
  const onBall = owner ? ids.indexOf(owner) : -1;
  const stale = memo.current && (memo.current.carrier !== onBall || now - memo.current.at > REFRESH_MS);
  if (onBall >= 0 && (!memo.current || stale)) {
    // While the ball is in the air the last carrier's shape stays up; the receiver's takes over when it lands.
    const mates = range(team(onBall < 11 ? "HOME" : "AWAY")).filter((i) => i !== onBall);
    const support = mates
      .filter((i) => dist(players[i], players[onBall]) < SUPPORT_RANGE)
      .sort((i, j) => dist(players[i], players[onBall]) - dist(players[j], players[onBall]))
      .slice(0, SUPPORT_PLAYERS);
    memo.current = { carrier: onBall, support, at: now };
  }
  if (!memo.current) return null;
  const { carrier, support } = memo.current;
  const attack: Side = carrier < 11 ? "HOME" : "AWAY";
  const defend: Side = attack === "HOME" ? "AWAY" : "HOME";
  const opponents = range(team(defend));
  // Which way each side plays, from where its goalkeeper is.
  const ownGoalLeft = (side: Side) => players[team(side)[0]][0] < L / 2;

  // --- the side on the ball -------------------------------------------------------------------------------------
  const shape = [carrier, ...support];
  const outline = hull(shape.map((i) => players[i])).map((k) => shape[k]);
  let name = "";
  if (support.length >= 2) {
    name = tr(lang, "triangle");
    if (outline.length === 4) {
      // Four on the outline: one deep, two wide, one high is a diamond; two pairs level with each other, a box.
      const forward = ownGoalLeft(attack) ? 1 : -1;
      const u = outline.map((i) => players[i][0] * forward).sort((a, b) => a - b);
      name = tr(lang, u[2] - u[1] > u[1] - u[0] + (u[3] - u[2]) ? "box" : "diamond");
    }
  }
  const open = support.map(
    (j) =>
      !opponents.some((o) => {
        const [d, along] = toSegment(players[o], players[carrier], players[j]);
        return d < LANE_CUT && along > 0.1 && along < 0.95;
      }),
  );
  const openCount = open.filter(Boolean).length;
  const near = (side: Side) => range(team(side)).filter((i) => dist(players[i], ball) < AT_THE_BALL).length;
  const lanesText =
    lang === "es"
      ? `${openCount} ${openCount === 1 ? "línea de pase libre" : "líneas de pase libres"}`
      : `${openCount} open ${openCount === 1 ? "lane" : "lanes"}`;
  const numbersText = lang === "es" ? `${near(attack)}v${near(defend)} cerca del balón` : `${near(attack)}v${near(defend)} at the ball`;
  const shapeXY = shape.map((i) => players[i]);
  const top = Math.min(...shapeXY.map((p) => p[1]));
  const bottom = Math.max(...shapeXY.map((p) => p[1]));
  const labelX = Math.min(L - 9, Math.max(9, shapeXY.reduce((s, p) => s + p[0], 0) / shapeXY.length));
  const above = top > 6;
  const labelY = above ? top - 4.2 : bottom + 3.4;

  // --- the side without it -----------------------------------------------------------------------------------------
  const left = ownGoalLeft(defend);
  const depth = (p: XY) => (left ? p[0] : L - p[0]);
  const outfield = range(team(defend))
    .slice(1)
    .sort((i, j) => depth(players[i]) - depth(players[j]));
  const [backSize, nextSize] = lineSizes(meta.teams[defend].formation);
  const lines = [outfield.slice(0, backSize), outfield.slice(backSize, backSize + nextSize)];
  const meanDepth = (line: number[]) => line.reduce((s, i) => s + depth(players[i]), 0) / line.length;
  const back = meanDepth(lines[0]);
  const next = meanDepth(lines[1]);
  const gap = Math.round(next - back);
  const xBack = left ? back : L - back;
  const xNext = left ? next : L - next;
  const verdict = gap <= COMPACT_M ? tr(lang, "compact_block") : gap >= STRETCHED_M ? tr(lang, "stretched_block") : null;
  const gapText = lang === "es" ? `${gap} m entre líneas` : `${gap} m between the lines`;
  const blockText = [meta.teams[defend].short, verdict, gapText].filter(Boolean).join(" · ");

  return (
    <g className="shapes" aria-hidden="true">
      <g className="block">
        {lines
          .filter((line) => line.length >= 2)
          .map((line, k) => (
            <polyline
              key={k}
              className={k === 0 ? "back-line" : undefined}
              points={pts([...line].sort((i, j) => players[i][1] - players[j][1]).map((i) => players[i]))}
            />
          ))}
        <g className="gap" transform={`translate(0 ${W + 1.1})`}>
          <line x1={xBack} x2={xNext} y1={0} y2={0} />
          <line x1={xBack} x2={xBack} y1={-0.6} y2={0.6} />
          <line x1={xNext} x2={xNext} y1={-0.6} y2={0.6} />
          <text x={(xBack + xNext) / 2} y={1.75}>
            {blockText}
          </text>
        </g>
      </g>
      {name && showSupport && (
        <g className="support">
          <polygon points={pts(outline.map((i) => players[i]))} />
          {outline.map((i, k) => {
            const j = outline[(k + 1) % outline.length];
            return i === carrier || j === carrier ? null : (
              <line key={`${i}-${j}`} className="link" x1={players[i][0]} y1={players[i][1]} x2={players[j][0]} y2={players[j][1]} />
            );
          })}
          {support.map((j, k) => (
            <line
              key={j}
              className={open[k] ? "lane" : "lane cut"}
              x1={players[carrier][0]}
              y1={players[carrier][1]}
              x2={players[j][0]}
              y2={players[j][1]}
            />
          ))}
          <text x={labelX} y={labelY}>
            <tspan className="shape-name">
              {meta.teams[attack].short} {name}
            </tspan>
            <tspan x={labelX} dy={1.7}>
              {lanesText} · {numbersText}
            </tspan>
          </text>
        </g>
      )}
    </g>
  );
}
