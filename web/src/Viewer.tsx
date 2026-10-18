import { LANGS, MODES, tr } from "./i18n";
import { OverlayLayer } from "./overlays/OverlayLayer";
import { ScoreBug } from "./overlays/ScoreBug";
import { Pitch, type Pin, type Replay } from "./pitch/Pitch";
import { pinValue } from "./plugins/builtin";
import type { Lang, Meta, Mode, Overlay, Side, Snapshot } from "./types";
import type { FrameBuffer, Status } from "./useLiveMatch";
import { useOverlaySchedule } from "./useOverlaySchedule";

/** What one viewer has chosen: how much detail, which language, which club they support. */
export interface ViewerSettings {
  mode: Mode;
  lang: Lang;
  favourite: Side | null;
}

export function ViewerControls({
  meta,
  settings,
  onChange,
}: {
  meta: Meta;
  settings: ViewerSettings;
  onChange: (s: ViewerSettings) => void;
}) {
  const { mode, lang, favourite } = settings;
  return (
    <div className="viewer">
      <div className="seg" role="group" aria-label="Viewer mode">
        {MODES.map((m) => (
          <button key={m.id} className={mode === m.id ? "on" : ""} onClick={() => onChange({ ...settings, mode: m.id })}>
            {m.label[lang]}
          </button>
        ))}
      </div>
      <div className="seg" role="group" aria-label="Language">
        {LANGS.filter((l) => !meta.languages || meta.languages.includes(l.id)).map((l) => (
          <button key={l.id} className={lang === l.id ? "on" : ""} onClick={() => onChange({ ...settings, lang: l.id })}>
            {l.label}
          </button>
        ))}
      </div>
      <div className="seg" role="group" aria-label="Favourite club">
        <button className={favourite === null ? "on" : ""} onClick={() => onChange({ ...settings, favourite: null })}>
          Neutral
        </button>
        {(["HOME", "AWAY"] as Side[]).map((side) => (
          <button
            key={side}
            className={favourite === side ? "on" : ""}
            onClick={() => onChange({ ...settings, favourite: side })}
          >
            <i className="dot" style={{ background: meta.teams[side].colors[0] }} />
            {meta.teams[side].short} fan
          </button>
        ))}
      </div>
    </div>
  );
}

interface StageProps {
  meta: Meta;
  frames: React.RefObject<FrameBuffer>;
  slots: { HOME: string[]; AWAY: string[] };
  overlays: Overlay[];
  snapshot: Snapshot | null;
  clock: string;
  status: Status;
  settings: ViewerSettings;
}

/** One viewer's screen: the pitch with the score bug and the graphics the schedule puts on air for them. */
export function ViewerStage({ meta, frames, slots, overlays, snapshot, clock, status, settings }: StageProps) {
  const { mode, lang, favourite } = settings;
  const onAir = useOverlaySchedule(overlays, frames, { speed: meta.speed, favourite });

  const lower = onAir["lower-third"];
  const drawing = lower?.overlay.telestrator;
  const replay: Replay | null = drawing
    ? {
        drawing: {
          ...drawing,
          zones: drawing.zones.map((z) => ({ ...z, label: z.label === "the gap" ? tr(lang, "the_gap") : z.label })),
        },
        startedAt: lower.startedAt,
        duration_s: lower.overlay.duration_s,
      }
    : null;
  const tagged = onAir["pitch"]?.overlay;
  const pin: Pin | null =
    tagged?.player != null ? { player: tagged.player, title: tr(lang, tagged.kind), value: pinValue(tagged) } : null;

  return (
    <div className="pitch-wrap">
      <Pitch meta={meta} frames={frames} slots={slots} replay={replay} pin={pin} />
      <div className="overlay-top-left">
        <ScoreBug meta={meta} snapshot={snapshot} clock={clock} />
      </div>
      {replay && <div className="replay-badge">{tr(lang, "replay")}</div>}
      <OverlayLayer onAir={onAir} meta={meta} mode={mode} lang={lang} />
      {status === "finished" && !onAir["full-screen"] && <div className="overlay-banner">{tr(lang, "full_time")}</div>}
    </div>
  );
}
