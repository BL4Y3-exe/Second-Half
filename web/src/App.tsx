import { useEffect, useMemo, useState } from "react";
import { LANGS, MODES } from "./i18n";
import { EventFeed } from "./overlays/EventFeed";
import { StatsPanel } from "./overlays/StatsPanel";
import { TracePanel } from "./overlays/TracePanel";
import type { Club, Lang, Mode, Side } from "./types";
import { useLiveMatch, type MatchRequest } from "./useLiveMatch";
import { ViewerControls, ViewerStage, type ViewerSettings } from "./Viewer";

const SPEEDS = [1, 5, 10, 20, 40];

type View = "desk" | "split";

export default function App() {
  const [clubs, setClubs] = useState<Club[]>([]);
  const [form, setForm] = useState({ home: "harbourside", away: "kingsmere", seed: 9, speed: 10 });
  const [req, setReq] = useState<MatchRequest | null>(null);
  const [view, setView] = useState<View>("desk");
  const [desk, setDesk] = useState<ViewerSettings>({ mode: "analyst", lang: "en", favourite: null });
  // Split screen: the same match for two very different viewers.
  const [left, setLeft] = useState<ViewerSettings>({ mode: "analyst", lang: "en", favourite: null });
  const [right, setRight] = useState<ViewerSettings>({ mode: "casual", lang: "es", favourite: "AWAY" });
  const [tab, setTab] = useState<"feed" | "trace">("feed");
  const { meta, events, triggers, snapshot, overlays, trace, status, frames } = useLiveMatch(req);

  useEffect(() => {
    // ?seed=7&speed=20&mode=casual&lang=es&fav=HOME&tab=trace&view=split in the address bar sets up the screen.
    const params = new URLSearchParams(window.location.search);
    const start = {
      ...form,
      seed: Number(params.get("seed") ?? form.seed),
      speed: Number(params.get("speed") ?? form.speed),
    };
    setForm(start);
    const m = params.get("mode");
    const l = params.get("lang");
    const f = params.get("fav");
    setDesk({
      mode: MODES.some((x) => x.id === m) ? (m as Mode) : "analyst",
      lang: LANGS.some((x) => x.id === l) ? (l as Lang) : "en",
      favourite: f === "HOME" || f === "AWAY" ? f : null,
    });
    if (params.get("tab") === "trace") setTab("trace");
    if (params.get("view") === "split") setView("split");
    fetch("/api/clubs")
      .then((r) => r.json())
      .then(setClubs)
      .catch(() => setClubs([]));
    setReq({ ...start, run: 1 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const switchView = (v: View) => {
    setView(v);
    const url = new URL(window.location.href);
    if (v === "split") url.searchParams.set("view", "split");
    else url.searchParams.delete("view");
    window.history.replaceState(null, "", url);
  };

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

  const caught = trace.filter((s) => s.agent === "fact_checker" && s.status === "rejected").length;
  const lastEvent = events[events.length - 1];
  const clock = snapshot?.clock ?? lastEvent?.clock ?? "00:00";
  const kickOff = () => setReq({ ...form, run: (req?.run ?? 0) + 1 });
  const stage = (settings: ViewerSettings) =>
    meta && (
      <ViewerStage
        meta={meta}
        frames={frames}
        slots={slots}
        overlays={overlays}
        snapshot={snapshot}
        clock={clock}
        status={status}
        settings={settings}
      />
    );
  const placeholder = (
    <div className="placeholder">
      {status === "error" ? "Can't reach the match server. Is `python -m api` running?" : "Connecting…"}
    </div>
  );

  return (
    <div className={`app${view === "split" ? " wide" : ""}`}>
      <header>
        <div className="brand">
          <span className="logo">2H</span>
          <div>
            <h1>Second Half</h1>
            <p>Live AI match desk · synthetic match data</p>
          </div>
        </div>
        <div className="seg view-switch" role="group" aria-label="View">
          <button className={view === "desk" ? "on" : ""} onClick={() => switchView("desk")}>
            Match desk
          </button>
          <button className={view === "split" ? "on" : ""} onClick={() => switchView("split")}>
            Split screen
          </button>
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

      {view === "split" ? (
        <main className="split-screen">
          {meta ? (
            [
              { label: "Viewer 1", settings: left, set: setLeft },
              { label: "Viewer 2", settings: right, set: setRight },
            ].map((pane) => (
              <section key={pane.label} className="pane">
                <ViewerControls meta={meta} settings={pane.settings} onChange={pane.set} />
                {stage(pane.settings)}
              </section>
            ))
          ) : (
            <section className="pane wide-pane">{placeholder}</section>
          )}
          <aside>{meta && <TracePanel meta={meta} trace={trace} />}</aside>
        </main>
      ) : (
        <main>
          <section className="stage">
            {meta ? (
              <>
                <ViewerControls meta={meta} settings={desk} onChange={setDesk} />
                {stage(desk)}
                <StatsPanel meta={meta} snapshot={snapshot} />
              </>
            ) : (
              placeholder
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
      )}
    </div>
  );
}
