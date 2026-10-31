import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import "./concept-link.css";

/** The anchor always navigates; the adjacent button only opens the definition. */
export function ConceptLink({ href, definition, children }: {
  href: string;
  definition: string;
  children?: ReactNode;
}) {
  const { i18n } = useTranslation();
  const russian = i18n.resolvedLanguage?.startsWith("ru") ?? true;
  const id = useId();
  const trigger = useRef<HTMLSpanElement>(null);
  const popup = useRef<HTMLSpanElement>(null);
  const closeTimer = useRef<ReturnType<typeof setTimeout>>();
  const [open, setOpen] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [position, setPosition] = useState<{ left: number; top: number }>();

  function cancelClose() {
    clearTimeout(closeTimer.current);
  }
  function close() {
    cancelClose();
    setOpen(false);
    setPinned(false);
    setPosition(undefined);
  }
  function leave() {
    if (!pinned && !trigger.current?.contains(document.activeElement)) {
      closeTimer.current = setTimeout(close, 150);
    }
  }
  function show() {
    cancelClose();
    setOpen(true);
  }

  useEffect(() => () => clearTimeout(closeTimer.current), []);
  useEffect(() => {
    if (!open) return;
    function place() {
      const rect = trigger.current?.getBoundingClientRect();
      const tip = popup.current;
      if (rect && tip) {
        const gutter = 16;
        const below = rect.bottom + 8;
        const top = below + tip.offsetHeight <= window.innerHeight - gutter
          ? below : Math.max(gutter, rect.top - tip.offsetHeight - 8);
        setPosition({
          left: Math.max(gutter, Math.min(rect.left, window.innerWidth - tip.offsetWidth - gutter)),
          top,
        });
      }
    }
    place();
    function keydown(event: KeyboardEvent) {
      if (event.key === "Escape") close();
    }
    function outside(event: PointerEvent) {
      if (event.target instanceof Node && !trigger.current?.contains(event.target)
        && !popup.current?.contains(event.target)) close();
    }
    function scroll(event: Event) {
      // A long definition may need its own scrollbar on a short screen.
      if (event.target instanceof Node && popup.current?.contains(event.target)) return;
      const rect = trigger.current?.getBoundingClientRect();
      // Focusing an off-screen link scrolls it into view. Keep its definition
      // open and attached to the link while keyboard focus remains visible.
      if (trigger.current?.contains(document.activeElement) && rect
        && rect.bottom > 0 && rect.top < window.innerHeight) {
        place();
        return;
      }
      close();
    }
    document.addEventListener("keydown", keydown);
    document.addEventListener("pointerdown", outside);
    window.addEventListener("resize", close);
    window.addEventListener("scroll", scroll, true);
    return () => {
      document.removeEventListener("keydown", keydown);
      document.removeEventListener("pointerdown", outside);
      window.removeEventListener("resize", close);
      window.removeEventListener("scroll", scroll, true);
    };
  }, [open]);

  return (
    <span
      className="concept-link"
      ref={trigger}
      onPointerEnter={(event) => { if (event.pointerType === "mouse") show(); }}
      onPointerLeave={leave}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) close();
      }}
    >
      <a href={href} onFocus={show} onClick={close} aria-describedby={open ? id : undefined}>
        {children}
      </a>
      <button
        className="concept-link-toggle"
        type="button"
        aria-label={russian ? "Показать определение понятия" : "Show concept definition"}
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        aria-describedby={open ? id : undefined}
        onClick={() => {
          if (pinned) close();
          else { show(); setPinned(true); }
        }}
      >
        <span aria-hidden="true">i</span>
      </button>
      {open && createPortal(
        <span
          id={id}
          ref={popup}
          role="tooltip"
          className="concept-link-preview"
          style={{ left: position?.left ?? 16, top: position?.top ?? 16, visibility: position ? "visible" : "hidden" }}
          onPointerEnter={cancelClose}
          onPointerLeave={leave}
        >
          {definition.trim()}
        </span>,
        document.body,
      )}
    </span>
  );
}
