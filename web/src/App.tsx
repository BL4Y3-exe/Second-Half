import { useEffect, useMemo, useState } from "react";
import { LANGS, MODES, tr } from "./i18n";
import { Pitch, type Pin, type Replay } from "./pitch/Pitch";
import { EventFeed } from "./overlays/EventFeed";
import { OverlayLayer } from "./overlays/OverlayLayer";
import { ScoreBug } from "./overlays/ScoreBug";
import { StatsPanel } from "./overlays/StatsPanel";
import { TracePanel } from "./overlays/TracePanel";
import { pinValue } from "./plugins/builtin";
import type { Club, Lang, Mode, Side } from "./types";
import { useLiveMatch, type MatchRequest } from "./useLiveMatch";
import { useOverlaySchedule } from "./useOverlaySchedule";

const SPEEDS = [1, 5, 10, 20, 40];

export default function App() {
  const [clubs, setClubs] = useState<Club[]>([]);
  const [form, setForm] = useState({ home: "harbourside", away: "kingsmere", seed: 9, speed: 10 });
  const [req, setReq] = useState<MatchRequest | null>(null);
  const [mode, setMode] = useState<Mode>("analyst");
  const [lang, setLang] = useState<Lang>("en");
  const [favourite, setFavourite] = useState<Side | null>(null);
  const [tab, setTab] = useState<"feed" | "trace">("feed");
  const { meta, events, triggers, snapshot, overlays, trace, status, frames } = useLiveMatch(req);
  const onAir = useOverlaySchedule(overlays, frames, { speed: meta?.speed ?? form.speed, favourite });

  useEffect(() => {
    // ?seed=7&speed=20&mode=casual&lang=es&fav=HOME&tab=trace in the address bar sets up the screen.
    const params = new URLSearchParams(window.location.search);
    const start = {
      ...form,
      seed: Number(params.get("seed") ?? form.seed),
      speed: Number(params.get("speed") ?? form.speed),
    };
    setForm(start);
    const m = params.get("mode");
    if (MODES.some((x) => x.id === m)) setMode(m as Mode);
    const l = params.get("lang");
    if (LANGS.some((x) => x.id === l)) setLang(l as Lang);
    const f = params.get("fav");
    if (f === "HOME" || f === "AWAY") setFavourite(f);
    if (params.get("tab") === "trace") setTab("trace");
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

  const lower = onAir["lower-third"];
  const replay: Replay | null =
    lower?.overlay.telestrator != null
      ? {
          drawing: {
            ...lower.overlay.telestrator,
            zones: lower.overlay.telestrator.zones.map((z) => ({ ...z, label: z.label === "the gap" ? tr(lang, "the_gap") : z.label })),
          },
          startedAt: lower.startedAt,
          duration_s: lower.overlay.duration_s,
        }
      : null;
  const tagged = onAir["pitch"]?.overlay;
  const pin: Pin | null =
    tagged?.player != null ? { player: tagged.player, title: tr(lang, tagged.kind), value: pinValue(tagged) } : null;
  const caught = trace.filter((s) => s.status === "rejected").length;

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
              <div className="viewer">
                <div className="seg" role="group" aria-label="Viewer mode">
                  {MODES.map((m) => (
                    <button key={m.id} className={mode === m.id ? "on" : ""} onClick={() => setMode(m.id)}>
                      {m.label[lang]}
                    </button>
                  ))}
                </div>
                <div className="seg" role="group" aria-label="Language">
                  {LANGS.filter((l) => !meta.languages || meta.languages.includes(l.id)).map((l) => (
                    <button key={l.id} className={lang === l.id ? "on" : ""} onClick={() => setLang(l.id)}>
                      {l.label}
                    </button>
                  ))}
                </div>
                <div className="seg" role="group" aria-label="Favourite club">
                  <button className={favourite === null ? "on" : ""} onClick={() => setFavourite(null)}>
                    Neutral
                  </button>
                  {(["HOME", "AWAY"] as Side[]).map((side) => (
                    <button key={side} className={favourite === side ? "on" : ""} onClick={() => setFavourite(side)}>
                      <i className="dot" style={{ background: meta.teams[side].colors[0] }} />
                      {meta.teams[side].short} fan
                    </button>
                  ))}
                </div>
              </div>
              <div className="pitch-wrap">
                <Pitch meta={meta} frames={frames} slots={slots} replay={replay} pin={pin} />
                <div className="overlay-top-left">
                  <ScoreBug meta={meta} snapshot={snapshot} clock={clock} />
                </div>
                {replay && <div className="replay-badge">{tr(lang, "replay")}</div>}
                <OverlayLayer onAir={onAir} meta={meta} mode={mode} lang={lang} />
                {status === "finished" && !onAir["full-screen"] && (
                  <div className="overlay-banner">{tr(lang, "full_time")}</div>
                )}
              </div>
              <StatsPanel meta={meta} snapshot={snapshot} />
            </>
          ) : (
            <div className="placeholder">
              {status === "error" ? "Can't reach the match server. Is `python -m api` running?" : "Connecting…"}
            </div>
          )}
        </section>
        <aside>
          {meta && (
            <>
              <div className="tabs" role="tablist">
                <button role="tab" aria-selected={tab === "feed"} onClick={() => setTab("feed")}>
                  Match feed
                </button>
                <button role="tab" aria-selected={tab === "trace"} onClick={() => setTab("trace")}>
                  Agent trace
                  {caught > 0 && <span className="pill">{caught} caught</span>}
                </button>
              </div>
              {tab === "feed" ? (
                <EventFeed meta={meta} events={events} triggers={triggers} />
              ) : (
                <TracePanel meta={meta} trace={trace} />
              )}
            </>
          )}
        </aside>
      </main>
    </div>
  );
}
