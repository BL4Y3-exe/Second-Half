import { useCallback, useMemo, useState } from "react";
import { NOTES } from "../notes";
import { EventFeed } from "../overlays/EventFeed";
import { StatsPanel } from "../overlays/StatsPanel";
import { groupMoments } from "../trace";
import type { MatchEvent, Meta, MomentumPoint, Overlay, Snapshot, TraceStep, Trigger } from "../types";
import type { FrameBuffer, Status } from "../useLiveMatch";
import { ViewerStage, type ViewerSettings } from "../Viewer";
import { AgentDesks } from "./AgentDesks";
import { MomentCard } from "./MomentCard";
import { MomentumWave } from "./MomentumWave";
import { Rundown } from "./Rundown";

interface Props {
  meta: Meta;
  frames: React.RefObject<FrameBuffer>;
  slots: { HOME: string[]; AWAY: string[] };
  events: MatchEvent[];
  triggers: Trigger[];
  overlays: Overlay[];
  trace: TraceStep[];
  momentum: MomentumPoint[];
  snapshot: Snapshot | null;
  secondHalfAt: number | null;
  clock: string;
  status: Status;
  you: ViewerSettings;
  guest: ViewerSettings | null;
  paused: boolean;
}

/**
 * The Analysis view: the gallery behind the broadcast. The whole match's momentum with every moment on it,
 * the programme picture, each agent's desk for the picked moment, every version of its story, the rundown,
 * the team numbers and the match feed.
 */
export function Analysis(props: Props) {
  const { meta, overlays, trace, triggers, snapshot, you, guest } = props;
  const moments = useMemo(() => groupMoments(trace, overlays, triggers), [trace, overlays, triggers]);
  const [picked, setPicked] = useState<string | null>(null);
  const [onAir, setOnAir] = useState<string | null>(null);
  const report = useCallback((ov: Overlay | null) => setOnAir(ov?.moment_id ?? null), []);

  // Following live, the picked moment is whatever is on air, or else the latest one that aired.
  const latest = [...moments].reverse().find((m) => m.overlay) ?? moments[moments.length - 1];
  const selectedId = picked ?? onAir ?? latest?.id ?? null;
  const selected = moments.find((m) => m.id === selectedId) ?? null;
  const pick = (id: string) => setPicked(id);
  const step = (dir: -1 | 1) => {
    const i = moments.findIndex((m) => m.id === selectedId);
    const next = moments[Math.min(moments.length - 1, Math.max(0, i + dir))];
    if (next) setPicked(next.id);
  };

  return (
    <div className="analysis">
      <section className="panel wave-panel">
        <div className="panel-head">
          <h2 data-note={NOTES.momentum}>How the match has swung</h2>
          <span className="muted">
            Momentum each minute. Pick any moment on the rail to see how the agents handled it.
          </span>
          <span className="legend">
            <span>
              <i style={{ background: meta.teams.HOME.colors[0] }} />
              {meta.teams.HOME.name} on top
            </span>
            <span>
              <i style={{ background: meta.teams.AWAY.colors[0] }} />
              {meta.teams.AWAY.name} on top
            </span>
          </span>
        </div>
        <MomentumWave
          meta={meta}
          points={props.momentum}
          now={snapshot?.t ?? 0}
          finished={props.status === "finished"}
          secondHalfAt={props.secondHalfAt}
          moments={moments}
          selected={selectedId}
          onSelect={pick}
        />
      </section>

      <div className="an-row">
        <section className="monitor" aria-label="Programme">
          <div className="mon-head">
            <span className="tag pgm">PGM</span>
            <span className="what" data-note={NOTES.program}>
              Programme · what <b>you</b> see
            </span>
          </div>
          <ViewerStage
            meta={meta}
            frames={props.frames}
            slots={props.slots}
            overlays={overlays}
            snapshot={snapshot}
            clock={props.clock}
            status={props.status}
            settings={you}
            onAir={report}
            paused={props.paused}
          />
        </section>
        <AgentDesks meta={meta} moment={selected} />
      </div>

      <MomentCard
        meta={meta}
        moment={selected}
        you={you}
        guest={guest}
        following={picked === null}
        onFollow={() => setPicked(null)}
        onStep={step}
      />

      <div className="an-row three">
        <StatsPanel meta={meta} snapshot={snapshot} />
        <Rundown meta={meta} moments={moments} trace={trace} selected={selectedId} onSelect={pick} />
        <EventFeed meta={meta} events={props.events} triggers={triggers} />
      </div>
    </div>
  );
}
