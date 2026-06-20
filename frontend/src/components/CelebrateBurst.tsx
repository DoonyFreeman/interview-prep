import { motion, useReducedMotion } from "motion/react";

// A ring of little particles bursting outward — fired once on a perfect score.
const PARTICLES = Array.from({ length: 12 }, (_, i) => {
  const angle = (i / 12) * Math.PI * 2;
  const dist = 46 + (i % 3) * 10;
  return {
    x: Math.cos(angle) * dist,
    y: Math.sin(angle) * dist,
    color: ["bg-celebrate", "bg-accent", "bg-primary"][i % 3],
    delay: (i % 4) * 0.03,
  };
});

/**
 * A one-shot celebratory burst for "perfect result" moments. Renders nothing if
 * the user prefers reduced motion. The parent must be `relative`; the burst is
 * centered and `pointer-events-none` so it never blocks clicks.
 */
export function CelebrateBurst() {
  const reduce = useReducedMotion();
  if (reduce) return null;

  return (
    <div
      className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center"
      aria-hidden
    >
      {PARTICLES.map((p, i) => (
        <motion.span
          key={i}
          className={`absolute h-1.5 w-1.5 rounded-full ${p.color}`}
          initial={{ opacity: 0, scale: 0, x: 0, y: 0 }}
          animate={{
            opacity: [0, 1, 1, 0],
            scale: [0, 1, 1, 0.6],
            x: p.x,
            y: p.y,
          }}
          transition={{
            duration: 0.9,
            delay: p.delay,
            ease: [0.22, 1, 0.36, 1],
            times: [0, 0.2, 0.7, 1],
          }}
        />
      ))}
    </div>
  );
}
