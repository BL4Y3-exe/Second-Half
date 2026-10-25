import { AGENT_NOTES } from "../notes";
import { AGENTS, duration, mismatches, outcome, type Moment } from "../trace";
import type { Meta, TraceStep } from "../types";

const ROLES: Record<string, string> = {
  spotter: "watches the stats",
  analyst: "match tools",
  storyteller: "writes",
  fact_checker: "plain code",
  director: "runs the screen",
  persona: "each viewer",
  recap: "summaries",
  test: "demo switch",
};

function heading(step: TraceStep): string {
  const { agent, action, detail } = step;
  if (agent === "analyst") return `${action} · ${step.summary}`;
  if (agent === "fact_checker" && step.status === "rejected") return `${action} · sent back`;
  if (agent === "fact_checker") {
    const n = (detail.checked as string[] | undefined)?.length;
    return n ? `${action} · ${n} of ${n}` : action;
  }
  if (agent === "spotter" && typeof detail.priority === "number") return `${action} · priority ${detail.priority}`;
  return action;
}

/** The draft with the numbers the Fact-checker went on to reject marked. */
function Draft({ text, wrong }: { text: string; wrong: string[] }) {
  if (!wrong.length) return <q>{text}</q>;
  const pattern = new RegExp(`(${wrong.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "g");
  return (
    <q>
      {text.split(pattern).map((part, i) =>
        wrong.includes(part) ? (
          <mark key={i} className="bad">
            {part}
          </mark>
        ) : (
          part
        ),
      )}
    </q>
  );
}

function Body({ step, next }: { step: TraceStep; next: TraceStep[] }) {
  const { agent, status, detail, summary } = step;
  if (agent === "analyst") {
    const calls = (detail.tool_calls as string[] | undefined) ?? [];
    return (
      <div className="chips">
        {calls.map((c, i) => (
          <span key={i} className="tool">
            {c}
          </span>
        ))}
      </div>
    );
  }
  if (agent === "storyteller" && status === "ok") {
    const verdict = next.find((s) => s.agent === "fact_checker" || s.agent === "storyteller");
    const wrong = verdict?.status === "rejected" ? mismatches(verdict).map(([said]) => said) : [];
    return <Draft text={summary} wrong={wrong} />;
  }
  if (agent === "test") {
    return (
      <p>
        Changed <mark className="ok">{String(detail.was)}</mark> to <mark className="bad">{String(detail.now)}</mark> in
        the draft, to show the Fact-checker at work.
      </p>
    );
  }
  if (agent === "fact_checker" && status === "rejected") {
    const pairs = mismatches(step);
    if (!pairs.length) return <p>{summary}</p>;
    return (
      <p>
        {pairs.map(([said, real], i) => (
          <span key={i} className="mismatch">
            Says <mark className="bad">{said}</mark>, the match data has <mark className="ok">{real}</mark>
          </span>
        ))}
      </p>
    );
  }
  if (agent === "fact_checker") {
    const checked = (detail.checked as string[] | undefined) ?? [];
    return checked.length ? (
      <div className="chips">
        {checked.map((c, i) => (
          <span key={i} className="fact">
            {c}
          </span>
        ))}
      </div>
    ) : (
      <p>{summary}</p>
    );
  }
  return <p>{summary}</p>;
}

/** One desk per handoff on the picked moment, lit by how it went. */
export function AgentDesks({ meta, moment }: { meta: Meta; moment: Moment | null }) {
  if (!moment) {
    return (
      <section className="panel desks">
        <h2>Agent desks</h2>
        <p className="muted">The Spotter hasn't flagged anything yet.</p>
      </section>
    );
  }
  const o = outcome(moment);
  const team = moment.overlay?.team ?? moment.trigger?.team;
  return (
    <section className="panel desks" aria-label="How the agents handled this moment">
      <div className="desk-moment">
        <span className="kind" style={{ background: team ? meta.teams[team].colors[0] : undefined }}>
          {moment.clock}
        </span>
        <b>{moment.overlay?.headline ?? moment.steps[0].summary}</b>
        <span className={`badge ${o.cls}`}>{o.text}</span>
      </div>
      <ol className="desk-list">
        {moment.steps.map((s, i) => (
          <li key={s.id} className={`desk ${s.status}`}>
            <span className="lamp" aria-hidden="true" />
            <span className="who">
              <b data-note={AGENT_NOTES[s.agent]}>{AGENTS[s.agent] ?? s.agent}</b>
              <span>{ROLES[s.agent] ?? ""}</span>
            </span>
            <div className="out">
              <span className="act">{heading(s)}</span>
              <Body step={s} next={moment.steps.slice(i + 1)} />
            </div>
            <span className="ms">{s.ms > 0 ? duration(s.ms) : ""}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}
