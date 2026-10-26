import { NOTES, STAT_NOTES } from "../notes";
import { LANES } from "../types";
import type { Lane, Meta, Side, Snapshot } from "../types";

const LANE_NAMES: Record<Lane, string> = {
  left_wing: "Left wing",
  left_half_space: "Left half",
  centre: "Centre",
  right_half_space: "Right half",
  right_wing: "Right wing",
};

/** Where each team gets the ball into the final third, lane by lane from its own left to its right. */
function LaneSplit({ meta, snapshot }: { meta: Meta; snapshot: Snapshot }) {
  return (
    <div className="lanes">
      <span className="label" data-note={STAT_NOTES["Attacks by lane"]}>
        Attacks by lane
      </span>
      <div className="lanes-grid">
        <span />
        {LANES.map((lane) => (
          <span key={lane} className={`lane-name${lane.includes("half") ? " half" : ""}`}>
            {LANE_NAMES[lane]}
          </span>
        ))}
        {(["HOME", "AWAY"] as Side[]).map((side) => {
          const entries = snapshot.teams[side].final_third_entries;
          const total = entries ? LANES.reduce((n, lane) => n + entries[lane], 0) : 0;
          return [
            <span key={side} className="lane-team">
              {meta.teams[side].short}
            </span>,
            ...LANES.map((lane) => {
              const share = total ? (100 * entries[lane]) / total : 0;
              return (
                <span key={`${side}-${lane}`} className="lane-cell" title={`${entries?.[lane] ?? 0} of ${total}`}>
                  <b>{total ? `${Math.round(share)}%` : "–"}</b>
                  <span className="track">
                    <i style={{ width: `${share}%`, background: `var(--${side.toLowerCase()})` }} />
                  </span>
                </span>
              );
            }),
          ];
        })}
      </div>
    </div>
  );
}

interface RowProps {
  label: string;
  home: number | null; // null: nothing to show yet
  away: number | null;
  pct?: boolean;
  digits?: number;
  lower?: boolean; // the lower number gets the bigger share of the bar
  words?: [string, string]; // a word under the bar for each side
}

function Row({ label, home, away, pct, digits = 0, lower, words }: RowProps) {
  const invert = (v: number | null) => (v === null ? null : 1 / Math.max(v, 0.1));
  const [h, a] = lower ? [invert(home), invert(away)] : [home, away];
  const total = (h ?? 0) + (a ?? 0);
  const share = total > 0 ? ((h ?? 0) / total) * 100 : 50;
  const fmt = (v: number | null) => (v === null ? "–" : pct ? `${Math.round(v)}%` : v.toFixed(digits));
  return (
    <div className="stat-row">
      <span className="v">{fmt(home)}</span>
      <div className="mid">
        <span className="label" data-note={STAT_NOTES[label]}>
          {label}
        </span>
        <div className="split">
          <div className="home" style={{ width: `${share}%` }} />
          <div className="away" style={{ width: `${100 - share}%` }} />
        </div>
        {words && (
          <div className="words">
            <span>{words[0]}</span>
            <span>{words[1]}</span>
          </div>
        )}
      </div>
      <span className="v right">{fmt(away)}</span>
    </div>
  );
}

/** What a PPDA says about a team: at 10 passes per defensive action or under it presses high, over 15 it sits deep. */
const pressing = (ppda: number | null) =>
  ppda === null ? "" : ppda <= 10 ? "High press" : ppda <= 15 ? "Mid block" : "Sits deep";

export function StatsPanel({ meta, snapshot }: { meta: Meta; snapshot: Snapshot | null }) {
  if (!snapshot) return <div className="panel stats muted">Waiting for kickoff…</div>;
  const h = snapshot.teams.HOME;
  const a = snapshot.teams.AWAY;
  const m = snapshot.momentum; // -100 (away) .. +100 (home)
  const cc = snapshot.control_chaos;
  const ccLabel = cc >= 65 ? "Controlled" : cc >= 45 ? "Balanced" : cc >= 30 ? "Scrappy" : "Chaos";
  return (
    <div
      className="panel stats"
      style={
        {
          "--home": meta.teams.HOME.colors[0],
          "--away": meta.teams.AWAY.colors[0],
        } as React.CSSProperties
      }
    >
      <h2 className="stats-title">Team numbers</h2>
      <div className="gauges">
        <div className="gauge">
          <div className="gauge-label" data-note={NOTES.momentum}>
            Momentum
            <span>{m > 35 ? meta.teams.HOME.short : m < -35 ? meta.teams.AWAY.short : "Even"}</span>
          </div>
          <div className="momentum">
            <div className="centre" />
            <div
              className={`fill ${m >= 0 ? "home" : "away"}`}
              style={m >= 0 ? { left: "50%", width: `${m / 2}%` } : { right: "50%", width: `${-m / 2}%` }}
            />
          </div>
        </div>
        <div className="gauge">
          <div className="gauge-label" data-note={NOTES.controlChaos}>
            Control vs chaos
            <span>{ccLabel}</span>
          </div>
          <div className="cc">
            <div className="needle" style={{ left: `${cc}%` }} />
          </div>
        </div>
      </div>
      <Row label="xG" home={h.xg} away={a.xg} digits={2} />
      <Row label="Shots" home={h.shots} away={a.shots} />
      <Row label="On target" home={h.shots_on_target} away={a.shots_on_target} />
      <Row label="Possession" home={h.possession_pct} away={a.possession_pct} pct />
      <Row label="Pass accuracy" home={h.pass_completion_pct ?? 0} away={a.pass_completion_pct ?? 0} pct />
      <Row label="Field tilt" home={h.field_tilt_pct} away={a.field_tilt_pct} pct />
      <Row label="Counter-press wins" home={h.counter_press_wins ?? 0} away={a.counter_press_wins ?? 0} />
      <Row
        label="Pressing (PPDA)"
        home={h.ppda ?? null}
        away={a.ppda ?? null}
        digits={1}
        lower
        words={[pressing(h.ppda ?? null), pressing(a.ppda ?? null)]}
      />
      <Row label="Corners" home={h.corners} away={a.corners} />
      <Row label="Distance (km)" home={h.distance_km} away={a.distance_km} digits={1} />
      <LaneSplit meta={meta} snapshot={snapshot} />
    </div>
  );
}
