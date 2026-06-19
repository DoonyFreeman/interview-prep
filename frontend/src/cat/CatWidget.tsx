import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useGlossary, useProgress } from "../api/hooks";
import { pickThought, type CatThought } from "../lib/cat";
import { CatSprite } from "./CatSprite";
import { ThoughtBubble } from "./ThoughtBubble";
import { useCat } from "./useCat";
import { useCatMood, type CatMood } from "./useCatMood";

/** Per-mood whole-cat motion (the sprite handles the face; this adds life). */
function moodMotion(mood: CatMood, reduced: boolean) {
  if (reduced) return { animate: {}, transition: {} };
  switch (mood) {
    case "play":
      return {
        animate: { rotate: [0, -6, 6, 0], scale: [1, 1.08, 1] },
        transition: { duration: 0.5 },
      };
    case "stretch":
      return {
        animate: { scaleX: [1, 1.12, 1], scaleY: [1, 0.9, 1] },
        transition: { duration: 0.9, ease: "easeInOut" as const },
      };
    case "look":
      return {
        animate: { x: [0, 2, 0] },
        transition: { duration: 1.2, ease: "easeInOut" as const },
      };
    case "sleep":
      return {
        animate: { scale: [1, 1.03, 1] },
        transition: { duration: 3.2, repeat: Infinity, ease: "easeInOut" as const },
      };
    default: // idle / groom — gentle bob
      return {
        animate: { y: [0, -2, 0] },
        transition: { duration: 2.6, repeat: Infinity, ease: "easeInOut" as const },
      };
  }
}

export function CatWidget() {
  const { t } = useTranslation();
  const reducedMotion = useReducedMotion() ?? false;
  const cat = useCat();
  const { mood, pet, wake } = useCatMood(reducedMotion);
  const { data: glossary } = useGlossary(null, "", "reference");
  const { data: progress } = useProgress();

  const [open, setOpen] = useState(false);
  const [thought, setThought] = useState<CatThought | null>(null);

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
    setThought(pickThought(glossary?.terms ?? [], progress, Date.now()));
    setOpen(true);
  }, [wake, pet, open, glossary, progress]);

  if (!cat.loaded) return null;

  const petName = cat.pet.name.trim() || t("cat.defaultName");

  // Collapsed: a tiny paw to bring the cat back.
  if (cat.pet.hidden) {
    return (
      <button
        onClick={() => cat.setHidden(false)}
        title={petName}
        className="fixed right-3 bottom-[calc(4.25rem+env(safe-area-inset-bottom))] z-40 flex h-9 w-9 items-center justify-center rounded-full border border-border bg-surface text-base shadow-card transition-transform hover:scale-110 sm:bottom-3"
      >
        <span aria-hidden>🐾</span>
      </button>
    );
  }

  const { animate, transition } = moodMotion(mood, reducedMotion);

  return (
    <div className="fixed right-3 bottom-[calc(4.25rem+env(safe-area-inset-bottom))] z-40 sm:right-4 sm:bottom-4">
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
          animate={!reducedMotion}
          size={62}
        />
      </motion.button>
    </div>
  );
}
