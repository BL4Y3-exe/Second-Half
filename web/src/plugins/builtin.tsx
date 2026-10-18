import { tr } from "../i18n";
import type { Lang, Meta, Overlay, Side } from "../types";

/** What every graphics plugin is handed: the Director's item and the viewer's text for it. */
export interface PluginProps {
  overlay: Overlay;
  text: string;
  meta: Meta;
  lang: Lang;
}

const num = (v: unknown, digits = 0) => (typeof v === "number" ? v.toFixed(digits) : "–");
const str = (v: unknown) => (typeof v === "string" ? v : "");

function Chips({ items }: { items: [string, string][] }) {
  return (
    <div className="lt-chips">
      {items.map(([label, value]) => (
        <span key={label} className="chip">
          <b>{value}</b> {label}
        </span>
      ))}
    </div>
  );
}

export function GoalCard({ overlay, meta, lang }: PluginProps) {
  const d = overlay.data;
  const { HOME: home, AWAY: away } = meta.teams;
  return (
    <>
      <div className="lt-main">
        <span className="lt-name">{str(d.player)}</span>
        <span className="lt-score">
          {home.short} {num(d.score_home)}-{num(d.score_away)} {away.short}
        </span>
      </div>
      <Chips
        items={[
          [tr(lang, "xg"), num(d.xg, 2)],
          [tr(lang, "distance"), `${num(d.distance_m)} m`],
          [tr(lang, "shot_speed_label"), `${num(d.shot_speed_kmh)} km/h`],
        ]}
      />
    </>
  );
}

export function ShotCard({ overlay, lang }: PluginProps) {
  const d = overlay.data;
  const outcome = str(lang === "es" ? d.outcome_text_es : d.outcome_text) || str(d.outcome_text);
  return (
    <>
      <div className="lt-main">
        <span className="lt-name">{str(d.player)}</span>
        {outcome && <span className="lt-outcome">{outcome}</span>}
      </div>
      <Chips
        items={[
          [tr(lang, "xg"), num(d.xg, 2)],
          [tr(lang, "distance"), `${num(d.distance_m)} m`],
          [tr(lang, "shot_speed_label"), `${num(d.shot_speed_kmh)} km/h`],
        ]}
      />
    </>
  );
}

export function PassCard({ overlay, lang }: PluginProps) {
  const d = overlay.data;
  const label = tr(lang, str(d.difficulty_label).replace(" ", "_"));
  const chips: [string, string][] = [
    [tr(lang, "difficulty"), `${num(d.difficulty, 2)} · ${label}`],
    [tr(lang, "distance"), `${num(d.distance_m)} m`],
  ];
  if (typeof d.lane_gap_m === "number" && d.lane_gap_m >= 1) chips.push([tr(lang, "gap"), `${num(d.lane_gap_m, 1)} m`]);
  return (
    <>
      <div className="lt-main">
        <span className="lt-name">{str(d.passer)}</span>
        <span className="lt-arrow">→</span>
        <span className="lt-name">{str(d.receiver)}</span>
      </div>
      <Chips items={chips} />
    </>
  );
}

export function MomentumBar({ overlay, meta, lang }: PluginProps) {
  const d = overlay.data;
  const side = (overlay.team ?? "HOME") as Side;
  const other: Side = side === "HOME" ? "AWAY" : "HOME";
  const share = typeof d.tilt_recent === "number" ? d.tilt_recent : 50;
  return (
    <>
      <div className="lt-main">
        <span className="lt-name">{meta.teams[side].name}</span>
      </div>
      <div className="lt-tilt">
        <div className="lt-tilt-bar">
          <span style={{ width: `${share}%`, background: meta.teams[side].colors[0] }} />
          <span style={{ width: `${100 - share}%`, background: meta.teams[other].colors[0] }} />
        </div>
        <span className="lt-tilt-label">
          <b>{num(share)}%</b> {tr(lang, "final_third")}
        </span>
      </div>
    </>
  );
}

export function StatCard({ overlay }: PluginProps) {
  return <div className="lt-main lt-line">{str(overlay.data.line)}</div>;
}

/** Corner caption that goes with a player pinned on the pitch. */
export function PlayerTag({ overlay, text, lang }: PluginProps) {
  return (
    <div className="corner-card">
      <span className="lt-tag">{tr(lang, overlay.kind)}</span>
      <p>{text}</p>
    </div>
  );
}

/** The value a player-tag pins above the player on the pitch. */
export function pinValue(overlay: Overlay): string {
  const d = overlay.data;
  if (typeof d.top_speed_kmh === "number" && overlay.kind === "sprint_speed") return `${d.top_speed_kmh.toFixed(1)} km/h`;
  if (typeof d.distance_km === "number") return `${d.distance_km.toFixed(1)} km`;
  return "";
}

interface Rating {
  id: string;
  name: string;
  team: Side;
  rating: number;
}

interface Goal {
  minute: number;
  player: string;
  team: Side;
}

export function RecapCard({ overlay, text, meta, lang }: PluginProps) {
  const d = overlay.data;
  const { HOME: home, AWAY: away } = meta.teams;
  const rows: [string, string, string, number, number][] = [
    [tr(lang, "xg"), num(d.home_xg, 2), num(d.away_xg, 2), Number(d.home_xg) || 0, Number(d.away_xg) || 0],
    [tr(lang, "shots"), num(d.home_shots), num(d.away_shots), Number(d.home_shots) || 0, Number(d.away_shots) || 0],
    [tr(lang, "possession"), `${num(d.home_poss)}%`, `${num(d.away_poss)}%`, Number(d.home_poss) || 0, Number(d.away_poss) || 0],
  ];
  const ratings = (d.ratings as Rating[] | undefined) ?? [];
  const goals = (d.goals as Goal[] | undefined) ?? [];
  const title = overlay.headline.toLowerCase().includes("half") ? tr(lang, "half_time") : tr(lang, "full_time");
  return (
    <div className="recap">
      <div className="recap-title">{title}</div>
      <div className="recap-score">
        <span className="team">
          <i style={{ background: home.colors[0] }} />
          {home.name}
        </span>
        <span className="score">
          {num(d.score_home)}-{num(d.score_away)}
        </span>
        <span className="team right">
          {away.name}
          <i style={{ background: away.colors[0] }} />
        </span>
      </div>
      <div className="recap-goals">
        {(["HOME", "AWAY"] as Side[]).map((side) => (
          <div key={side} className={side === "AWAY" ? "right" : ""}>
            {goals
              .filter((g) => g.team === side)
              .map((g, i) => (
                <div key={i}>
                  {g.player.split(" ").slice(-1)[0]} {g.minute}'
                </div>
              ))}
          </div>
        ))}
      </div>
      <div className="recap-grid">
        <div className="recap-stats">
          {rows.map(([label, h, a, hv, av]) => (
            <div key={label} className="recap-row">
              <span className="v">{h}</span>
              <div>
                <span className="label">{label}</span>
                <div className="split">
                  <span style={{ width: `${(hv / (hv + av || 1)) * 100}%`, background: home.colors[0] }} />
                  <span style={{ width: `${(av / (hv + av || 1)) * 100}%`, background: away.colors[0] }} />
                </div>
              </div>
              <span className="v right">{a}</span>
            </div>
          ))}
        </div>
        <div className="recap-ratings">
          <span className="label">{tr(lang, "top_rated")}</span>
          {ratings.map((r) => (
            <div key={r.id} className="rating">
              <i style={{ background: meta.teams[r.team].colors[0] }} />
              <span>{r.name}</span>
              <b>{r.rating.toFixed(1)}</b>
            </div>
          ))}
        </div>
      </div>
      <p className="recap-text">{text}</p>
    </div>
  );
}
