import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "../components/Button";
import { useToast } from "../components/Toast";
import { SKIN_MILESTONES, type CatSkin } from "../lib/cat";
import { CatSprite } from "./CatSprite";
import { useCat } from "./useCat";

const inputCls =
  "w-full rounded-xl border border-border bg-surface-2 px-3 py-2.5 text-sm outline-none transition-colors focus:border-primary";
const labelCls = "mb-1 block text-xs font-semibold text-muted";

export function PetSettings() {
  const { t } = useTranslation();
  const toast = useToast();
  const cat = useCat();

  const [name, setName] = useState(cat.pet.name);
  useEffect(() => {
    setName(cat.pet.name);
  }, [cat.pet.name]);

  if (!cat.loaded) return null;

  function saveName() {
    cat.setName(name.trim().slice(0, 40));
    toast.success(t("settings.saved"));
  }

  const displayName = cat.pet.name.trim() || t("cat.defaultName");

  return (
    <div className="space-y-5">
      {/* Live preview */}
      <div className="flex items-center gap-4 rounded-xl border border-border bg-surface-2 p-4">
        <CatSprite
          skin={cat.skin}
          stage={cat.stage}
          mood="idle"
          animate={false}
          size={72}
        />
        <div className="min-w-0">
          <p className="truncate font-display text-base font-bold text-ink">
            {displayName}
          </p>
          <p className="text-xs text-muted">
            🔥 {t("cat.streakDays", { count: cat.pet.streak })} ·{" "}
            {t("settings.petBest", { count: cat.pet.bestStreak })}
          </p>
        </div>
      </div>

      {/* Name */}
      <div>
        <label className="block">
          <span className={labelCls}>{t("settings.petName")}</span>
          <input
            value={name}
            maxLength={40}
            placeholder={t("cat.defaultName")}
            onChange={(e) => setName(e.target.value)}
            className={inputCls}
          />
        </label>
        <div className="mt-2">
          <Button onClick={saveName}>{t("settings.save")}</Button>
        </div>
      </div>

      {/* Skins */}
      <div>
        <span className={labelCls}>{t("settings.petSkin")}</span>
        <div className="grid grid-cols-3 gap-2.5 sm:grid-cols-5">
          {SKIN_MILESTONES.map(({ skin, at }) => {
            const unlocked = cat.unlocked.includes(skin);
            const selected = cat.skin === skin;
            return (
              <button
                key={skin}
                type="button"
                disabled={!unlocked}
                onClick={() => cat.setSkin(skin as CatSkin)}
                className={`relative flex flex-col items-center gap-1 rounded-xl border p-2 transition-colors ${
                  selected
                    ? "border-primary bg-primary-soft"
                    : "border-border bg-surface-2 hover:bg-surface"
                } ${unlocked ? "" : "cursor-not-allowed"}`}
                title={
                  unlocked
                    ? t(`cat.skins.${skin}`)
                    : t("settings.petSkinLocked", { count: at })
                }
              >
                <span className={unlocked ? "" : "opacity-30 grayscale"}>
                  <CatSprite
                    skin={skin as CatSkin}
                    stage={cat.stage}
                    mood="idle"
                    animate={false}
                    size={40}
                  />
                </span>
                <span className="text-[10px] font-semibold text-muted">
                  {unlocked ? t(`cat.skins.${skin}`) : `🔒 ${at}`}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Visibility */}
      <label className="flex cursor-pointer items-center justify-between gap-3 rounded-xl border border-border bg-surface-2 px-3 py-2.5">
        <span className="text-sm font-semibold text-ink">
          {t("settings.petVisible")}
        </span>
        <input
          type="checkbox"
          checked={!cat.pet.hidden}
          onChange={(e) => cat.setHidden(!e.target.checked)}
          className="h-5 w-5 accent-primary"
        />
      </label>
    </div>
  );
}
