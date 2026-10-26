import { useEffect, useRef, useState } from "react";
import type {
  Frame,
  HalfSpaceBall,
  MatchEvent,
  Meta,
  MomentumPoint,
  Overlay,
  Press,
  Snapshot,
  TraceStep,
  Trigger,
  XY,
} from "./types";

export interface MatchRequest {
  home: string;
  away: string;
  seed: number;
  speed: number;
  plant: boolean; // the demo switch: plant wrong numbers for the Fact-checker to catch
  run: number; // bump to restart
}

export interface FrameBuffer {
  cur: Frame | null; // the newest frame
  history: Frame[]; // recent frames: the pitch plays a little behind the newest, and replays from them
  presses: Press[]; // recent counter-press windows and how they ended, drawn when the playback reaches them
  spaces: HalfSpaceBall[]; // recent passes into a half-space in the final third, lit when the ball gets there
}

const HISTORY = 2400;
const emptyBuffer = (): FrameBuffer => ({ cur: null, history: [], presses: [], spaces: [] });

/** A completed pass that lands in a half-space in the final third, timed for when the ball gets there. */
function halfSpaceBall(ev: MatchEvent): HalfSpaceBall | null {
  const lane = (ev.stats as { lane?: string } | undefined)?.lane;
  if (ev.type !== "pass" || (lane !== "left_half_space" && lane !== "right_half_space") || !ev.team) return null;
  const speed = Number(ev.ball_speed_kmh) / 3.6;
  const flight = speed > 0 ? Number(ev.distance_m) / speed : 0;
  return { id: ev.id, team: ev.team, t: ev.t + (Number.isFinite(flight) ? flight : 0), lane, to: ev.to as XY };
}

export type Status = "connecting" | "live" | "finished" | "error";

/** Subscribes to the live feed. Frames go into a ref (read by the pitch every animation frame), the rest into state. */
export function useLiveMatch(req: MatchRequest | null) {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [events, setEvents] = useState<MatchEvent[]>([]);
  const [triggers, setTriggers] = useState<Trigger[]>([]);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [momentum, setMomentum] = useState<MomentumPoint[]>([]);
  const [overlays, setOverlays] = useState<Overlay[]>([]);
  const [trace, setTrace] = useState<TraceStep[]>([]);
  const [status, setStatus] = useState<Status>("connecting");
  const frames = useRef<FrameBuffer>(emptyBuffer());

  useEffect(() => {
    if (!req) return;
    setMeta(null);
    setEvents([]);
    setTriggers([]);
    setSnapshot(null);
    setMomentum([]);
    setOverlays([]);
    setTrace([]);
    setStatus("connecting");
    frames.current = emptyBuffer();

    const qs = new URLSearchParams({
      home: req.home,
      away: req.away,
      seed: String(req.seed),
      speed: String(req.speed),
    });
    if (req.plant) qs.set("plant", "1");
    const source = new EventSource(`/api/live?${qs}`);
    let pendingEvents: MatchEvent[] = [];
    const seenEvents = new Set<string>();
    let flushTimer: number | undefined;
    const flush = () => {
      flushTimer = undefined;
      const batch = pendingEvents;
      pendingEvents = [];
      setEvents((old) => [...old, ...batch].slice(-400));
    };

    source.addEventListener("meta", (e) => {
      setMeta(JSON.parse((e as MessageEvent).data));
      setStatus("live");
    });
    source.addEventListener("frame", (e) => {
      const f: Frame = JSON.parse((e as MessageEvent).data);
      const buf = frames.current;
      buf.cur = f;
      buf.history.push(f);
      if (buf.history.length > HISTORY + 200) buf.history.splice(0, 200);
    });
    source.addEventListener("press", (e) => {
      const press: Press = JSON.parse((e as MessageEvent).data);
      const buf = frames.current;
      buf.presses = [...buf.presses.filter((p) => p.id !== press.id), press].slice(-20);
    });
    source.addEventListener("event", (e) => {
      const ev: MatchEvent = JSON.parse((e as MessageEvent).data);
      if (seenEvents.has(ev.id)) return; // a reconnect replays the latest events
      seenEvents.add(ev.id);
      const space = halfSpaceBall(ev);
      if (space) frames.current.spaces = [...frames.current.spaces, space].slice(-20);
      pendingEvents.push(ev);
      if (flushTimer === undefined) flushTimer = window.setTimeout(flush, 150);
    });
    source.addEventListener("trigger", (e) => {
      const tr: Trigger = JSON.parse((e as MessageEvent).data);
      setTriggers((old) => [...old, tr].slice(-100));
    });
    source.addEventListener("stats", (e) => {
      const snap: Snapshot = JSON.parse((e as MessageEvent).data);
      setSnapshot(snap);
      // One momentum point per minute played, like the server's history.
      const minute = Math.floor(snap.t / 60);
      setMomentum((old) =>
        old.length && old[old.length - 1].minute >= minute ? old : [...old, { minute, momentum: snap.momentum }],
      );
    });
    source.addEventListener("history", (e) => {
      const { momentum: points }: { momentum: MomentumPoint[] } = JSON.parse((e as MessageEvent).data);
      setMomentum((old) => [...points, ...old.filter((p) => p.minute > (points.at(-1)?.minute ?? -1))]);
    });
    source.addEventListener("overlay", (e) => {
      const ov: Overlay = JSON.parse((e as MessageEvent).data);
      setOverlays((old) => (old.some((o) => o.id === ov.id) ? old : [...old, ov].slice(-60)));
    });
    source.addEventListener("trace", (e) => {
      const step: TraceStep = JSON.parse((e as MessageEvent).data);
      setTrace((old) => (old.some((s) => s.id === step.id) ? old : [...old, step].slice(-300)));
    });
    source.addEventListener("end", () => {
      setStatus("finished");
      source.close();
    });
    source.onerror = () => {
      if (source.readyState === EventSource.CLOSED) setStatus("error");
    };

    return () => {
      if (flushTimer !== undefined) window.clearTimeout(flushTimer);
      source.close();
    };
  }, [req]);

  return { meta, events, triggers, snapshot, momentum, overlays, trace, status, frames };
}
