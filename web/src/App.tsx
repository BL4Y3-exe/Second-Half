import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Analysis } from "./analysis/Analysis";
import { LANGS, MODES } from "./i18n";
import { MatchSetup, type MatchForm } from "./MatchSetup";
import { NoteTip } from "./NoteTip";
import { NOTES } from "./notes";
import { ScoreBug } from "./overlays/ScoreBug";
import type { Club, Lang, Mode, Side, Snapshot } from "./types";
import { useLiveMatch, type MatchRequest } from "./useLiveMatch";
import { type ViewerSettings } from "./Viewer";
import { GUEST, Watch } from "./watch/Watch";

type View = "watch" | "analysis";

// Match seconds per viewing second unless the viewer picks another: a whole match takes about 8 minutes, with time for
// the agents to write each graphic before the next moment comes along.
const SPEED = 8;
const TO_ANALYSIS_S = 15; // seconds the full-time card stays up before the page moves on to the analysis

/** The broadcast clock in whole match minutes, 01' from kick-off; stoppage time reads 45+2' or 90+3'. */
function minuteClock(clock: string, period: number): string {
  const minute = Number(clock.split(":")[0]) + 1;
  const end = period >= 2 ? 90 : 45;
  return minute > end ? `${end}+${minute - end}'` : `${String(minute).padStart(2, "0")}'`;
}

export default function App() {
  const [clubs, setClubs] = useState<Club[]>([]);
  const [form, setForm] = useState<MatchForm>({
    home: "harbourside",
    away: "kingsmere",
    seed: 7,
    speed: SPEED,
    plant: false,
  });
  const [req, setReq] = useState<MatchRequest | null>(null);
  const [view, setView] = useState<View>("watch");
  const [countdown, setCountdown] = useState<number | null>(null); // seconds until the page moves on after full time
  const [you, setYou] = useState<ViewerSettings>({ mode: "analyst", lang: "en", favourite: null });
  const [guest, setGuest] = useState<ViewerSettings | null>(null);
  const live = useLiveMatch(req);
  const { meta, events, status } = live;
  // Paused, the screen holds the numbers it had at that moment while the match plays on behind it.
  const [pause, setPause] = useState<{ snapshot: Snapshot | null } | null>(null);
  const paused = pause !== null;
  const snapshot = pause ? pause.snapshot : live.snapshot;
  const latest = useRef(live.snapshot);
  latest.current = live.snapshot;
  const togglePause = useCallback(() => setPause((p) => (p ? null : { snapshot: latest.current })), []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.code !== "Space" || e.repeat) return;
      // A focused control keeps Space for itself.
      if ((e.target as HTMLElement).closest?.("button, input, select, textarea, a, [contenteditable]")) return;
      e.preventDefault();
      togglePause();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [togglePause]);

  useEffect(() => {
    // ?home=ashford&away=northgate&seed=7&speed=20&mode=casual&lang=es&fav=HOME&view=analysis&guest=1&plant=1 in the
    // address bar sets up the screen.
    const params = new URLSearchParams(window.location.search);
    const start = {
      ...form,
      home: params.get("home") ?? form.home,
      away: params.get("away") ?? form.away,
      seed: Number(params.get("seed") ?? form.seed),
      speed: Math.min(60, Math.max(1, Number(params.get("speed")) || form.speed)),
      plant: params.get("plant") === "1",
    };
    setForm(start);
    const m = params.get("mode");
    const l = params.get("lang");
    const f = params.get("fav");
    setYou({
      mode: MODES.some((x) => x.id === m) ? (m as Mode) : "analyst",
      lang: LANGS.some((x) => x.id === l) ? (l as Lang) : "en",
      favourite: f === "HOME" || f === "AWAY" ? f : null,
    });
    // Older links: view=split was two viewers side by side, tab=trace the agent trace.
    if (params.get("view") === "analysis" || params.get("tab") === "trace") setView("analysis");
    if (params.get("guest") === "1" || params.get("view") === "split") setGuest(GUEST);
    fetch("/api/clubs")
      .then((r) => r.json())
      .then(setClubs)
      .catch(() => setClubs([]));
    setReq({ ...start, run: 1 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const switchView = (v: View) => {
    setCountdown(null);
    setView(v);
    const url = new URL(window.location.href);
    url.searchParams.delete("tab");
    if (v === "analysis") url.searchParams.set("view", "analysis");
    else url.searchParams.delete("view");
    window.history.replaceState(null, "", url);
    window.scrollTo(0, 0);
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

  const lastEvent = events[events.length - 1];
  const clock = snapshot
    ? minuteClock(snapshot.clock, snapshot.period)
    : lastEvent
      ? minuteClock(lastEvent.clock, lastEvent.period)
      : "00'";
  // Match seconds when the second half kicked off: the clock restarts at 45:00 then, whatever the stoppage time.
  let secondHalfAt: number | null = null;
  if (snapshot && snapshot.period >= 2) {
    const [mm, ss] = snapshot.clock.split(":").map(Number);
    secondHalfAt = Math.round(snapshot.t - (mm * 60 + ss - 45 * 60));
  }
  // Each kick-off is a new match. Its number goes in the address bar, so the link replays it.
  const kickOff = () => {
    const next = { ...form, seed: Math.floor(Math.random() * 9999) + 1 };
    setPause(null);
    setForm(next);
    setReq({ ...next, run: (req?.run ?? 0) + 1 });
    const url = new URL(window.location.href);
    url.searchParams.set("home", next.home);
    url.searchParams.set("away", next.away);
    url.searchParams.set("seed", String(next.seed));
    if (next.speed !== SPEED) url.searchParams.set("speed", String(next.speed));
    else url.searchParams.delete("speed");
    if (next.plant) url.searchParams.set("plant", "1");
    else url.searchParams.delete("plant");
    window.history.replaceState(null, "", url);
  };

  // After the final whistle the Watch page shows the full-time card, then moves on to the match analysis.
  const viewNow = useRef(view);
  viewNow.current = view;
  useEffect(() => {
    setCountdown(status === "finished" && viewNow.current === "watch" ? TO_ANALYSIS_S : null);
  }, [status]);
  useEffect(() => {
    if (countdown === null) return;
    if (countdown <= 0) {
      switchView("analysis");
      return;
    }
    const timer = window.setTimeout(() => setCountdown((s) => (s === null ? null : s - 1)), 1000);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [countdown]);

  const bar = (
    <div className="bar">
      <div className="seg view-switch" role="group" aria-label="View">
        {(["watch", "analysis"] as View[]).map((v) => (
          <button
            key={v}
            type="button"
            aria-pressed={view === v}
            className={view === v ? "on" : ""}
            onClick={() => switchView(v)}
            data-note={NOTES[v]}
          >
            {v === "watch" ? "Watch" : "Analysis"}
          </button>
        ))}
      </div>
      {meta && (
        <button
          type="button"
          className={`pause-button${paused ? " on" : ""}`}
          aria-pressed={paused}
          onClick={togglePause}
          data-note={paused ? NOTES.resume : NOTES.pause}
        >
          <svg viewBox="0 0 10 10" aria-hidden="true">
            {paused ? <path d="M2 1 L9 5 L2 9 Z" /> : <path d="M2 1 h2 v8 h-2 Z M6 1 h2 v8 h-2 Z" />}
          </svg>
          {paused ? "Live" : "Pause"}
        </button>
      )}
      <MatchSetup clubs={clubs} form={form} setForm={setForm} onKickOff={kickOff} playing={meta} />
    </div>
  );
  const scoreBug = meta && <ScoreBug meta={meta} snapshot={snapshot} clock={clock} status={status} lang={you.lang} />;
  const waiting = <div className="placeholder">{status === "error" ? NOTES.live.error : "Connecting…"}</div>;

  if (view === "watch") {
    return (
      <>
        <h1 className="sr-only">Second Half</h1>
        {meta ? (
          <Watch
            {...live}
            snapshot={snapshot}
            paused={paused}
            meta={meta}
            slots={slots}
            clock={clock}
            you={you}
            setYou={setYou}
            guest={guest}
            setGuest={setGuest}
            scoreBug={
              <>
                <span className="logo" aria-hidden="true">
                  2H
                </span>
                {scoreBug}
              </>
            }
            bar={bar}
            next={{ go: () => switchView("analysis"), seconds: countdown }}
          />
        ) : (
          <div className="tv tv-waiting">
            <div className="tv-top">
              <div className="tv-left" />
              <div className="tv-centre">{bar}</div>
              <div className="tv-right" />
            </div>
            {waiting}
          </div>
        )}
        <NoteTip />
      </>
    );
  }

  return (
    <div className="app">
      <header className="gallery">
        <div className="brand">
          <span className="logo" aria-hidden="true">
            2H
          </span>
          <div>
            <h1 translate="no">Second Half</h1>
            <p>Analysis · the gallery behind the broadcast</p>
          </div>
        </div>
        {status === "live" && (
          <span className="on-air" data-note={NOTES.live.live}>
            On air
          </span>
        )}
        {scoreBug}
        {bar}
      </header>
      {meta ? (
        <Analysis
          {...live}
          snapshot={snapshot}
          paused={paused}
          meta={meta}
          slots={slots}
          clock={clock}
          secondHalfAt={secondHalfAt}
          you={you}
          guest={guest}
        />
      ) : (
        waiting
      )}
      <NoteTip />
    </div>
  );
}
