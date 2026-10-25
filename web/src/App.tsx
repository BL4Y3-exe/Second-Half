import { useEffect, useMemo, useState } from "react";
import { Analysis } from "./analysis/Analysis";
import { LANGS, MODES } from "./i18n";
import { MatchSetup, type MatchForm } from "./MatchSetup";
import { NoteTip } from "./NoteTip";
import { NOTES } from "./notes";
import { ScoreBug } from "./overlays/ScoreBug";
import type { Club, Lang, Mode, Side } from "./types";
import { useLiveMatch, type MatchRequest } from "./useLiveMatch";
import { type ViewerSettings } from "./Viewer";
import { GUEST, Watch } from "./watch/Watch";

type View = "watch" | "analysis";

export default function App() {
  const [clubs, setClubs] = useState<Club[]>([]);
  const [form, setForm] = useState<MatchForm>({
    home: "harbourside",
    away: "kingsmere",
    seed: 9,
    speed: 10,
    plant: false,
  });
  const [req, setReq] = useState<MatchRequest | null>(null);
  const [view, setView] = useState<View>("watch");
  const [you, setYou] = useState<ViewerSettings>({ mode: "analyst", lang: "en", favourite: null });
  const [guest, setGuest] = useState<ViewerSettings | null>(null);
  const live = useLiveMatch(req);
  const { meta, events, snapshot, status } = live;

  useEffect(() => {
    // ?seed=7&speed=20&mode=casual&lang=es&fav=HOME&view=analysis&guest=1&plant=1 in the address bar
    // sets up the screen.
    const params = new URLSearchParams(window.location.search);
    const start = {
      ...form,
      seed: Number(params.get("seed") ?? form.seed),
      speed: Number(params.get("speed") ?? form.speed),
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
  const clock = snapshot?.clock ?? lastEvent?.clock ?? "00:00";
  // Match seconds when the second half kicked off: the clock restarts at 45:00 then, whatever the stoppage time.
  let secondHalfAt: number | null = null;
  if (snapshot && snapshot.period >= 2) {
    const [mm, ss] = snapshot.clock.split(":").map(Number);
    secondHalfAt = Math.round(snapshot.t - (mm * 60 + ss - 45 * 60));
  }
  const kickOff = () => setReq({ ...form, run: (req?.run ?? 0) + 1 });

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
            onTrace={() => switchView("analysis")}
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
