import { useEffect, useRef, useState } from "react";
import type { FrameBuffer } from "../useLiveMatch";
import type { Meta, XY } from "../types";

const L = 105;
const W = 68;
const M = 3; // margin around the pitch, metres

interface Props {
  meta: Meta;
  frames: React.RefObject<FrameBuffer>;
  slots: { HOME: string[]; AWAY: string[] };
}

interface Drawn {
  players: XY[];
  ball: XY;
  owner: string | null;
}

const lerp = (a: XY, b: XY, f: number): XY => [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f];

/** 2D pitch. Reads frames from a ref and interpolates between them every animation frame. */
export function Pitch({ meta, frames, slots }: Props) {
  const [drawn, setDrawn] = useState<Drawn | null>(null);
  const [hover, setHover] = useState<number | null>(null);
  const raf = useRef(0);

  useEffect(() => {
    const loop = () => {
      const buf = frames.current;
      if (buf?.cur) {
        const { prev, cur } = buf;
        const f = prev ? Math.min(1, (performance.now() - buf.arrivedAt) / buf.interval) : 1;
        // Do not glide across a jump (half time line-up): snap instead.
        const jump = prev && prev.period !== cur.period;
        const players = cur.p.map((xy, i) => (prev && !jump ? lerp(prev.p[i], xy, f) : xy));
        const ball = prev && !jump ? lerp(prev.b, cur.b, f) : cur.b;
        setDrawn({ players, ball, owner: cur.o });
      }
      raf.current = requestAnimationFrame(loop);
    };
    raf.current = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf.current);
  }, [frames]);

  const byId = new Map(
    (["HOME", "AWAY"] as const).flatMap((s) => meta.teams[s].players.map((p) => [p.id, p] as const)),
  );
  const ids = [...slots.HOME, ...slots.AWAY];

  return (
    <svg className="pitch" viewBox={`${-M} ${-M} ${L + 2 * M} ${W + 2 * M}`} role="img" aria-label="Live pitch">
      <defs>
        <pattern id="stripes" width="10.5" height={W} patternUnits="userSpaceOnUse">
          <rect width="5.25" height={W} fill="var(--grass-a)" />
          <rect x="5.25" width="5.25" height={W} fill="var(--grass-b)" />
        </pattern>
      </defs>
      <rect x={-M} y={-M} width={L + 2 * M} height={W + 2 * M} fill="var(--grass-b)" />
      <rect x={0} y={0} width={L} height={W} fill="url(#stripes)" />
      <g className="lines">
        <rect x={0} y={0} width={L} height={W} />
        <line x1={L / 2} y1={0} x2={L / 2} y2={W} />
        <circle cx={L / 2} cy={W / 2} r={9.15} />
        <circle cx={L / 2} cy={W / 2} r={0.4} className="spot" />
        {[0, 1].map((end) => {
          const x = end === 0 ? 0 : L;
          const dir = end === 0 ? 1 : -1;
          return (
            <g key={end}>
              <rect x={end === 0 ? 0 : L - 16.5} y={W / 2 - 20.16} width={16.5} height={40.32} />
              <rect x={end === 0 ? 0 : L - 5.5} y={W / 2 - 9.16} width={5.5} height={18.32} />
              <circle cx={x + dir * 11} cy={W / 2} r={0.4} className="spot" />
              <path
                d={`M ${x + dir * 16.5} ${W / 2 - 7.3} A 9.15 9.15 0 0 ${end === 0 ? 1 : 0} ${x + dir * 16.5} ${W / 2 + 7.3}`}
              />
              <rect x={end === 0 ? -2 : L} y={W / 2 - 3.66} width={2} height={7.32} className="goal" />
            </g>
          );
        })}
      </g>

      {drawn &&
        drawn.players.map(([x, y], i) => {
          const side = i < 11 ? "HOME" : "AWAY";
          const team = meta.teams[side];
          const id = ids[i];
          const player = byId.get(id);
          const keeper = i % 11 === 0;
          const fill = keeper ? (side === "HOME" ? "#f5c518" : "#9be15d") : team.colors[0];
          const text = keeper ? "#111" : team.colors[1];
          const onBall = drawn.owner === id;
          return (
            <g
              key={i}
              transform={`translate(${x} ${y})`}
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
              className="player"
            >
              {onBall && <circle r={2.1} className="on-ball" />}
              <circle r={1.35} fill={fill} stroke={text} strokeWidth={0.18} />
              <text y={0.5} fill={text} className="shirt">
                {player?.number ?? ""}
              </text>
              {hover === i && player && (
                <g className="tag" transform="translate(0 -2.6)">
                  <rect x={-player.name.length * 0.48 - 0.8} y={-1.6} width={player.name.length * 0.96 + 1.6} height={2.2} rx={0.4} />
                  <text y={0}>{player.name}</text>
                </g>
              )}
            </g>
          );
        })}
      {drawn && (
        <g transform={`translate(${drawn.ball[0]} ${drawn.ball[1]})`}>
          <circle r={0.75} className="ball" />
        </g>
      )}
    </svg>
  );
}
