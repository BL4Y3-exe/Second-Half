import { useState } from "react";
import { tr } from "../i18n";
import { ShapePitch } from "../pitch/ShapePitch";
import type { Lang, Meta, Mode, Overlay, Side, XY } from "../types";

/** What every graphics plugin is handed: the Director's item and the viewer's text for it. */
export interface PluginProps {
  overlay: Overlay;
  text: string;
  meta: Meta;
  lang: Lang;
  mode: Mode;
  next?: Next; // after the full-time card: the way to the match analysis
}

/** The way from the full-time card to the match analysis, and the seconds until the page goes there itself. */
export interface Next {
  go: () => void;
  seconds: number | null;
}

/** The button to the match analysis, with the countdown to going there anyway. */
export function AnalysisButton({ next, lang }: { next: Next; lang: Lang }) {
  return (
    <div className="to-analysis">
      <button type="button" onClick={next.go}>
        {tr(lang, "see_analysis")}
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M5 12h14M13 6l6 6-6 6" />
        </svg>
      </button>
      {next.seconds !== null && (
        <span role="timer">
          {tr(lang, "opening_in")} {next.seconds} s
        </span>
      )}
    </div>
  );
}

const num = (v: unknown, digits = 0) => (typeof v === "number" ? v.toFixed(digits) : "–");
const str = (v: unknown) => (typeof v === "string" ? v : "");
const seconds = (v: unknown, lang: Lang) => num(v, 1).replace(".", lang === "es" ? "," : ".");

/**
 * The chips for a shot, how fast the ball was won back when a counter-press started the move, and the half-space
 * the move came through.
 */
function shotChips(d: Overlay["data"], lang: Lang): [string, string][] {
  const chips: [string, string][] = [
    [tr(lang, "xg"), num(d.xg, 2)],
    [tr(lang, "distance"), `${num(d.distance_m)} m`],
    [tr(lang, "shot_speed_label"), `${num(d.shot_speed_kmh)} km/h`],
  ];
  if (typeof d.won_back_s === "number") chips.push([tr(lang, "to_win_it_back"), `${seconds(d.won_back_s, lang)} s`]);
  if (d.half_space === "left" || d.half_space === "right") chips.push(["", tr(lang, `${d.half_space}_half_space`)]);
  return chips;
}

/** The stat chips under a card's headline. A casual viewer gets none: their line already says what matters. */
function Chips({ items, mode }: { items: [string, string][]; mode: Mode }) {
  if (mode === "casual") return null;
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

export function GoalCard({ overlay, meta, lang, mode }: PluginProps) {
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
      <Chips items={shotChips(d, lang)} mode={mode} />
    </>
  );
}

export function ShotCard({ overlay, lang, mode }: PluginProps) {
  const d = overlay.data;
  const outcome = str(lang === "es" ? d.outcome_text_es : d.outcome_text) || str(d.outcome_text);
  return (
    <>
      <div className="lt-main">
        <span className="lt-name">{str(d.player)}</span>
        {outcome && <span className="lt-outcome">{outcome}</span>}
      </div>
      <Chips items={shotChips(d, lang)} mode={mode} />
    </>
  );
}

export function PassCard({ overlay, lang, mode }: PluginProps) {
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
      <Chips items={chips} mode={mode} />
    </>
  );
}

export function PressCard({ overlay, meta, lang, mode }: PluginProps) {
  const d = overlay.data;
  const side = (overlay.team ?? "HOME") as Side;
  const outcome = str(lang === "es" ? d.outcome_text_es : d.outcome_text) || str(d.outcome_text);
  const chips: [string, string][] = [[tr(lang, "to_win_it_back"), `${seconds(d.won_back_s, lang)} s`]];
  if (typeof d.shot_after_s === "number") chips.push([tr(lang, "to_the_shot"), `${num(d.shot_after_s)} s`]);
  if (typeof d.counter_press_wins === "number") {
    chips.push([tr(lang, "press_wins"), `${num(d.counter_press_wins)}/${num(d.counter_presses)}`]);
  }
  return (
    <>
      <div className="lt-main">
        <span className="lt-name">{meta.teams[side].name}</span>
        <span className="lt-arrow">→</span>
        <span className="lt-name">{str(d.player)}</span>
        {outcome && <span className="lt-outcome">{outcome}</span>}
      </div>
      <Chips items={chips} mode={mode} />
    </>
  );
}

export function MomentumBar({ overlay, meta, lang, mode }: PluginProps) {
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
        {mode !== "casual" && (
          <span className="lt-tilt-label">
            <b>{num(share)}%</b> {tr(lang, "final_third")}
          </span>
        )}
      </div>
    </>
  );
}

export function StatCard({ overlay, lang }: PluginProps) {
  const line = (lang === "es" && str(overlay.data.line_es)) || str(overlay.data.line);
  return <div className="lt-main lt-line">{line}</div>;
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

interface Shape {
  positions: XY[];
  formation: string;
  back_line_m: number;
}

type Shapes = Record<Side, { on: Shape; off: Shape }>;

/** Half time: each team's average shape, attacking left to right, with the ball or without it at a click. */
function RecapShapes({ shapes, meta, lang }: { shapes: Shapes; meta: Meta; lang: Lang }) {
  const [state, setState] = useState<"on" | "off">("on");
  return (
    <div className="recap-shapes">
      <div className="recap-shapes-head">
        <span className="label">{tr(lang, "shape_title")}</span>
        <div className="seg" role="group" aria-label={tr(lang, "shape_title")}>
          {(["on", "off"] as const).map((s) => (
            <button
              key={s}
              type="button"
              className={state === s ? "on" : ""}
              aria-pressed={state === s}
              onClick={() => setState(s)}
            >
              {tr(lang, s === "on" ? "with_ball" : "without_ball")}
            </button>
          ))}
        </div>
        <span className="dir">{tr(lang, "attacking")} →</span>
      </div>
      <div className="recap-shapes-grid">
        {(["HOME", "AWAY"] as Side[]).map((side) => {
          const team = meta.teams[side];
          const shape = shapes[side][state];
          return (
            <figure key={side}>
              <ShapePitch
                positions={shape.positions}
                color={team.colors[0]}
                keeper={side === "HOME" ? "#f5c518" : "#9be15d"}
                label={`${team.name}: ${shape.formation}`}
              />
              <figcaption>
                <span className="team">
                  <i style={{ background: team.colors[0] }} />
                  {team.short}
                </span>
                <b>{shape.formation}</b>
                <span>
                  {tr(lang, "back_line")} {shape.back_line_m} m
                </span>
              </figcaption>
            </figure>
          );
        })}
      </div>
    </div>
  );
}

export function RecapCard({ overlay, text, meta, lang, mode, next }: PluginProps) {
  const d = overlay.data;
  const { HOME: home, AWAY: away } = meta.teams;
  const rows: [string, string, string, number, number][] = [
    [tr(lang, "shots"), num(d.home_shots), num(d.away_shots), Number(d.home_shots) || 0, Number(d.away_shots) || 0],
    [tr(lang, "possession"), `${num(d.home_poss)}%`, `${num(d.away_poss)}%`, Number(d.home_poss) || 0, Number(d.away_poss) || 0],
  ];
  if (mode !== "casual") {
    const xg = [Number(d.home_xg) || 0, Number(d.away_xg) || 0];
    rows.unshift([tr(lang, "xg"), num(d.home_xg, 2), num(d.away_xg, 2), xg[0], xg[1]]);
  }
  const ratings = (d.ratings as Rating[] | undefined) ?? [];
  const goals = (d.goals as Goal[] | undefined) ?? [];
  const shapes = mode !== "casual" ? (d.shapes as Shapes | undefined) : undefined;
  const halfTime = overlay.headline.toLowerCase().includes("half");
  const title = halfTime ? tr(lang, "half_time") : tr(lang, "full_time");
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
      {shapes && <RecapShapes shapes={shapes} meta={meta} lang={lang} />}
      <p className="recap-text">{text}</p>
      {!halfTime && next && <AnalysisButton next={next} lang={lang} />}
    </div>
  );
}
