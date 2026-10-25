import { MODES } from "../i18n";
import { NOTES } from "../notes";
import { MovePitch } from "../pitch/Pitch";
import { outcome, type Moment } from "../trace";
import type { Lang, Meta } from "../types";
import type { ViewerSettings } from "../Viewer";

interface Props {
  meta: Meta;
  moment: Moment | null;
  you: ViewerSettings;
  guest: ViewerSettings | null;
  following: boolean;
  onFollow: () => void;
  onStep: (dir: -1 | 1) => void;
}

/** One moment up close: the move as the Telestrator drew it, and every version the viewers could get. */
export function MomentCard({ meta, moment, you, guest, following, onFollow, onStep }: Props) {
  const ov = moment?.overlay;
  const langs: Lang[] = meta.languages ?? ["en", "es"];
  const team = ov?.team ?? moment?.trigger?.team;
  return (
    <section className="panel moment-card" aria-label="The picked moment">
      <div className="mc-head">
        {moment && (
          <span className="kind" style={{ background: team ? meta.teams[team].colors[0] : undefined }}>
            {moment.clock}
          </span>
        )}
        <h2>{ov?.headline ?? moment?.label ?? "No moments yet"}</h2>
        {moment && <span className={`badge ${outcome(moment).cls}`}>{outcome(moment).text}</span>}
        <div className="mc-nav">
          <button type="button" aria-label="Earlier moment" onClick={() => onStep(-1)} disabled={!moment}>
            ‹
          </button>
          <button type="button" aria-label="Later moment" onClick={() => onStep(1)} disabled={!moment}>
            ›
          </button>
          <button
            type="button"
            className={`follow${following ? " on" : ""}`}
            aria-pressed={following}
            onClick={onFollow}
            data-note={NOTES.follow}
          >
            {following ? "Following live" : "Follow live"}
          </button>
        </div>
      </div>
      {moment && !ov && <p className="muted mc-why">{moment.steps[moment.steps.length - 1].summary}</p>}
      {ov && (
        <div className={`mc-body${ov.telestrator ? "" : " no-move"}`}>
          {ov.telestrator && (
            <figure className="mc-move">
              <MovePitch drawing={ov.telestrator} />
              <figcaption className="sr-only">The move, as the Telestrator drew it</figcaption>
            </figure>
          )}
          <div className="ways">
            <h3 data-note={NOTES.versions}>
              The same moment, {langs.length * MODES.length} ways
            </h3>
            <div className="ways-grid">
              {langs.flatMap((lang) =>
                MODES.map((m) => {
                  const mine = you.mode === m.id && you.lang === lang;
                  const theirs = guest?.mode === m.id && guest.lang === lang;
                  return (
                    <div key={`${lang}-${m.id}`} className={`way${mine ? " mine" : ""}`} lang={lang}>
                      <div className="way-who">
                        <span className="lang">{lang.toUpperCase()}</span>
                        {m.label[lang]}
                        {mine && <span className="tag">You</span>}
                        {theirs && <span className="tag guest">Guest</span>}
                      </div>
                      <p>{ov.text?.[lang]?.[m.id] ?? ov.story}</p>
                    </div>
                  );
                }),
              )}
            </div>
            <p className="mc-story">
              <span className="lbl">{ov.fallback ? "Plain stat card" : "Approved story"}</span>
              {ov.story}
            </p>
          </div>
        </div>
      )}
    </section>
  );
}
