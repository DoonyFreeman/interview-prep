import { useCallback, useEffect, useRef, useState } from "react";
import { useReducedMotion } from "motion/react";
import {
  DEFAULT_CAT_STATE,
  resolveSkin,
  rolloverStreak,
  skinsUnlocked,
  stageForStreak,
  todayKey,
  type CatSkin,
  type CatStage,
  type CatState,
} from "../lib/cat";

const KEY = "ip_cat";

function load(): CatState {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return { ...DEFAULT_CAT_STATE };
    return { ...DEFAULT_CAT_STATE, ...(JSON.parse(raw) as Partial<CatState>) };
  } catch {
    return { ...DEFAULT_CAT_STATE };
  }
}

function save(state: CatState) {
  try {
    localStorage.setItem(KEY, JSON.stringify(state));
  } catch {
    // private mode / quota — the cat just won't remember. No-op.
  }
}

export type CatMood = "idle" | "sleep" | "play";

export interface CatApi {
  state: CatState;
  stage: CatStage;
  mood: CatMood;
  skin: CatSkin;
  unlocked: CatSkin[];
  reducedMotion: boolean;
  pet: () => void;
  wake: () => void;
  setSkin: (s: CatSkin) => void;
  setHidden: (h: boolean) => void;
}

const SLEEP_AFTER_MS = 30_000;
const PLAY_MS = 2200;

/** Stateful cat: persists to localStorage, rolls the daily streak once on
 *  mount, and runs a tiny mood machine (idle ⇄ sleep, momentary play). */
export function useCat(): CatApi {
  const [state, setState] = useState<CatState>(() => {
    const rolled = rolloverStreak(load(), todayKey());
    const skin = resolveSkin(rolled.skin, rolled.bestStreak);
    return skin === rolled.skin ? rolled : { ...rolled, skin };
  });
  const [mood, setMood] = useState<CatMood>("idle");
  const sleepTimer = useRef<ReturnType<typeof setTimeout>>();
  const playTimer = useRef<ReturnType<typeof setTimeout>>();
  const reducedMotion = useReducedMotion() ?? false;

  useEffect(() => {
    save(state);
  }, [state]);

  const armSleep = useCallback(() => {
    clearTimeout(sleepTimer.current);
    sleepTimer.current = setTimeout(() => setMood("sleep"), SLEEP_AFTER_MS);
  }, []);

  useEffect(() => {
    armSleep();
    return () => {
      clearTimeout(sleepTimer.current);
      clearTimeout(playTimer.current);
    };
  }, [armSleep]);

  const wake = useCallback(() => {
    setMood("idle");
    armSleep();
  }, [armSleep]);

  const pet = useCallback(() => {
    clearTimeout(playTimer.current);
    setMood("play");
    playTimer.current = setTimeout(() => setMood("idle"), PLAY_MS);
    armSleep();
  }, [armSleep]);

  const setSkin = useCallback((s: CatSkin) => {
    setState((prev) =>
      skinsUnlocked(prev.bestStreak).includes(s) ? { ...prev, skin: s } : prev,
    );
  }, []);

  const setHidden = useCallback((h: boolean) => {
    setState((prev) => ({ ...prev, hidden: h }));
  }, []);

  return {
    state,
    stage: stageForStreak(state.streak),
    mood,
    skin: state.skin,
    unlocked: skinsUnlocked(state.bestStreak),
    reducedMotion,
    pet,
    wake,
    setSkin,
    setHidden,
  };
}
