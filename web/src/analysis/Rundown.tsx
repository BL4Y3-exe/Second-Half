import { NOTES, TOTAL_NOTES } from "../notes";
import { outcome, totals, type Moment } from "../trace";
import type { Meta, TraceStep } from "../types";

interface Props {
  meta: Meta;
  moments: Moment[];
  trace: TraceStep[];
  selected: string | null;
  onSelect: (id: string) => void;
}

/** Every moment the Spotter saw, newest first, with what became of it. */
export function Rundown({ meta, moments, trace, selected, onSelect }: Props) {
  return (
    <section className="panel rundown" aria-label="Every moment so far">
      <h2>
        Rundown
        <span className="model" data-note={NOTES.model}>
          model: {meta.model ?? "mock"}
        </span>
      </h2>
      <div className="trace-totals">
        {totals(trace, moments).map(([label, n, cls]) => (
          <span key={label} className={cls} data-note={TOTAL_NOTES[label]}>
            <b>{n}</b> {label}
          </span>
        ))}
      </div>
      {moments.length === 0 && <p className="muted">The Spotter hasn't flagged anything yet.</p>}
      <ol className="rd-list">
        {[...moments].reverse().map((m) => {
          const o = outcome(m);
          const team = m.overlay?.team ?? m.trigger?.team;
          return (
            <li key={m.id}>
              <button
                type="button"
                className={`rd-row${selected === m.id ? " on" : ""}`}
                aria-pressed={selected === m.id}
                onClick={() => onSelect(m.id)}
              >
                <span className="side" style={{ background: team ? meta.teams[team].colors[0] : "transparent" }} />
                <span className="t">{m.clock}</span>
                <span className="label">{m.overlay?.headline ?? m.label}</span>
                <span className={`badge ${o.cls}`}>{o.text}</span>
              </button>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
