import { createContext, useContext } from "react";
import { useTranslation } from "react-i18next";

type RehearsalAnswer = { question: string; answer: string };
export type PrivateHrAnswerGroups = Record<string, RehearsalAnswer[]>;

export const PrivateHrAnswersContext = createContext<PrivateHrAnswerGroups | undefined>(
  undefined,
);

export function PrivateHrAnswers({ slot }: { slot: string }) {
  const { t } = useTranslation();
  const answers = useContext(PrivateHrAnswersContext);
  const items = answers && Object.hasOwn(answers, slot) ? answers[slot] : undefined;
  if (!items?.length) return null;

  return (
    <section className="not-prose my-5 rounded-xl border border-border bg-primary-soft p-3 sm:p-4">
      <p className="font-display text-base font-bold text-ink">{t("privateHr.title")}</p>
      <p className="mt-0.5 mb-3 text-xs text-muted">{t("privateHr.subtitle")}</p>
      <div className="space-y-2">
        {items.map(({ question, answer }) => (
          <details key={question} className="rounded-lg border border-border bg-surface">
            <summary className="min-h-11 cursor-pointer rounded-lg px-3 py-2.5 text-sm font-semibold text-ink focus-visible:outline-2 focus-visible:outline-primary">
              {question}
            </summary>
            <p className="border-t border-border px-3 py-3 text-sm leading-relaxed text-ink whitespace-pre-wrap [overflow-wrap:anywhere]">
              {answer}
            </p>
          </details>
        ))}
      </div>
    </section>
  );
}
