import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useCatThoughts } from "../api/hooks";
import { pickThought, type CatThought } from "../lib/cat";
import { CatBurst } from "./CatBurst";
import { CatSprite } from "./CatSprite";
import { ThoughtBubble } from "./ThoughtBubble";
import { useCat } from "./useCat";
import { useCatMood, type CatMood, type CatReaction } from "./useCatMood";
import { IconPaw } from "../components/icons";

const EASE_SOFT = [0.22, 1, 0.36, 1] as const; // smooth, gentle ease-out

/** A different cute one-shot for each tap — never sharp, always springy. */
function reactionMotion(reaction: CatReaction) {
  switch (reaction) {
    case "hop":
      return {
        animate: { y: [0, -12, 0, -5, 0] },
        transition: { duration: 0.75, ease: EASE_SOFT },
      };
    case "wiggle":
      return {
        animate: { rotate: [0, -10, 9, -6, 5, 0] },
        transition: { duration: 0.8, ease: "easeInOut" as const },
      };
    case "wobble":
      return {
        animate: { rotate: [0, -6, 6, -3, 0], scale: [1, 1.07, 1] },
        transition: { duration: 0.75, ease: "easeInOut" as const },
      };
    case "pounce":
      return {
        animate: {
          y: [0, 5, -9, 0],
          scaleX: [1, 1.14, 0.96, 1],
          scaleY: [1, 0.84, 1.06, 1],
        },
        transition: { duration: 0.7, ease: "easeOut" as const },
      };
    case "spin":
      return {
        animate: { rotate: [0, 360], scale: [1, 0.9, 1] },
        transition: { duration: 0.85, ease: EASE_SOFT },
      };
  }
}

/** Per-mood whole-cat motion (the sprite handles the face; this adds life). */
function moodMotion(mood: CatMood, reaction: CatReaction, reduced: boolean) {
  if (reduced) return { animate: {}, transition: {} };
  if (mood === "play") return reactionMotion(reaction);
  switch (mood) {
    case "stretch":
      return {
        animate: { scaleX: [1, 1.12, 1], scaleY: [1, 0.9, 1] },
        transition: { duration: 1.1, ease: "easeInOut" as const },
      };
    case "look":
      return {
        animate: { x: [0, 2, 0, -2, 0], rotate: [0, 1.5, 0, -1.5, 0] },
        transition: { duration: 2.4, ease: "easeInOut" as const },
      };
    case "groom":
      return {
        animate: { y: [0, -1.5, 0], rotate: [0, -2.5, 0] },
        transition: { duration: 1.5, repeat: Infinity, ease: "easeInOut" as const },
      };
    case "sleep":
      return {
        animate: { scale: [1, 1.035, 1] },
        transition: { duration: 3.4, repeat: Infinity, ease: "easeInOut" as const },
      };
    default: // idle — gentle bob + soft breathing
      return {
        animate: { y: [0, -2.5, 0], scale: [1, 1.02, 1] },
        transition: { duration: 3, repeat: Infinity, ease: "easeInOut" as const },
      };
  }
}

// Anti-repeat: remember the last N thought keys across reloads so the cat keeps
// varying what it says even after a page refresh.
const SEEN_KEY = "cat_recent_v1";
const SEEN_WINDOW = 30;

function loadRecent(): string[] {
  try {
    const raw = localStorage.getItem(SEEN_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((x) => typeof x === "string") : [];
  } catch {
    return [];
  }
}

function saveRecent(keys: string[]): void {
  try {
    localStorage.setItem(SEEN_KEY, JSON.stringify(keys));
  } catch {
    /* storage may be unavailable (private mode) — anti-repeat is best-effort */
  }
}

export function CatWidget() {
  const { t } = useTranslation();
  const reducedMotion = useReducedMotion() ?? false;
  const cat = useCat();
  const { mood, reaction, playId, pet, wake } = useCatMood(reducedMotion);
  const { data: thoughts } = useCatThoughts();

  const [open, setOpen] = useState(false);
  const [thought, setThought] = useState<CatThought | null>(null);
  // Keys of recently shown thoughts (persisted), so clicks don't repeat a topic.
  const recentRef = useRef<string[]>(loadRecent());

  // Roll the daily streak (and migrate legacy localStorage) once after load.
  const rolled = useRef(false);
  useEffect(() => {
    if (cat.loaded && !rolled.current) {
      rolled.current = true;
      cat.syncDailyStreak();
    }
  }, [cat]);

  const onCatClick = useCallback(() => {
    wake();
    pet();
    if (open) {
      setOpen(false);
      return;
    }
    const next = pickThought(thoughts ?? [], recentRef.current, Date.now());
    if (next) {
      // Remember the last N keys (persisted) so picks avoid recent repeats.
      recentRef.current = [...recentRef.current, next.key].slice(-SEEN_WINDOW);
      saveRecent(recentRef.current);
    }
    setThought(next);
    setOpen(true);
  }, [wake, pet, open, thoughts]);

  if (!cat.loaded) return null;

  const petName = cat.pet.name.trim() || t("cat.defaultName");

  // Collapsed: a tiny paw to bring the cat back.
  if (cat.pet.hidden) {
    return (
      <button
        onClick={() => cat.setHidden(false)}
        title={petName}
        className="fixed right-3 bottom-[calc(5rem+env(safe-area-inset-bottom))] z-40 flex h-9 w-9 items-center justify-center rounded-full border border-border bg-surface text-muted shadow-card transition-transform hover:scale-110 hover:text-accent sm:bottom-3"
        aria-label={petName}
      >
        <IconPaw className="h-[18px] w-[18px]" />
      </button>
    );
  }

  const { animate, transition } = moodMotion(mood, reaction, reducedMotion);

  return (
    <div className="fixed right-3 bottom-[calc(5rem+env(safe-area-inset-bottom))] z-40 sm:right-4 sm:bottom-4">
      <AnimatePresence>
        {open && (
          <ThoughtBubble
            name={petName}
            thought={thought}
            streak={cat.pet.streak}
            onClose={() => setOpen(false)}
            onHide={() => {
              setOpen(false);
              cat.setHidden(true);
            }}
          />
        )}
      </AnimatePresence>

      {/* A spray of hearts/stars/paws/notes on each tap. Keyed by `playId` so
          every tap mounts a fresh burst and AnimatePresence lets the previous
          one finish flying out instead of snapping away. */}
      <AnimatePresence>
        {mood === "play" && (
          <CatBurst key={playId} seed={playId} reduced={reducedMotion} />
        )}
      </AnimatePresence>

      <motion.button
        onClick={onCatClick}
        aria-label={petName}
        title={petName}
        className="block origin-bottom select-none rounded-xl p-0.5 transition-transform active:scale-95"
        animate={animate}
        transition={transition}
      >
        <CatSprite
          skin={cat.skin}
          stage={cat.stage}
          mood={mood}
          hat={cat.hat}
          animate={!reducedMotion}
          size={62}
        />
      </motion.button>
    </div>
  );
}
