import type { Frame, XY } from "../types";

/**
 * Smooth playback of the frame stream. Frames arrive about 12 times a wall-clock second, but not evenly, and each
 * is about a match second after the last at 12x. Drawing straight lines from one to the next makes players dart: a
 * frame that comes late and one that comes early play its move in a third of the time. Instead the pitch runs its
 * own clock at match speed a few frames behind the newest one, and draws players along a curve through the frames
 * around it.
 */

const LAG_FRAMES = 3; // how far behind the newest frame the pitch plays (a quarter of a second), to ride out late frames
const SNAP_FRAMES = 8; // further off than this (a paused screen, a hidden tab), jump straight to live
const MAX_RUN = 11; // m/s: a player who moves faster between two frames was swapped in (a substitute), not running
const MAX_BALL = 36; // m/s: likewise the ball, put down for a restart

export interface Sample {
  players: XY[];
  ball: XY;
  owner: string | null;
}

/** Indices of the frames either side of match time `t` in the history, or null if the history does not cover it. */
export function around(history: Frame[], t: number): [number, number] | null {
  if (history.length < 2 || t < history[0].t || t > history[history.length - 1].t) return null;
  let lo = 0;
  let hi = history.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (history[mid].t <= t) lo = mid;
    else hi = mid;
  }
  return [lo, hi];
}

const lerp = (a: XY, b: XY, f: number): XY => [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f];
const jumped = (a: XY, b: XY, dt: number, limit: number) => Math.hypot(b[0] - a[0], b[1] - a[1]) > limit * Math.max(dt, 0.3);

/** A Catmull-Rom curve from p1 to p2: it passes through every frame without the corners of straight lines. */
function curve(p0: XY, p1: XY, p2: XY, p3: XY, f: number): XY {
  const f2 = f * f;
  const f3 = f2 * f;
  const at = (k: 0 | 1) =>
    0.5 *
    (2 * p1[k] +
      (p2[k] - p0[k]) * f +
      (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * f2 +
      (3 * p1[k] - p0[k] - 3 * p2[k] + p3[k]) * f3);
  return [at(0), at(1)];
}

/** Where everyone is at match time `t`, or null if the history does not cover it. */
export function sampleAt(history: Frame[], t: number): Sample | null {
  const pair = around(history, t);
  if (!pair) return null;
  const [lo, hi] = pair;
  const a = history[lo];
  const b = history[hi];
  // Do not glide across a jump (the half-time line-up): snap instead.
  if (a.period !== b.period) return { players: b.p, ball: b.b, owner: b.o };
  const dt = b.t - a.t;
  const f = dt > 0 ? Math.min(1, Math.max(0, (t - a.t) / dt)) : 1;
  const before = lo > 0 && history[lo - 1].period === a.period ? history[lo - 1] : a;
  const after = hi + 1 < history.length && history[hi + 1].period === b.period ? history[hi + 1] : b;
  const players = b.p.map((pb, i): XY => {
    const pa = a.p[i];
    if (jumped(pa, pb, dt, MAX_RUN)) return pb;
    const p0 = jumped(before.p[i], pa, a.t - before.t, MAX_RUN) ? pa : before.p[i];
    const p3 = jumped(pb, after.p[i], after.t - b.t, MAX_RUN) ? pb : after.p[i];
    return curve(p0, pa, pb, p3, f);
  });
  // The ball flies in straight lines, so it keeps them.
  const ball = jumped(a.b, b.b, dt, MAX_BALL) ? b.b : lerp(a.b, b.b, f);
  return { players, ball, owner: f < 0.5 ? a.o : b.o };
}

/** The pitch's own match clock: runs at match speed and eases towards a few frames behind the newest one. */
export class PlayoutClock {
  private t = -1;
  private wall = 0;

  /** Match time to draw at wall time `now` (ms), given the frames so far and the match speed. */
  tick(history: Frame[], now: number, speed: number): number | null {
    const newest = history[history.length - 1];
    if (!newest) return null;
    const step = history.length > 1 ? Math.max(0.1, newest.t - history[history.length - 2].t) : 1;
    const target = newest.t - LAG_FRAMES * step;
    const dt = this.wall ? Math.min(0.25, (now - this.wall) / 1000) : 0;
    this.wall = now;
    if (this.t < 0 || Math.abs(target - this.t) > SNAP_FRAMES * step) {
      this.t = target;
    } else {
      this.t += dt * speed;
      this.t += (target - this.t) * Math.min(1, dt); // drift back towards the target over about a second
    }
    this.t = Math.max(history[0].t, Math.min(newest.t, this.t));
    return this.t;
  }

  /** Called while the screen is paused, so that playing again jumps to live rather than catching up. */
  hold(now: number) {
    this.wall = now;
    this.t = -1;
  }
}
