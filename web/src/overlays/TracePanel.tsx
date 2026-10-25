import { AGENT_NOTES, NOTES, TOTAL_NOTES } from "../notes";
import type { Meta, TraceStep } from "../types";

const AGENTS: Record<string, string> = {
  spotter: "Spotter",
  analyst: "Analyst",
  storyteller: "Storyteller",
  fact_checker: "Fact-checker",
  director: "Director",
  persona: "Persona",
  recap: "Recap",
  test: "Demo test",
};

interface Moment {
  id: string;
  clock: string;
  label: string;
  steps: TraceStep[];
}

function group(trace: TraceStep[]): Moment[] {
  const byId = new Map<string, Moment>();
  for (const step of trace) {
    let m = byId.get(step.moment_id);
    if (!m) {
      m = { id: step.moment_id, clock: step.clock, label: step.summary, steps: [] };
      byId.set(step.moment_id, m);
    }
    m.steps.push(step);
  }
  return [...byId.values()].reverse();
}

const caught = (s: TraceStep) => s.agent === "fact_checker" && s.status === "rejected";

function duration(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${Math.round(ms)} ms`;
}

function outcome(m: Moment): { text: string; cls: string } {
  const last = m.steps[m.steps.length - 1];
  if (m.steps[0].action === "passed over") return { text: "passed over", cls: "skipped" };
  const dropped = m.steps.find((s) => s.action === "dropped");
  if (dropped) return { text: dropped.summary.startsWith("too late") ? "too late" : "held back", cls: "skipped" };
  if (m.steps.some((s) => s.status === "fallback")) return { text: "stat card", cls: "fallback" };
  const recapScripted = m.steps.some((s) => s.agent === "recap" && s.action === "no answer");
  if (recapScripted) return { text: "scripted line", cls: "fallback" };
  if (m.steps.some((s) => s.agent === "test")) return { text: "planted & caught", cls: "rejected" };
  if (m.steps.some(caught)) return { text: "caught & fixed", cls: "rejected" };
  if (last.agent === "persona" || last.action === "scheduled") return { text: "on air", cls: "ok" };
  return { text: "working…", cls: "pending" };
}

/** Every handoff between the agents, newest moment first, so judges can watch the team think. */
export function TracePanel({ meta, trace }: { meta: Meta; trace: TraceStep[] }) {
  const moments = group(trace);
  const count = (pred: (s: TraceStep) => boolean) => trace.filter(pred).length;
  const firstTime = moments.filter((m) => m.steps.find((s) => s.agent === "fact_checker")?.status === "ok").length;
  const totals: [string, number, string][] = [
    ["moments", count((s) => s.action === "flagged"), ""],
    ["approved first time", firstTime, "ok"],
    ["wrong numbers caught", count(caught), "rejected"],
    ["stat-card fallbacks", count((s) => s.status === "fallback"), "fallback"],
    ["held back", count((s) => s.status === "skipped"), "skipped"],
  ];
  const planted = count((s) => s.status === "planted");
  if (planted > 0) totals.push(["planted by the demo switch", planted, "planted"]);
  return (
    <div className="panel trace">
      <h3>
        Agent trace
        <span className="model" data-note={NOTES.model}>
          model: {meta.model ?? "mock"}
        </span>
      </h3>
      <div className="trace-totals">
        {totals.map(([label, n, cls]) => (
          <span key={label} className={cls} data-note={TOTAL_NOTES[label]}>
            <b>{n}</b> {label}
          </span>
        ))}
      </div>
      {moments.length === 0 && <p className="muted">The Spotter hasn't flagged anything yet.</p>}
      <ol>
        {moments.slice(0, 25).map((m) => {
          const o = outcome(m);
          return (
            <li key={m.id} className="moment">
              <div className="moment-head">
                <span className="t">{m.clock}</span>
                <span className="label">{m.label}</span>
                <span className={`badge ${o.cls}`}>{o.text}</span>
              </div>
              <ol className="steps">
                {m.steps.slice(1).map((s) => (
                  <li key={s.id} className={`step ${s.status}`}>
                    <span className={`agent ${s.agent}`} data-note={AGENT_NOTES[s.agent]}>
                      {AGENTS[s.agent] ?? s.agent}
                    </span>
                    <span className="action">{s.action}</span>
                    <span className="summary">{s.summary}</span>
                    {s.ms >= 1 && <span className="ms">{duration(s.ms)}</span>}
                  </li>
                ))}
              </ol>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
