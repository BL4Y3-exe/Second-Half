import { useEffect, useId, useRef, useState } from "react";
import { NOTES } from "../notes";
import type { Moment } from "../trace";
import type { Meta, MomentumPoint, Side } from "../types";

interface Props {
  meta: Meta;
  points: MomentumPoint[];
  now: number; // match seconds played
  finished: boolean;
  secondHalfAt: number | null; // match seconds when the second half kicked off, once it has
  moments: Moment[];
  selected: string | null;
  onSelect: (id: string) => void;
}

const H = 214;
const TOP = 26;
const CHART = 124;
const RAIL = TOP + CHART + 26;
const LEFT = 52; // room for the side labels
const PAD = 12;
const FULL_MATCH_S = 95 * 60;

function useWidth(ref: React.RefObject<HTMLElement | null>): number {
  const [width, setWidth] = useState(0);
  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, [ref]);
  return width;
}

/** A smooth path through the points (Catmull-Rom turned into cubic Béziers). */
function smooth(pts: [number, number][]): string {
  let d = `M ${pts[0][0].toFixed(1)} ${pts[0][1].toFixed(1)}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const [p0, p1, p2, p3] = [pts[Math.max(i - 1, 0)], pts[i], pts[i + 1], pts[Math.min(i + 2, pts.length - 1)]];
    const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
    const c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
    d += ` C ${c1[0].toFixed(1)} ${c1[1].toFixed(1)} ${c2[0].toFixed(1)} ${c2[1].toFixed(1)}`;
    d += ` ${p2[0].toFixed(1)} ${p2[1].toFixed(1)}`;
  }
  return d;
}

const kindOf = (m: Moment) => m.overlay?.kind ?? m.trigger?.kind ?? String(m.steps[0].detail.kind ?? "");

/**
 * Momentum through the whole match: above the line the home side is on top, below it the away side.
 * Every moment the Spotter saw sits on the rail underneath; pick one to see how the agents handled it.
 */
export function MomentumWave({ meta, points, now, finished, secondHalfAt, moments, selected, onSelect }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const width = useWidth(box);
  const id = useId();
  const [hover, setHover] = useState<number | null>(null); // match seconds under the pointer
  const end = Math.max(FULL_MATCH_S, now + 120);
  const x = (t: number) => LEFT + ((width - LEFT - PAD) * t) / end;
  const mid = TOP + CHART / 2;
  const y = (v: number) => mid - ((CHART / 2) * Math.max(-100, Math.min(100, v))) / 100;
  const s2 = secondHalfAt ?? 48 * 60;
  // Football minutes: 02:38 is the 3rd minute, and stoppage time reads 45+2'.
  const clockAt = (t: number) => {
    const [base, m] = t < s2 ? [0, Math.floor(t / 60) + 1] : [45, 45 + Math.floor((t - s2) / 60) + 1];
    return m > base + 45 ? `${base + 45}+${m - base - 45}'` : `${m}'`;
  };
  const colour = (side: Side | null | undefined) => (side ? meta.teams[side].colors[0] : "var(--muted)");

  const pts: [number, number][] = points
    .filter((p) => p.minute * 60 <= now)
    .map((p) => [x(p.minute * 60), y(p.momentum)]);
  if (pts.length) pts.push([x(now), pts[pts.length - 1][1]]);
  const line = pts.length > 1 ? smooth(pts) : "";
  const area = line ? `${line} L ${pts[pts.length - 1][0]} ${mid} L ${pts[0][0]} ${mid} Z` : "";

  const ticks: [string, number][] = [
    ["0'", 0],
    ["15'", 900],
    ["30'", 1800],
    [secondHalfAt === null ? "45'" : "HT", secondHalfAt ?? 2700],
    ["60'", s2 + 900],
    ["75'", s2 + 1800],
    ["90'", s2 + 2700],
  ];

  const near = hover === null ? null : points.reduce<MomentumPoint | null>((best, p) => {
    const d = Math.abs(p.minute * 60 - hover);
    return best === null || d < Math.abs(best.minute * 60 - hover) ? p : best;
  }, null);

  const shown = moments.filter((m) => kindOf(m) !== "recap");
  const goals = shown.filter((m) => kindOf(m) === "goal");
  let lastLabel = -Infinity;

  return (
    <div className="wave-box" ref={box}>
      {width > 0 && (
        <svg
          className="wave"
          width={width}
          height={H}
          viewBox={`0 0 ${width} ${H}`}
          role="img"
          aria-label="Momentum through the match, with every moment the Spotter flagged"
          onMouseMove={(e) => {
            const r = e.currentTarget.getBoundingClientRect();
            const t = ((e.clientX - r.left - LEFT) / (width - LEFT - PAD)) * end;
            setHover(t >= 0 && t <= now && e.clientY - r.top < TOP + CHART ? t : null);
          }}
          onMouseLeave={() => setHover(null)}
        >
          <defs>
            <clipPath id={`${id}-above`}>
              <rect x={0} y={0} width={width} height={mid} />
            </clipPath>
            <clipPath id={`${id}-below`}>
              <rect x={0} y={mid} width={width} height={H} />
            </clipPath>
          </defs>
          {ticks.map(([label, t]) => (
            <g key={label}>
              <line className={`grid${label === "HT" ? " ht" : ""}`} x1={x(t)} x2={x(t)} y1={TOP} y2={TOP + CHART} />
              <text className="tick" x={x(t)} y={H - 4}>
                {label}
              </text>
            </g>
          ))}
          <rect className="future" x={x(now)} y={TOP} width={Math.max(0, width - PAD - x(now))} height={CHART} />
          {area && (
            <>
              <path d={area} fill={colour("HOME")} className="area" clipPath={`url(#${id}-above)`} />
              <path d={area} fill={colour("AWAY")} className="area" clipPath={`url(#${id}-below)`} />
            </>
          )}
          <line className="midline" x1={LEFT} x2={width - PAD} y1={mid} y2={mid} />
          <text className="side-label" x={LEFT - 10} y={TOP + 16}>
            {meta.teams.HOME.short} ↑
          </text>
          <text className="side-label" x={LEFT - 10} y={TOP + CHART - 8}>
            {meta.teams.AWAY.short} ↓
          </text>
          {now > 0 && (
            <g className={`live-head${finished ? " done" : ""}`}>
              <line x1={x(now)} x2={x(now)} y1={TOP - 4} y2={TOP + CHART} />
              <g transform={`translate(${Math.min(x(now), width - 36)} ${TOP - 13})`}>
                <rect x={-36} y={-10} width={72} height={20} rx={10} />
                <text y={4}>{finished ? "FULL TIME" : `LIVE ${clockAt(now)}`}</text>
              </g>
            </g>
          )}
          {near && hover !== null && (
            <g className="crosshair">
              <line x1={x(near.minute * 60)} x2={x(near.minute * 60)} y1={TOP} y2={TOP + CHART} />
              <circle cx={x(near.minute * 60)} cy={y(near.momentum)} r={4} />
            </g>
          )}
          <line className="rail" x1={LEFT} x2={Math.max(LEFT, x(now))} y1={RAIL} y2={RAIL} />
          {[...shown.filter((m) => kindOf(m) !== "goal"), ...goals].map((m) => {
            const goal = kindOf(m) === "goal";
            const side = m.overlay?.team ?? m.trigger?.team ?? null;
            const aired = Boolean(m.overlay);
            const label = `${m.clock} ${m.overlay?.headline ?? m.label}`;
            const cx = x(m.t);
            let tag: string | null = null;
            if (goal && cx - lastLabel > 110) {
              const who = String(m.overlay?.data.player ?? m.label.split(": ").pop() ?? "");
              tag = `${clockAt(m.t)} ${who.split(" ").pop()}`;
              lastLabel = cx;
            }
            return (
              <g
                key={m.id}
                className={`mark${goal ? " goal" : ""}${aired ? "" : " passed"}${selected === m.id ? " on" : ""}`}
                transform={`translate(${cx} ${RAIL})`}
                role="button"
                tabIndex={0}
                aria-label={label}
                aria-pressed={selected === m.id}
                onClick={() => onSelect(m.id)}
                onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), onSelect(m.id))}
              >
                <title>{label}</title>
                <circle r={12} className="hit" />
                {selected === m.id && <circle r={goal ? 15 : 9} className="ring" />}
                {goal ? (
                  <>
                    <circle r={10} fill={colour(side)} className="dot" />
                    <path d="M -4 -1.5 L 0 -4.5 L 4 -1.5 L 2.5 3.5 L -2.5 3.5 Z" className="ball" />
                  </>
                ) : (
                  <circle r={aired ? 5 : 3} fill={aired ? colour(side) : "var(--muted)"} className="dot" />
                )}
                {tag && (
                  <text className="goal-label" x={16} y={5}>
                    {tag}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      )}
      {near && hover !== null && (
        <div
          className="wave-tip"
          style={{ left: Math.min(width - 180, Math.max(0, x(near.minute * 60) - 90)) }}
          data-note={NOTES.momentum}
        >
          <b>{clockAt(near.minute * 60)}</b>{" "}
          {Math.abs(near.momentum) < 15
            ? "Even"
            : `${meta.teams[near.momentum > 0 ? "HOME" : "AWAY"].short} on top, ${Math.abs(Math.round(near.momentum))}`}
        </div>
      )}
    </div>
  );
}
