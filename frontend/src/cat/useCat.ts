import { useCallback } from "react";
import { usePet, useUpdatePet } from "../api/hooks";
import {
  DEFAULT_CAT_STATE,
  petDiff,
  petToCatState,
  rolloverStreak,
  skinsUnlocked,
  stageForStreak,
  todayKey,
  type CatSkin,
  type CatState,
} from "../lib/cat";

const LEGACY_KEY = "ip_cat";

/** Read the pre-server localStorage state (for the one-time migration). */
function readLegacy(): CatState | null {
  try {
    const raw = localStorage.getItem(LEGACY_KEY);
    if (!raw) return null;
    return { ...DEFAULT_CAT_STATE, ...(JSON.parse(raw) as Partial<CatState>) };
  } catch {
    return null;
  }
}

export interface CatPersistApi {
  /** Server-backed pet state (defaults while the query loads). */
  pet: CatState;
  loaded: boolean;
  stage: ReturnType<typeof stageForStreak>;
  skin: CatSkin;
  unlocked: CatSkin[];
  setName: (name: string) => void;
  setSkin: (skin: CatSkin) => void;
  setHidden: (hidden: boolean) => void;
  /** Roll the daily streak (and migrate legacy localStorage) once on load. */
  syncDailyStreak: () => void;
}

/**
 * Pet state, server-backed via TanStack Query. The query cache is shared, so
 * the corner widget and the settings form see the same data and update live.
 * The streak's "day" is the user's *local* day, so the rollover is computed
 * here and pushed up.
 */
export function useCat(): CatPersistApi {
  const { data, isSuccess } = usePet();
  const update = useUpdatePet();

  const pet: CatState = data ? petToCatState(data) : { ...DEFAULT_CAT_STATE };

  const syncDailyStreak = useCallback(() => {
    if (!data) return;
    const server = petToCatState(data);

    // One-time migration: if the server pet was never active but this browser
    // has a legacy streak, carry it over so nothing visibly resets.
    let base = server;
    const legacy = readLegacy();
    if (
      server.lastActiveDay == null &&
      legacy &&
      (legacy.streak > 0 || legacy.name || legacy.skin !== "classic")
    ) {
      base = {
        ...server,
        name: server.name || legacy.name,
        skin: legacy.skin,
        streak: legacy.streak,
        bestStreak: Math.max(legacy.bestStreak, legacy.streak),
        lastActiveDay: legacy.lastActiveDay,
        hidden: legacy.hidden,
      };
    }

    const rolled = rolloverStreak(base, todayKey());
    const patch = petDiff(server, rolled);
    if (patch) update.mutate(patch);
    try {
      localStorage.removeItem(LEGACY_KEY);
    } catch {
      /* ignore */
    }
  }, [data, update]);

  return {
    pet,
    loaded: isSuccess,
    stage: stageForStreak(pet.streak),
    skin: pet.skin,
    unlocked: skinsUnlocked(pet.bestStreak),
    setName: (name) => update.mutate({ name }),
    setSkin: (skin) => update.mutate({ skin }),
    setHidden: (hidden) => update.mutate({ hidden }),
    syncDailyStreak,
  };
}
