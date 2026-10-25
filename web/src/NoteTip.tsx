import { useEffect, useRef, useState } from "react";

interface Shown {
  text: string;
  x: number;
  y: number;
  below: boolean;
}

const HOVER_DELAY_MS = 250;
const TOUCH_SHOW_MS = 3500;
const HALF_WIDTH = 150; // half the tip's max width, to keep it on screen

const noteOf = (el: EventTarget | null) => (el instanceof Element ? el.closest<HTMLElement>("[data-note]") : null);

/** One tooltip for the whole page: anything with a `data-note` shows its note on hover, on keyboard focus,
 *  or, for plain labels on a touch screen, on tap. */
export function NoteTip() {
  const [shown, setShown] = useState<Shown | null>(null);
  const target = useRef<HTMLElement | null>(null);
  const timer = useRef(0);

  useEffect(() => {
    const hide = () => {
      window.clearTimeout(timer.current);
      target.current?.removeAttribute("aria-describedby");
      target.current = null;
      setShown(null);
    };
    const show = (el: HTMLElement) => {
      const r = el.getBoundingClientRect();
      const below = r.top < 110;
      el.setAttribute("aria-describedby", "note-tip");
      setShown({
        text: el.dataset.note ?? "",
        x: Math.min(Math.max(r.left + r.width / 2, HALF_WIDTH + 8), window.innerWidth - HALF_WIDTH - 8),
        y: below ? r.bottom + 8 : r.top - 8,
        below,
      });
    };
    const point = (el: HTMLElement | null, delay: number) => {
      if (el === target.current) return;
      hide();
      if (!el) return;
      target.current = el;
      timer.current = window.setTimeout(() => show(el), delay);
    };

    const onOver = (e: MouseEvent) => point(noteOf(e.target), HOVER_DELAY_MS);
    const onFocus = (e: FocusEvent) => {
      const el = noteOf(e.target);
      if (el && e.target instanceof Element && e.target.matches(":focus-visible")) point(el, 0);
    };
    const onTouch = (e: PointerEvent) => {
      if (e.pointerType !== "touch") return;
      const el = noteOf(e.target);
      // Buttons and fields do their job on tap; their notes show in the viewer bar or on keyboard focus.
      if (!el || (e.target instanceof Element && e.target.closest("button, select, input"))) return hide();
      point(el, 0);
      timer.current = window.setTimeout(hide, TOUCH_SHOW_MS);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && hide();

    document.addEventListener("mouseover", onOver);
    document.addEventListener("focusin", onFocus);
    document.addEventListener("focusout", hide);
    document.addEventListener("pointerdown", onTouch);
    document.addEventListener("keydown", onKey);
    window.addEventListener("scroll", hide, true);
    return () => {
      hide();
      document.removeEventListener("mouseover", onOver);
      document.removeEventListener("focusin", onFocus);
      document.removeEventListener("focusout", hide);
      document.removeEventListener("pointerdown", onTouch);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("scroll", hide, true);
    };
  }, []);

  return (
    <div
      id="note-tip"
      role="tooltip"
      className={`note-tip${shown ? " on" : ""}${shown?.below ? " below" : ""}`}
      style={shown ? { left: shown.x, top: shown.y } : undefined}
    >
      {shown?.text}
    </div>
  );
}
