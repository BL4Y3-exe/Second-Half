import { useEffect, useState } from "react";
import { LANGS, MODES, tr } from "./i18n";
import { favouriteNote, LANG_NOTES, MODE_NOTES, NOTES, VIEWER_GROUPS } from "./notes";
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
  // The note line explains whatever the pointer or keyboard is on, and the current mode the rest of the time.
  const [preview, setPreview] = useState<{ label: string; note: string } | null>(null);
  const current = MODES.find((m) => m.id === mode)!;
  const note = preview ?? { label: current.label[lang], note: MODE_NOTES[mode][lang] };
  const explain = (label: string, text: string) => ({
    onMouseEnter: () => setPreview({ label, note: text }),
    onMouseLeave: () => setPreview(null),
    onFocus: () => setPreview({ label, note: text }),
    onBlur: () => setPreview(null),
  });
  const fanOf = (side: Side) => ({
    label: `${meta.teams[side].short} fan`,
    note: favouriteNote(lang, meta.teams[side === "HOME" ? "AWAY" : "HOME"].name),
  });
  return (
    <div className="viewer">
      <div className="viewer-groups">
        <div className="group">
          <span className="group-label">{VIEWER_GROUPS.mode[lang]}</span>
          <div className="seg" role="group" aria-label={VIEWER_GROUPS.mode[lang]}>
            {MODES.map((m) => (
              <button
                key={m.id}
                className={mode === m.id ? "on" : ""}
                aria-pressed={mode === m.id}
                onClick={() => onChange({ ...settings, mode: m.id })}
                {...explain(m.label[lang], MODE_NOTES[m.id][lang])}
              >
                {m.label[lang]}
              </button>
            ))}
          </div>
        </div>
        <div className="group">
          <span className="group-label">{VIEWER_GROUPS.lang[lang]}</span>
          <div className="seg" role="group" aria-label={VIEWER_GROUPS.lang[lang]}>
            {LANGS.filter((l) => !meta.languages || meta.languages.includes(l.id)).map((l) => (
              <button
                key={l.id}
                lang={l.id}
                className={lang === l.id ? "on" : ""}
                aria-pressed={lang === l.id}
                onClick={() => onChange({ ...settings, lang: l.id })}
                {...explain(l.label, LANG_NOTES[l.id][lang])}
              >
                {l.label}
              </button>
            ))}
          </div>
        </div>
        <div className="group">
          <span className="group-label">{VIEWER_GROUPS.favourite[lang]}</span>
          <div className="seg" role="group" aria-label={VIEWER_GROUPS.favourite[lang]}>
            <button
              className={favourite === null ? "on" : ""}
              aria-pressed={favourite === null}
              onClick={() => onChange({ ...settings, favourite: null })}
              {...explain("Neutral", favouriteNote(lang, null))}
            >
              Neutral
            </button>
            {(["HOME", "AWAY"] as Side[]).map((side) => (
              <button
                key={side}
                className={favourite === side ? "on" : ""}
                aria-pressed={favourite === side}
                onClick={() => onChange({ ...settings, favourite: side })}
                {...explain(fanOf(side).label, fanOf(side).note)}
              >
                <i className="dot" style={{ background: meta.teams[side].colors[0] }} aria-hidden="true" />
                {meta.teams[side].short} fan
              </button>
            ))}
          </div>
        </div>
      </div>
      <p className={`viewer-note${preview ? " previewing" : ""}`} lang={lang}>
        <b>{note.label}:</b> {note.note}
      </p>
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
  /** tv: the main Living Room screen, seen through a tilted broadcast camera. pip: the guest's corner screen. */
  variant?: "tv" | "pip" | "flat";
  /** Told which item is on screen, so the page can show how the agents made it. */
  onAir?: (overlay: Overlay | null) => void;
}

/** A Telestrator zone's label in the viewer's language; a casual viewer doesn't get the xG one. */
function zoneLabel(label: string | undefined, mode: Mode, lang: Lang): string | undefined {
  if (label === "the gap") return tr(lang, "the_gap");
  if (mode === "casual" && label?.endsWith("xG")) return undefined;
  return label;
}

/** One viewer's screen: the pitch with the score bug and the graphics the schedule puts on air for them. */
export function ViewerStage(props: StageProps) {
  const { meta, frames, slots, overlays, snapshot, clock, status, settings, variant = "flat", onAir: report } = props;
  const { mode, lang, favourite } = settings;
  const onAir = useOverlaySchedule(overlays, frames, { speed: meta.speed, favourite });
  const showing = onAir["lower-third"]?.overlay ?? onAir["pitch"]?.overlay ?? onAir["full-screen"]?.overlay ?? null;
  useEffect(() => report?.(showing), [report, showing]);

  const lower = onAir["lower-third"];
  const drawing = lower?.overlay.telestrator;
  const replay: Replay | null = drawing
    ? {
        drawing: {
          ...drawing,
          zones: drawing.zones.map((z) => ({ ...z, label: zoneLabel(z.label, mode, lang) })),
        },
        startedAt: lower.startedAt,
        duration_s: lower.overlay.duration_s,
      }
    : null;
  const tagged = onAir["pitch"]?.overlay;
  const pin: Pin | null =
    tagged?.player != null ? { player: tagged.player, title: tr(lang, tagged.kind), value: pinValue(tagged) } : null;

  return (
    <div className={`pitch-wrap ${variant}`}>
      {variant === "flat" ? (
        <Pitch meta={meta} frames={frames} slots={slots} replay={replay} pin={pin} />
      ) : (
        <div className="camera">
          <Pitch meta={meta} frames={frames} slots={slots} replay={replay} pin={pin} />
        </div>
      )}
      <div className="overlay-top-left">
        <ScoreBug meta={meta} snapshot={snapshot} clock={clock} status={status} lang={lang} />
      </div>
      {replay && (
        <div className="replay-badge" data-note={NOTES.replay}>
          {tr(lang, "replay")}
        </div>
      )}
      <OverlayLayer onAir={onAir} meta={meta} mode={mode} lang={lang} />
      {status === "finished" && !onAir["full-screen"] && <div className="overlay-banner">{tr(lang, "full_time")}</div>}
    </div>
  );
}
