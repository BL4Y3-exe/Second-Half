import { useCallback, useRef, useState } from "react";
import { NOTES } from "./notes";
import type { Club, Meta } from "./types";
import { useDismiss } from "./useDismiss";

const SPEEDS = [1, 5, 10, 20, 40];

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
  playing: Meta | null; // the match on screen, which the button names
}

/** Which match to play: clubs, match number, speed and the demo switch, tucked behind one button. */
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
        Match {playing?.seed ?? form.seed} · {playing?.speed ?? form.speed}x
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
          <div className="clubs">
            <label data-note={NOTES.seed}>
              Match no.
              <input
                type="number"
                name="seed"
                min={0}
                inputMode="numeric"
                autoComplete="off"
                value={form.seed}
                onChange={(e) => setForm({ ...form, seed: Number(e.target.value) || 0 })}
              />
            </label>
            <label data-note={NOTES.speed}>
              Speed
              <select
                name="speed"
                value={form.speed}
                onChange={(e) => setForm({ ...form, speed: Number(e.target.value) })}
              >
                {SPEEDS.map((s) => (
                  <option key={s} value={s}>
                    {s}x
                  </option>
                ))}
              </select>
            </label>
          </div>
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
