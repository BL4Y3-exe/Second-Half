import { tr } from "../i18n";
import { NOTES } from "../notes";
import type { Lang, Meta, Snapshot } from "../types";
import type { Status } from "../useLiveMatch";

const TALLY = { connecting: "connecting", live: "live", finished: "ft", error: "offline" } as const;

export function ScoreBug({
  meta,
  snapshot,
  clock,
  status,
  lang,
}: {
  meta: Meta;
  snapshot: Snapshot | null;
  clock: string;
  status: Status;
  lang: Lang;
}) {
  const { HOME: home, AWAY: away } = meta.teams;
  const score = snapshot?.score ?? { HOME: 0, AWAY: 0 };
  return (
    <div className="scorebug">
      <span className="chip" style={{ background: home.colors[0] }} aria-hidden="true" />
      <span className="abbr" title={home.name}>
        {home.short}
      </span>
      <span className="score">
        {score.HOME}
        <span className="dash">-</span>
        {score.AWAY}
      </span>
      <span className="abbr" title={away.name}>
        {away.short}
      </span>
      <span className="chip" style={{ background: away.colors[0] }} aria-hidden="true" />
      <span className="clock">{clock}</span>
      <span className={`tally ${status}`} data-note={NOTES.live[status]}>
        {tr(lang, TALLY[status])}
      </span>
    </div>
  );
}
