import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useTheme } from "../theme/ThemeContext";
import { IconMoon, IconSun } from "./icons";

/**
 * Sun ↔ moon, swapped with a quarter-turn. The outgoing icon rotates and
 * shrinks away while the incoming one turns in from the other side, so the
 * toggle reads as one object flipping rather than two icons blinking.
 * Under reduced motion it degrades to a plain crossfade.
 */
export function ThemeToggle() {
  const { theme, toggle } = useTheme();
  const reduce = useReducedMotion();
  const dark = theme === "dark";

  return (
    <button
      onClick={toggle}
      title={dark ? "Light" : "Dark"}
      aria-label="Toggle theme"
      className="icon-chip relative inline-flex items-center justify-center overflow-hidden hover:!text-accent"
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={theme}
          className="absolute inline-flex"
          initial={reduce ? { opacity: 0 } : { opacity: 0, rotate: -90, scale: 0.4 }}
          animate={reduce ? { opacity: 1 } : { opacity: 1, rotate: 0, scale: 1 }}
          exit={reduce ? { opacity: 0 } : { opacity: 0, rotate: 90, scale: 0.4 }}
          transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
        >
          {dark ? (
            <IconSun className="h-[17px] w-[17px]" />
          ) : (
            <IconMoon className="h-[17px] w-[17px]" />
          )}
        </motion.span>
      </AnimatePresence>
    </button>
  );
}
