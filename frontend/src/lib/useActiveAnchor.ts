import { useEffect, useState } from "react";

/**
 * Tracks which heading is currently in view, for highlighting a table of
 * contents. Observes the elements with the given ids and returns the topmost
 * one inside the reading band (just under the sticky header). Re-runs when the
 * set of ids changes (e.g. a different lesson loads).
 */
export function useActiveAnchor(ids: string[]): string | null {
  const [active, setActive] = useState<string | null>(ids[0] ?? null);
  const key = ids.join("|");

  useEffect(() => {
    if (ids.length === 0) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActive(visible[0].target.id);
      },
      { rootMargin: "-84px 0px -68% 0px", threshold: 0 },
    );
    const els = ids
      .map((id) => document.getElementById(id))
      .filter((el): el is HTMLElement => el != null);
    els.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return active;
}
