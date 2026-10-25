import { NOTES, STAT_NOTES } from "../notes";
import type { Meta, Snapshot } from "../types";

interface RowProps {
  label: string;
  home: number;
  away: number;
  pct?: boolean;
  digits?: number;
}

function Row({ label, home, away, pct, digits = 0 }: RowProps) {
  const total = home + away;
  const share = total > 0 ? (home / total) * 100 : 50;
  const fmt = (v: number) => (pct ? `${Math.round(v)}%` : v.toFixed(digits));
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
      </div>
      <span className="v right">{fmt(away)}</span>
    </div>
  );
}

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
      <Row label="Corners" home={h.corners} away={a.corners} />
      <Row label="Distance (km)" home={h.distance_km} away={a.distance_km} digits={1} />
    </div>
  );
}
