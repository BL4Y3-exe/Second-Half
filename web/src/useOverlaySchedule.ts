import { useEffect, useRef, useState } from "react";
import type { Overlay, Side } from "./types";
import type { FrameBuffer } from "./useLiveMatch";

export interface ScheduleOptions {
  speed: number; // match seconds per viewing second
  favourite: Side | null; // hide minor items about the other club
}

export interface OnAir {
  overlay: Overlay;
  startedAt: number; // performance.now() when it went on screen
}

/**
 * Decides which overlay is on screen in each slot right now. An item becomes due when the match
 * clock passes `show_at` and stays up for `duration_s` seconds of viewing time. The Director has
 * already spaced items out; if two still meet, a more important one (lower priority number)
 * takes the slot and the other waits, unless it has gone stale.
 */
const MIN_AIRTIME_MS = 2500;

/** Whether a newly due item should take its slot from the one on screen. */
function replaces(next: Overlay, current: OnAir, now: number): boolean {
  if (next.priority < current.overlay.priority) return true;
  if (next.kind === "goal" && current.overlay.kind !== "goal") return true;
  // Two must-show items: the newer one goes on once the first has had a moment on screen.
  return next.priority === 1 && current.overlay.priority === 1 && now - current.startedAt > MIN_AIRTIME_MS;
}

export function useOverlaySchedule(
  overlays: Overlay[],
  frames: React.RefObject<FrameBuffer>,
  opts: ScheduleOptions,
): Record<string, OnAir> {
  const [active, setActive] = useState<Record<string, OnAir>>({});
  const showing = useRef<Record<string, OnAir>>({});
  const done = useRef(new Set<string>());

  const fresh = overlays.length === 0;
  useEffect(() => {
    if (!fresh) return;
    showing.current = {};
    done.current.clear();
    setActive({});
  }, [fresh]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      const t = frames.current?.cur?.t ?? 0;
      const now = performance.now();
      const on = showing.current;
      let changed = false;

      for (const [slot, item] of Object.entries(on)) {
        if (now - item.startedAt > item.overlay.duration_s * 1000) {
          done.current.add(item.overlay.id);
          delete on[slot];
          changed = true;
        }
      }

      const due = overlays
        .filter((ov) => !done.current.has(ov.id) && ov.show_at <= t && on[ov.slot]?.overlay.id !== ov.id)
        .sort((a, b) => a.show_at - b.show_at);
      for (const ov of due) {
        const hidden = opts.favourite && ov.team && ov.team !== opts.favourite && ov.priority > 1;
        const stale = t - ov.show_at > (ov.duration_s + 15) * opts.speed;
        if (hidden || stale) {
          done.current.add(ov.id);
          continue;
        }
        const current = on[ov.slot];
        if (current && !replaces(ov, current, now)) continue; // wait for the slot
        if (current) done.current.add(current.overlay.id);
        on[ov.slot] = { overlay: ov, startedAt: now };
        changed = true;
      }
      if (changed) setActive({ ...on });
    }, 150);
    return () => window.clearInterval(timer);
  }, [overlays, frames, opts.favourite, opts.speed]);

  return active;
}
