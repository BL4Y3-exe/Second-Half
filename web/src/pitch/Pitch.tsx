import { useEffect, useRef, useState } from "react";
import type { FrameBuffer } from "../useLiveMatch";
import type { Lang, Meta, Telestrator as Drawing, XY } from "../types";
import { PlayoutClock, sampleAt } from "./playback";
import { HalfSpace, halfSpaceNow, LaneLines } from "./Lanes";
import { PressLines, pressNow } from "./PressLines";
import { TeamShapes } from "./TeamShapes";
import { Telestrator, TelestratorDefs } from "./Telestrator";

const L = 105;
const W = 68;
const M = 3; // margin around the pitch, metres

export interface Replay {
  drawing: Drawing;
  startedAt: number; // performance.now()
  duration_s: number; // viewing seconds the overlay is up
}

export interface Pin {
  player: string;
  title: string;
  value: string;
}

interface Props {
  meta: Meta;
  frames: React.RefObject<FrameBuffer>;
  slots: { HOME: string[]; AWAY: string[] };
  replay?: Replay | null;
  pin?: Pin | null;
  paused?: boolean; // hold the picture still
  shapes?: boolean; // draw the analyst's team shapes and counter-presses
  lang?: Lang;
}

interface Drawn {
  players: XY[];
  ball: XY;
  owner: string | null;
  replayAt: number | null; // match seconds being replayed, or null when live
  t: number; // match seconds being drawn
}

const REPLAY_SHARE = 0.75; // part of the overlay's time spent replaying; the rest holds the final picture

/**
 * 2D pitch. Reads frames from a ref and plays them back smoothly every animation frame. While a Telestrator item
 * is on air it replays the move from recent frames and draws over it. Paused, it holds the picture.
 */
export function Pitch({ meta, frames, slots, replay = null, pin = null, paused = false, shapes = false, lang = "en" }: Props) {
  const [drawn, setDrawn] = useState<Drawn | null>(null);
  const [hover, setHover] = useState<number | null>(null);
  const raf = useRef(0);
  const clock = useRef(new PlayoutClock());
  const live = useRef({ replay, paused, speed: meta.speed });
  live.current = { replay, paused, speed: meta.speed };

  useEffect(() => {
    const loop = () => {
      const buf = frames.current;
      const now = performance.now();
      const { replay: rp, paused: hold, speed } = live.current;
      raf.current = requestAnimationFrame(loop);
      if (hold) {
        clock.current.hold(now);
        return;
      }
      if (buf && rp) {
        const [w0, w1] = rp.drawing.window;
        const progress = Math.min(1, (now - rp.startedAt) / (rp.duration_s * 1000 * REPLAY_SHARE));
        const at = w0 + (w1 - w0) * progress;
        const shot = sampleAt(buf.history, at);
        if (shot) {
          setDrawn({ ...shot, replayAt: at, t: at });
          return;
        }
      }
      if (!buf?.cur) return;
      const t = clock.current.tick(buf.history, now, speed);
      const shot = t === null ? null : sampleAt(buf.history, t);
      setDrawn(
        shot && t !== null
          ? { ...shot, replayAt: null, t }
          : { players: buf.cur.p, ball: buf.cur.b, owner: buf.cur.o, replayAt: null, t: buf.cur.t },
      );
    };
    raf.current = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf.current);
  }, [frames]);

  const byId = new Map(
    (["HOME", "AWAY"] as const).flatMap((s) => meta.teams[s].players.map((p) => [p.id, p] as const)),
  );
  const ids = [...slots.HOME, ...slots.AWAY];
  const positions = new Map<string, XY>();
  if (drawn) ids.forEach((id, i) => positions.set(id, drawn.players[i]));
  const replaying = drawn?.replayAt != null;
  const pinned = pin ? positions.get(pin.player) : undefined;
  const press =
    shapes && drawn && !replaying && frames.current
      ? pressNow(frames.current.presses, drawn.t, meta.speed, drawn.players, ids, drawn.ball, drawn.owner)
      : null;
  const pressing = press !== null && (press.chase !== null || press.tag !== null);
  const space =
    shapes && drawn && !replaying && frames.current
      ? halfSpaceNow(frames.current.spaces, drawn.t, meta.speed, frames.current.history)
      : null;

  return (
    <svg
      className={`pitch${replaying ? " replaying" : ""}`}
      viewBox={`${-M} ${-M} ${L + 2 * M} ${W + 2 * M}`}
      role="img"
      aria-label="Live pitch"
    >
      <PitchBase />
      {shapes && <LaneLines />}
      {space && <HalfSpace key={space.id} ball={space} meta={meta} lang={lang} />}
      {shapes && drawn && !replaying && (
        <TeamShapes
          meta={meta}
          players={drawn.players}
          ball={drawn.ball}
          owner={drawn.owner}
          ids={ids}
          lang={lang}
          support={!pressing && !space}
        />
      )}

      {drawn &&
        drawn.players.map(([x, y], i) => {
          const side = i < 11 ? "HOME" : "AWAY";
          const team = meta.teams[side];
          const id = ids[i];
          const player = byId.get(id);
          const keeper = i % 11 === 0;
          const fill = keeper ? (side === "HOME" ? "#f5c518" : "#9be15d") : team.colors[0];
          const text = keeper ? "#111" : team.colors[1];
          const onBall = drawn.owner === id;
          return (
            <g
              key={i}
              transform={`translate(${x} ${y})`}
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
              className="player"
            >
              {onBall && <circle r={2.1} className="on-ball" />}
              <circle r={1.35} fill={fill} stroke={text} strokeWidth={0.18} />
              <text y={0.5} fill={text} className="shirt">
                {player?.number ?? ""}
              </text>
              {hover === i && player && (
                <g className="tag" transform="translate(0 -2.6)">
                  <rect x={-player.name.length * 0.48 - 0.8} y={-1.6} width={player.name.length * 0.96 + 1.6} height={2.2} rx={0.4} />
                  <text y={0}>{player.name}</text>
                </g>
              )}
            </g>
          );
        })}
      {press && drawn && pressing && (
        <PressLines
          now={press}
          meta={meta}
          lang={lang}
          players={drawn.players}
          ids={ids}
          ball={drawn.ball}
          owner={drawn.owner}
        />
      )}
      {drawn && (
        <g transform={`translate(${drawn.ball[0]} ${drawn.ball[1]})`}>
          <circle r={0.75} className="ball" />
        </g>
      )}
      {replay && drawn && <Telestrator drawing={replay.drawing} at={drawn.replayAt} positions={positions} />}
      {pin && pinned && (
        <g className="pin" transform={`translate(${pinned[0]} ${pinned[1]})`}>
          <line y1={pinned[1] < 10 ? 1.6 : -1.6} y2={pinned[1] < 10 ? 3.4 : -3.4} />
          <g
            transform={`translate(${Math.min(L + M - 8, Math.max(8 - M, pinned[0])) - pinned[0]} ${
              pinned[1] < 10 ? 6.4 : -6.4
            })`}
          >
            <rect x={-8} y={-2.6} width={16} height={5.6} rx={0.6} />
            <text className="pin-title" y={-0.6}>
              {pin.title}
            </text>
            <text className="pin-value" y={2.1}>
              {pin.value}
            </text>
          </g>
        </g>
      )}
    </svg>
  );
}

/** The grass, the markings and the arrow heads: everything on the pitch that never moves. */
export function PitchBase() {
  return (
    <>
      <defs>
        <TelestratorDefs />
        <pattern id="stripes" width="10.5" height={W} patternUnits="userSpaceOnUse">
          <rect width="5.25" height={W} fill="var(--grass-a)" />
          <rect x="5.25" width="5.25" height={W} fill="var(--grass-b)" />
        </pattern>
      </defs>
      <rect x={-M} y={-M} width={L + 2 * M} height={W + 2 * M} fill="var(--grass-b)" />
      <rect x={0} y={0} width={L} height={W} fill="url(#stripes)" />
      <g className="lines">
        <rect x={0} y={0} width={L} height={W} />
        <line x1={L / 2} y1={0} x2={L / 2} y2={W} />
        <circle cx={L / 2} cy={W / 2} r={9.15} />
        <circle cx={L / 2} cy={W / 2} r={0.4} className="spot" />
        {[0, 1].map((end) => {
          const x = end === 0 ? 0 : L;
          const dir = end === 0 ? 1 : -1;
          return (
            <g key={end}>
              <rect x={end === 0 ? 0 : L - 16.5} y={W / 2 - 20.16} width={16.5} height={40.32} />
              <rect x={end === 0 ? 0 : L - 5.5} y={W / 2 - 9.16} width={5.5} height={18.32} />
              <circle cx={x + dir * 11} cy={W / 2} r={0.4} className="spot" />
              <path
                d={`M ${x + dir * 16.5} ${W / 2 - 7.3} A 9.15 9.15 0 0 ${end === 0 ? 1 : 0} ${x + dir * 16.5} ${W / 2 + 7.3}`}
              />
              <rect x={end === 0 ? -2 : L} y={W / 2 - 3.66} width={2} height={7.32} className="goal" />
            </g>
          );
        })}
      </g>
    </>
  );
}

/** A still picture of a move: the pitch and the Telestrator's arrows, without the players. */
export function MovePitch({ drawing }: { drawing: Drawing }) {
  return (
    <svg className="pitch move" viewBox={`${-M} ${-M} ${L + 2 * M} ${W + 2 * M}`} role="img" aria-label="The move">
      <PitchBase />
      <Telestrator drawing={drawing} at={null} positions={new Map()} />
    </svg>
  );
}
