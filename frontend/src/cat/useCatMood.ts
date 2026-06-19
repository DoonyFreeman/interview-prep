import { useCallback, useEffect, useRef, useState } from "react";

export type CatMood = "idle" | "sleep" | "play" | "groom" | "look" | "stretch";

/** Different cute ways the cat reacts to a tap (picked at random each time). */
export type CatReaction = "hop" | "wiggle" | "wobble" | "pounce" | "spin";
const REACTIONS: CatReaction[] = ["hop", "wiggle", "wobble", "pounce", "spin"];

const PLAY_MS = 2200;
const MIN_GAP = 4000;
const MAX_GAP = 11000;
// Calm idle actions the cat drifts through on its own.
const AMBIENT: CatMood[] = ["idle", "idle", "idle", "look", "groom", "stretch"];

function rand(min: number, max: number) {
  return min + Math.random() * (max - min);
}
function pick<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

/**
 * Makes the cat feel *alive*: on its own it glances around, grooms, stretches,
 * dozes off after a while and wakes back up — at random intervals. Clicking
 * (`pet`) plays a happy beat and resets its sleepiness. Honours
 * `prefers-reduced-motion` by staying calmly idle (no autonomous motion).
 */
export function useCatMood(reducedMotion: boolean) {
  const [mood, setMood] = useState<CatMood>("idle");
  const [reaction, setReaction] = useState<CatReaction>("hop");
  // Bumped on every tap so the widget can re-trigger a one-shot particle even
  // when the same reaction is rolled twice in a row.
  const [playId, setPlayId] = useState(0);
  const sleepiness = useRef(0);
  const ambientTimer = useRef<ReturnType<typeof setTimeout>>();
  const playTimer = useRef<ReturnType<typeof setTimeout>>();

  // Autonomous ambient loop.
  useEffect(() => {
    if (reducedMotion) {
      setMood("idle");
      return;
    }
    let alive = true;

    const tick = () => {
      ambientTimer.current = setTimeout(() => {
        if (!alive) return;
        setMood((prev) => {
          if (prev === "play") return prev; // never interrupt a play beat
          if (prev === "sleep") {
            // Sometimes wake up, otherwise keep snoozing.
            if (Math.random() < 0.4) {
              sleepiness.current = 0;
              return "stretch"; // wake with a stretch
            }
            return "sleep";
          }
          sleepiness.current += 1;
          if (sleepiness.current >= 4 && Math.random() < 0.6) {
            return "sleep";
          }
          return pick(AMBIENT);
        });
        tick();
      }, rand(MIN_GAP, MAX_GAP));
    };
    tick();

    return () => {
      alive = false;
      clearTimeout(ambientTimer.current);
    };
  }, [reducedMotion]);

  const wake = useCallback(() => {
    sleepiness.current = 0;
    setMood("idle");
  }, []);

  const pet = useCallback(() => {
    sleepiness.current = 0;
    clearTimeout(playTimer.current);
    setReaction(pick(REACTIONS));
    setPlayId((n) => n + 1);
    setMood("play");
    playTimer.current = setTimeout(() => setMood("idle"), PLAY_MS);
  }, []);

  useEffect(() => () => clearTimeout(playTimer.current), []);

  return { mood, reaction, playId, pet, wake };
}
