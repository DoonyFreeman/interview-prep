import { useTranslation } from "react-i18next";

const LANGS = ["ru", "en"] as const;

export function LanguageToggle() {
  const { i18n } = useTranslation();
  const current = i18n.resolvedLanguage ?? "ru";

  return (
    <div className="inline-flex overflow-hidden rounded-lg border border-border bg-surface text-xs font-semibold">
      {LANGS.map((lng) => (
        <button
          key={lng}
          onClick={() => i18n.changeLanguage(lng)}
          className={`px-2.5 py-1 uppercase transition-colors ${
            current.startsWith(lng)
              ? "bg-primary text-primary-fg"
              : "text-muted hover:bg-surface-2"
          }`}
        >
          {lng}
        </button>
      ))}
    </div>
  );
}
