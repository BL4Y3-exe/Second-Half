import { useEffect, useRef, useState } from "react";
import type { Frame, MatchEvent, Meta, MomentumPoint, Overlay, Snapshot, TraceStep, Trigger } from "./types";

export interface MatchRequest {
  home: string;
  away: string;
  seed: number;
  speed: number;
  plant: boolean; // the demo switch: plant wrong numbers for the Fact-checker to catch
  run: number; // bump to restart
}

export interface FrameBuffer {
  prev: Frame | null;
  cur: Frame | null;
  arrivedAt: number; // performance.now() when `cur` arrived
  interval: number; // expected ms between frames
  history: Frame[]; // recent frames, for Telestrator replays
}

const HISTORY = 2400;
const emptyBuffer = (): FrameBuffer => ({ prev: null, cur: null, arrivedAt: 0, interval: 83, history: [] });

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
      const now = performance.now();
      if (buf.cur) buf.interval = Math.min(250, Math.max(30, now - buf.arrivedAt));
      buf.prev = buf.cur;
      buf.cur = f;
      buf.arrivedAt = now;
      buf.history.push(f);
      if (buf.history.length > HISTORY + 200) buf.history.splice(0, 200);
    });
    source.addEventListener("event", (e) => {
      const ev: MatchEvent = JSON.parse((e as MessageEvent).data);
      if (seenEvents.has(ev.id)) return; // a reconnect replays the latest events
      seenEvents.add(ev.id);
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
