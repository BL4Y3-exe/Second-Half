import type { XY } from "../types";
import { PitchBase } from "./Pitch";

const L = 105;
const W = 68;
const M = 3;

interface Props {
  positions: XY[]; // average positions by slot, goalkeeper first, attacking left to right
  color: string;
  keeper: string;
  label: string;
}

/** A team's average shape on a still pitch. The dots glide to their new places when the shape changes. */
export function ShapePitch({ positions, color, keeper, label }: Props) {
  return (
    <svg className="pitch shape-pitch" viewBox={`${-M} ${-M} ${L + 2 * M} ${W + 2 * M}`} role="img" aria-label={label}>
      <PitchBase />
      {positions.map(([x, y], i) => (
        <circle
          key={i}
          className="shape-dot"
          r={1.7}
          fill={i === 0 ? keeper : color}
          style={{ transform: `translate(${x}px, ${y}px)` }}
        />
      ))}
    </svg>
  );
}
