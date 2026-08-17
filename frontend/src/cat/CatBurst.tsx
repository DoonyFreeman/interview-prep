import { motion } from "motion/react";
import {
  IconHeart,
  IconNote,
  IconPaw,
  IconSparkles,
  IconStar,
} from "../components/icons";

const SHAPES = [IconHeart, IconStar, IconPaw, IconNote, IconSparkles];

// Palette pulled from the design tokens, so the burst stays on-brand in both
// themes instead of shipping its own colours.
const TONES = [
  "text-danger",
  "text-accent",
  "text-primary",
  "text-celebrate",
  "text-accent",
];

const COUNT = 7;

/**
 * The particles for one tap. Derived entirely from `seed` (the tap counter) —
 * no `Math.random()`, so a re-render mid-flight can't reshuffle a burst that's
 * already on screen.
 */
function particles(seed: number) {
  return Array.from({ length: COUNT }, (_, i) => {
    // Fan the particles across a ~150° arc centred on "straight up".
    const spread = ((i + 0.5) / COUNT - 0.5) * 2.6;
    const angle = -Math.PI / 2 + spread;
    const dist = 38 + ((seed * 7 + i * 13) % 22);
    return {
      x: Math.cos(angle) * dist,
      y: Math.sin(angle) * dist,
      rotate: ((seed * 11 + i * 29) % 70) - 35,
      scale: 0.72 + ((seed * 3 + i * 5) % 6) / 12,
      delay: i * 0.03,
      Shape: SHAPES[(seed + i) % SHAPES.length],
      tone: TONES[(seed * 2 + i) % TONES.length],
    };
  });
}

/**
 * A one-shot spray of little vector tokens (hearts, stars, paws, notes) when
 * the cat is tapped — replaces the single floating emoji, which rendered in the
 * platform emoji font and so couldn't be tinted, sized or eased consistently.
 *
 * The parent must establish a positioning context; particles fly out from its
 * centre and never take pointer events. Renders nothing under reduced motion.
 */
export function CatBurst({ seed, reduced }: { seed: number; reduced: boolean }) {
  if (reduced) return null;

  return (
    <div
      className="pointer-events-none absolute left-1/2 top-1/2 z-10 h-0 w-0"
      aria-hidden
    >
      {particles(seed).map((p, i) => (
        <motion.span
          key={i}
          className={`absolute ${p.tone}`}
          initial={{ opacity: 0, x: 0, y: 0, scale: 0, rotate: 0 }}
          animate={{
            opacity: [0, 1, 1, 0],
            x: p.x,
            y: p.y,
            scale: [0, p.scale * 1.15, p.scale, p.scale * 0.85],
            rotate: p.rotate,
          }}
          transition={{
            duration: 0.95,
            delay: p.delay,
            ease: [0.22, 1, 0.36, 1],
            times: [0, 0.22, 0.62, 1],
          }}
        >
          <p.Shape className="h-3.5 w-3.5" />
        </motion.span>
      ))}
    </div>
  );
}
