import type { Telestrator as Drawing, XY } from "../types";

/** Arrow heads, one per arrow kind. Rendered once inside the pitch's <defs>. */
export function TelestratorDefs() {
  return (
    <>
      {(["pass", "carry", "shot"] as const).map((kind) => (
        <marker
          key={kind}
          id={`tele-head-${kind}`}
          viewBox="0 0 10 10"
          refX="7"
          refY="5"
          markerWidth="4"
          markerHeight="4"
          orient="auto-start-reverse"
        >
          <path d="M 0 0 L 10 5 L 0 10 z" className={`tele-head ${kind}`} />
        </marker>
      ))}
    </>
  );
}

interface Props {
  drawing: Drawing;
  at: number | null; // replay clock in match seconds; null draws everything at once
  positions: Map<string, XY>; // where the highlighted players are on screen right now
}

/**
 * The Telestrator: the arrows and zones the Director built from real event geometry. During a
 * replay each arrow appears as the play reaches it, and the zones once the move is complete.
 */
export function Telestrator({ drawing, at, positions }: Props) {
  const reached = (t: number) => at === null || at >= t - 0.05;
  const last = drawing.arrows.length ? Math.max(...drawing.arrows.map((a) => a.t)) : drawing.window[0];
  return (
    <g className="telestrator">
      {drawing.highlight.map((id) => {
        const xy = positions.get(id);
        return xy ? <circle key={id} cx={xy[0]} cy={xy[1]} r={2.4} className="tele-ring" /> : null;
      })}
      {drawing.arrows.map((a, i) =>
        reached(a.t) ? (
          <g key={i} className={`tele-arrow ${a.kind}`}>
            <line
              x1={a.from[0]}
              y1={a.from[1]}
              x2={a.to[0]}
              y2={a.to[1]}
              pathLength={1}
              markerEnd={`url(#tele-head-${a.kind})`}
            />
          </g>
        ) : null,
      )}
      {reached(last) &&
        drawing.zones.map((z, i) => (
          <g key={i} className="tele-zone">
            <circle cx={z.center[0]} cy={z.center[1]} r={z.r} />
            {z.label && (
              <text x={z.center[0]} y={z.center[1] - z.r - 1}>
                {z.label}
              </text>
            )}
          </g>
        ))}
    </g>
  );
}
