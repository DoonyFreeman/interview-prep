import { useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import { AnimatePresence, motion } from "motion/react";
import { useGlossary, useProgress } from "../api/hooks";
import { pickThought, type CatThought } from "../lib/cat";
import { CatSprite } from "./CatSprite";
import { ThoughtBubble } from "./ThoughtBubble";
import { useCat } from "./useCat";

export function CatWidget() {
  const { t } = useTranslation();
  const cat = useCat();
  const { data: glossary } = useGlossary(null, "", "reference");
  const { data: progress } = useProgress();

  const [open, setOpen] = useState(false);
  const [thought, setThought] = useState<CatThought | null>(null);

  const onCatClick = useCallback(() => {
    cat.pet();
    if (open) {
      setOpen(false);
      return;
    }
    setThought(pickThought(glossary?.terms ?? [], progress, Date.now()));
    setOpen(true);
  }, [cat, open, glossary, progress]);

  // Collapsed: a tiny paw to bring the cat back.
  if (cat.state.hidden) {
    return (
      <button
        onClick={() => cat.setHidden(false)}
        title={t("cat.show")}
        className="fixed right-3 bottom-[calc(4.25rem+env(safe-area-inset-bottom))] z-40 flex h-9 w-9 items-center justify-center rounded-full border border-border bg-surface text-base shadow-card transition-transform hover:scale-110 sm:bottom-3"
      >
        <span aria-hidden>🐾</span>
      </button>
    );
  }

  const bob =
    !cat.reducedMotion && cat.mood === "idle"
      ? { y: [0, -2, 0] }
      : cat.mood === "play" && !cat.reducedMotion
        ? { rotate: [0, -6, 6, 0], scale: [1, 1.08, 1] }
        : {};

  return (
    <div className="fixed right-3 bottom-[calc(4.25rem+env(safe-area-inset-bottom))] z-40 sm:right-4 sm:bottom-4">
      <AnimatePresence>
        {open && (
          <ThoughtBubble
            thought={thought}
            streak={cat.state.streak}
            skin={cat.skin}
            unlocked={cat.unlocked}
            onSkin={cat.setSkin}
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
        aria-label={t("cat.show")}
        className="block origin-bottom select-none rounded-xl p-0.5 transition-transform active:scale-95"
        animate={bob}
        transition={
          cat.mood === "play"
            ? { duration: 0.5 }
            : { duration: 2.6, repeat: Infinity, ease: "easeInOut" }
        }
      >
        <CatSprite
          skin={cat.skin}
          stage={cat.stage}
          mood={cat.mood}
          animate={!cat.reducedMotion}
          size={62}
        />
      </motion.button>
    </div>
  );
}
