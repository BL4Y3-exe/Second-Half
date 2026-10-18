import { useEffect, useMemo, useState } from "react";
import { Pitch } from "./pitch/Pitch";
import { EventFeed } from "./overlays/EventFeed";
import { ScoreBug } from "./overlays/ScoreBug";
import { StatsPanel } from "./overlays/StatsPanel";
import type { Club, Side } from "./types";
import { useLiveMatch, type MatchRequest } from "./useLiveMatch";

const SPEEDS = [1, 5, 10, 20, 40];

export default function App() {
  const [clubs, setClubs] = useState<Club[]>([]);
  const [form, setForm] = useState({ home: "harbourside", away: "kingsmere", seed: 9, speed: 10 });
  const [req, setReq] = useState<MatchRequest | null>(null);
  const { meta, events, triggers, snapshot, status, frames } = useLiveMatch(req);

  useEffect(() => {
    // ?seed=7&speed=20 in the address bar picks the match to start with.
    const params = new URLSearchParams(window.location.search);
    const start = {
      ...form,
      seed: Number(params.get("seed") ?? form.seed),
      speed: Number(params.get("speed") ?? form.speed),
    };
    setForm(start);
    fetch("/api/clubs")
      .then((r) => r.json())
      .then(setClubs)
      .catch(() => setClubs([]));
    setReq({ ...start, run: 1 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Which player is in which slot changes only at substitutions.
  const slots = useMemo(() => {
    if (!meta) return { HOME: [], AWAY: [] } as { HOME: string[]; AWAY: string[] };
    const s = {
      HOME: meta.teams.HOME.players.slice(0, 11).map((p) => p.id),
      AWAY: meta.teams.AWAY.players.slice(0, 11).map((p) => p.id),
    };
    for (const ev of events) {
      if (ev.type === "substitution") s[ev.team as Side][ev.slot as number] = String(ev.player_in);
    }
    return s;
  }, [meta, events]);

  const lastEvent = events[events.length - 1];
  const clock = snapshot?.clock ?? lastEvent?.clock ?? "00:00";
  const kickOff = () => setReq({ ...form, run: (req?.run ?? 0) + 1 });

  return (
    <div className="app">
      <header>
        <div className="brand">
          <span className="logo">2H</span>
          <div>
            <h1>Second Half</h1>
            <p>Live AI match desk · synthetic match data</p>
          </div>
        </div>
        <form
          className="controls"
          onSubmit={(e) => {
            e.preventDefault();
            kickOff();
          }}
        >
          <label>
            Home
            <select value={form.home} onChange={(e) => setForm({ ...form, home: e.target.value })}>
              {clubs.map((c) => (
                <option key={c.key} value={c.key} disabled={c.key === form.away}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Away
            <select value={form.away} onChange={(e) => setForm({ ...form, away: e.target.value })}>
              {clubs.map((c) => (
                <option key={c.key} value={c.key} disabled={c.key === form.home}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Seed
            <input
              type="number"
              value={form.seed}
              onChange={(e) => setForm({ ...form, seed: Number(e.target.value) || 0 })}
            />
          </label>
          <label>
            Speed
            <select value={form.speed} onChange={(e) => setForm({ ...form, speed: Number(e.target.value) })}>
              {SPEEDS.map((s) => (
                <option key={s} value={s}>
                  {s}x
                </option>
              ))}
            </select>
          </label>
          <button type="submit">Kick off</button>
        </form>
      </header>

      <main>
        <section className="stage">
          {meta ? (
            <>
              <div className="pitch-wrap">
                <Pitch meta={meta} frames={frames} slots={slots} />
                <div className="overlay-top-left">
                  <ScoreBug meta={meta} snapshot={snapshot} clock={clock} />
                </div>
                {status === "finished" && <div className="overlay-banner">Full time</div>}
              </div>
              <StatsPanel meta={meta} snapshot={snapshot} />
            </>
          ) : (
            <div className="placeholder">
              {status === "error" ? "Can't reach the match server. Is `python -m api` running?" : "Connecting…"}
            </div>
          )}
        </section>
        <aside>{meta && <EventFeed meta={meta} events={events} triggers={triggers} />}</aside>
      </main>
    </div>
  );
}
