import type { Transition, Variants } from "motion/react";

/**
 * Shared motion vocabulary. Deliberately *subtle* — this is a study app, the
 * UI should settle quickly and never pull the eye away from reading. Small
 * offsets (6–10px), short durations (0.15–0.28s), gentle easing. Everything
 * honours `prefers-reduced-motion` via the global CSS reset + Motion's own
 * `useReducedMotion`, so we keep distances tiny on purpose.
 */

const EASE_OUT: Transition["ease"] = [0.22, 1, 0.36, 1];

/** Page/section content rising a few px into place. */
export const fadeInUp: Variants = {
  hidden: { opacity: 0, y: 8 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.24, ease: EASE_OUT },
  },
};

/** Plain crossfade — for swapping between two states in the same slot. */
export const fade: Variants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { duration: 0.18 } },
  exit: { opacity: 0, transition: { duration: 0.12 } },
};

/** Container that reveals its children one after another. */
export const staggerContainer: Variants = {
  hidden: {},
  show: {
    transition: { staggerChildren: 0.05, delayChildren: 0.04 },
  },
};

/** A small "pop" for reward moments (score gauge, badges). One-shot only. */
export const pop: Variants = {
  hidden: { opacity: 0, scale: 0.92 },
  show: {
    opacity: 1,
    scale: 1,
    transition: { type: "spring", stiffness: 420, damping: 26 },
  },
};

/** Route transition — barely-there crossfade with a hair of vertical drift. */
export const routeTransition: Variants = {
  hidden: { opacity: 0, y: 6 },
  show: { opacity: 1, y: 0, transition: { duration: 0.2, ease: EASE_OUT } },
  exit: { opacity: 0, y: -4, transition: { duration: 0.12 } },
};
