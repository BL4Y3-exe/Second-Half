import { Fragment, useEffect, useRef } from "react";
import { tr } from "../i18n";
import { AGENT_NOTES, NOTES } from "../notes";
import { AGENTS, gist, mismatches } from "../trace";
import type { Lang, Overlay, TraceStep } from "../types";

const ICONS: Record<string, React.ReactNode> = {
  ok: <path d="M4 12l5 5L20 6" />,
  rejected: <path d="M6 6l12 12M18 6L6 18" />,
  redo: (
    <>
      <path d="M3 12a9 9 0 1 0 3-6.7" />
      <path d="M3 3v6h6" />
    </>
  ),
  planted: <path d="M12 4v10M12 19v1" />,
  skipped: <path d="M6 12h12" />,
};

function look(step: TraceStep): string {
  if (step.status === "rejected") return "rejected";
  if (step.status === "planted" || step.status === "fallback") return "planted";
  if (step.status === "retry" || step.action.startsWith("redrafted")) return "redo";
  if (step.status === "skipped") return "skipped";
  return "ok";
}

/** What the step did; a rejection shows each wrong number struck through, then the right one. */
function Gist({ step }: { step: TraceStep }) {
  const pairs = step.agent === "fact_checker" && step.status === "rejected" ? mismatches(step) : [];
  if (!pairs.length) return <span>{gist(step)}</span>;
  return (
    <span>
      {pairs.map(([said, real], i) => (
        <Fragment key={i}>
          {i > 0 && " · "}
          <s>{said}</s> {real}
        </Fragment>
      ))}
    </span>
  );
}

interface Props {
  overlay: Overlay | null;
  live: boolean; // the graphic is on screen now, rather than the last one that was
  steps: TraceStep[];
  lang: Lang;
  onTrace: () => void;
}

/** The relay of agents behind the graphic on screen, one hop per handoff. */
export function BehindStrip({ overlay, live, steps, lang, onTrace }: Props) {
  const title = live ? "Behind this graphic" : overlay ? "The last graphic" : "Agents";
  // On a narrow screen the relay scrolls; keep the catch (or else the latest hop) in view.
  const relay = useRef<HTMLOListElement>(null);
  useEffect(() => {
    const ol = relay.current;
    const hop = ol?.querySelector<HTMLElement>(".hop.rejected") ?? (ol?.lastElementChild as HTMLElement | null);
    if (ol && hop && ol.scrollWidth > ol.clientWidth) {
      ol.scrollLeft = hop.offsetLeft - (ol.clientWidth - hop.offsetWidth) / 2;
    }
  }, [overlay, steps.length]);
  return (
    <section className="behind" aria-label="How the agents made this graphic">
      <div className="behind-title">
        <span data-note={NOTES.behind}>{title}</span>
        {overlay && (
          <b>
            {overlay.clock} · {tr(lang, overlay.kind)}
          </b>
        )}
      </div>
      {overlay ? (
        <ol className="relay" ref={relay}>
          {steps.map((s) => {
            const kind = look(s);
            return (
              <li key={s.id} className={`hop ${kind}`}>
                <span className="dot" aria-hidden="true">
                  <svg viewBox="0 0 24 24">{ICONS[kind]}</svg>
                </span>
                <span className="hop-text">
                  <b data-note={AGENT_NOTES[s.agent]}>{AGENTS[s.agent] ?? s.agent}</b>
                  <Gist step={s} />
                </span>
              </li>
            );
          })}
        </ol>
      ) : (
        <p className="relay-empty">The Spotter is watching the match. The next graphic's story shows up here.</p>
      )}
      <button type="button" className="behind-more" onClick={onTrace}>
        Analysis
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M5 12h14M13 6l6 6-6 6" />
        </svg>
      </button>
    </section>
  );
}
