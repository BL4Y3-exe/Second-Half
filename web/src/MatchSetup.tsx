import { useCallback, useRef, useState } from "react";
import { NOTES } from "./notes";
import type { Club, Meta } from "./types";
import { useDismiss } from "./useDismiss";

const MATCH_MINUTES = 96; // a match with stoppage time, so 8x takes about 12 minutes

/** How long a whole match takes at the speed it plays at. */
function lasts(speed: number): string {
  const minutes = MATCH_MINUTES / speed;
  return minutes >= 60 ? "about an hour and a half" : `about ${Math.round(minutes)} minutes`;
}

export interface MatchForm {
  home: string;
  away: string;
  seed: number;
  speed: number;
  plant: boolean;
}

interface Props {
  clubs: Club[];
  form: MatchForm;
  setForm: (f: MatchForm) => void;
  onKickOff: () => void;
  playing: Meta | null; // the match on screen: the button says when its demo switch is on
}

/** Which match to play next: the clubs and the demo switch, tucked behind one button. Each kick-off is a new match. */
export function MatchSetup({ clubs, form, setForm, onKickOff, playing }: Props) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const close = useCallback(() => setOpen(false), []);
  useDismiss(box, open, close);
  return (
    <div className="setup" ref={box}>
      <button
        type="button"
        className={`setup-toggle${open ? " on" : ""}`}
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        data-note={NOTES.setup}
      >
        New match
        {playing?.planted_slips && <span className="armed">slip armed</span>}
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>
      {open && (
        <form
          className="controls popover"
          onSubmit={(e) => {
            e.preventDefault();
            onKickOff();
            close();
          }}
        >
          <div className="clubs">
            <label data-note={NOTES.home}>
              Home
              <select name="home" value={form.home} onChange={(e) => setForm({ ...form, home: e.target.value })}>
                {clubs.map((c) => (
                  <option key={c.key} value={c.key} disabled={c.key === form.away}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
            <span className="vs" aria-hidden="true">
              v
            </span>
            <label data-note={NOTES.away}>
              Away
              <select name="away" value={form.away} onChange={(e) => setForm({ ...form, away: e.target.value })}>
                {clubs.map((c) => (
                  <option key={c.key} value={c.key} disabled={c.key === form.home}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <span className="speed-note" data-note={NOTES.speed}>
            A whole match takes {lasts(playing?.speed ?? form.speed)}.
          </span>
          <label className="switch" data-note={NOTES.plant}>
            <input
              type="checkbox"
              name="plant"
              checked={form.plant}
              onChange={(e) => setForm({ ...form, plant: e.target.checked })}
            />
            Plant a slip for the Fact-checker to catch
          </label>
          <button type="submit" className="kick-off" data-note={NOTES.kickOff}>
            Kick off
          </button>
        </form>
      )}
    </div>
  );
}
