import { useEffect } from "react";
import {
  animate,
  motion,
  useMotionValue,
  useReducedMotion,
  useTransform,
} from "motion/react";

function colorFor(score: number): string {
  if (score >= 80) return "var(--color-success)";
  if (score >= 40) return "var(--color-warn)";
  return "var(--color-danger)";
}

export function ScoreGauge({ score, size = 88 }: { score: number; size?: number }) {
  const reduce = useReducedMotion();
  const stroke = 8;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const clamped = Math.max(0, Math.min(100, score));
  const color = colorFor(clamped);
  const strong = clamped >= 80;

  // Count the number up and sweep the ring from empty to the final value.
  const value = useMotionValue(reduce ? clamped : 0);
  const rounded = useTransform(value, (v) => Math.round(v));
  const offset = useTransform(value, (v) => c * (1 - v / 100));

  useEffect(() => {
    if (reduce) {
      value.set(clamped);
      return;
    }
    const controls = animate(value, clamped, { duration: 0.7, ease: "easeOut" });
    return () => controls.stop();
  }, [clamped, reduce, value]);

  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ type: "spring", stiffness: 420, damping: 24 }}
      className="relative shrink-0"
      style={{
        width: size,
        height: size,
        filter: strong
          ? "drop-shadow(0 0 10px color-mix(in oklab, var(--color-success) 45%, transparent))"
          : undefined,
      }}
      role="img"
      aria-label={`${clamped} / 100`}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--color-border)"
          strokeWidth={stroke}
        />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          style={{ strokeDashoffset: offset }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <motion.span
          className="font-display text-xl font-bold"
          style={{ color }}
        >
          {rounded}
        </motion.span>
        <span className="-mt-1 text-[10px] font-medium text-faint">/ 100</span>
      </div>
    </motion.div>
  );
}
