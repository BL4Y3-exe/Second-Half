import { useCallback, useRef, useState } from "react";
import { LANGS, MODES, tr } from "../i18n";
import { NOTES } from "../notes";
import type { Meta, Overlay, Snapshot, TraceStep } from "../types";
import type { FrameBuffer, Status } from "../useLiveMatch";
import { useDismiss } from "../useDismiss";
import { ViewerControls, ViewerStage, type ViewerSettings } from "../Viewer";
import { BehindStrip } from "./BehindStrip";

interface Props {
  meta: Meta;
  frames: React.RefObject<FrameBuffer>;
  slots: { HOME: string[]; AWAY: string[] };
  overlays: Overlay[];
  trace: TraceStep[];
  snapshot: Snapshot | null;
  clock: string;
  status: Status;
  you: ViewerSettings;
  setYou: (s: ViewerSettings) => void;
  guest: ViewerSettings | null;
  setGuest: (s: ViewerSettings | null) => void;
  scoreBug: React.ReactNode;
  bar: React.ReactNode; // the view switch and match set-up, shared with the Analysis view
  onTrace: () => void;
}

/** The guest a new second viewer starts as: a Spanish-speaking casual fan of the away side. */
export const GUEST: ViewerSettings = { mode: "casual", lang: "es", favourite: "AWAY" };

/** What a viewer has picked, in their own language: "Casual fan · Español · KMR fan". */
function describe(meta: Meta, s: ViewerSettings): string {
  const mode = MODES.find((m) => m.id === s.mode)!.label[s.lang];
  const lang = LANGS.find((l) => l.id === s.lang)!.label;
  const side = s.favourite ? `${meta.teams[s.favourite].short} fan` : "Neutral";
  return `${mode} · ${lang} · ${side}`;
}

function Profile({
  meta,
  name,
  settings,
  onChange,
  onRemove,
}: {
  meta: Meta;
  name: string;
  settings: ViewerSettings;
  onChange: (s: ViewerSettings) => void;
  onRemove?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const close = useCallback(() => setOpen(false), []);
  useDismiss(box, open, close);
  const colour = settings.favourite ? meta.teams[settings.favourite].colors[0] : "#3d5170";
  return (
    <div className="profile-box" ref={box}>
      <button
        type="button"
        className={`profile${open ? " on" : ""}`}
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        data-note={NOTES.profile}
      >
        <span className="avatar" style={{ background: colour }} aria-hidden="true">
          {name[0]}
        </span>
        <span className="who">
          <b>{name}</b>
          <span>{describe(meta, settings)}</span>
        </span>
      </button>
      {open && (
        <div className="popover viewer-pop" role="dialog" aria-label={`${name}: how they watch`}>
          <ViewerControls meta={meta} settings={settings} onChange={onChange} />
          {onRemove && (
            <button type="button" className="text-button" onClick={onRemove}>
              Close the guest screen
            </button>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * The Living Room: the match as a TV broadcast, seen through a tilted main camera, with each viewer's
 * own graphics and a strip under the picture showing how the agents made the one on air.
 */
export function Watch(props: Props) {
  const { meta, frames, slots, overlays, trace, snapshot, clock, status, you, setYou, guest, setGuest } = props;
  const [onAir, setOnAir] = useState<Overlay | null>(null);
  const [lastAired, setLastAired] = useState<Overlay | null>(null);
  const report = useCallback((ov: Overlay | null) => {
    setOnAir(ov);
    if (ov) setLastAired(ov);
  }, []);
  const stage = { meta, frames, slots, overlays, snapshot, clock, status };
  const shown = onAir ?? lastAired;
  return (
    <div className="tv">
      <ViewerStage {...stage} settings={you} variant="tv" onAir={report} />
      <div className="tv-top">
        <div className="tv-left">{props.scoreBug}</div>
        <div className="tv-centre">{props.bar}</div>
        <div className="tv-right">
          <span className="watching">{tr(you.lang, "watching")}</span>
          <Profile meta={meta} name="You" settings={you} onChange={setYou} />
          {guest ? (
            <Profile meta={meta} name="Guest" settings={guest} onChange={setGuest} onRemove={() => setGuest(null)} />
          ) : (
            <button
              type="button"
              className="add-viewer"
              aria-label="Add a second viewer"
              data-note={NOTES.addViewer}
              onClick={() => setGuest(GUEST)}
            >
              +
            </button>
          )}
        </div>
      </div>
      {guest && (
        <section className="tv-pip" aria-label="Guest's screen">
          <ViewerStage {...stage} settings={guest} variant="pip" />
          <span className="pip-tag">
            Guest · <span lang={guest.lang}>{describe(meta, guest)}</span>
          </span>
        </section>
      )}
      <BehindStrip
        overlay={shown}
        live={onAir !== null}
        steps={shown ? trace.filter((s) => s.moment_id === shown.moment_id) : []}
        lang={you.lang}
        onTrace={props.onTrace}
      />
    </div>
  );
}
