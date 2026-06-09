import { useTranslation } from "react-i18next";
import { useQuestionAttempts } from "../api/hooks";
import { Spinner } from "./Spinner";
import { ScorePill } from "./ScorePill";
import { VerdictBadge } from "./VerdictBadge";
import type { AttemptOut } from "../api/types";

function AttemptItem({ a }: { a: AttemptOut }) {
  const { t, i18n } = useTranslation();
  const when = new Date(a.created_at + "Z").toLocaleString(i18n.language, {
    dateStyle: "medium",
    timeStyle: "short",
  });
  return (
    <div className="rounded-xl border border-border bg-surface-2 p-3">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <ScorePill score={a.score} />
        <VerdictBadge verdict={a.verdict} />
        {a.hint_used && (
          <span className="rounded-full bg-surface px-2 py-0.5 text-xs text-muted">
            {t("questions.hintUsed")}
          </span>
        )}
        <span className="ml-auto text-xs text-faint">{when}</span>
      </div>

      <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink">
        <span className="font-semibold text-muted">
          {t("questions.yourAnswer")}:{" "}
        </span>
        {a.answer_text}
      </p>

      {a.summary && <p className="mt-2 text-sm text-muted">{a.summary}</p>}

      {a.gaps.length > 0 && (
        <ul className="mt-2 space-y-1">
          {a.gaps.map((g, i) => (
            <li key={i} className="flex gap-2 text-sm text-ink">
              <span className="mt-0.5 text-danger">•</span>
              <span>{g}</span>
            </li>
          ))}
        </ul>
      )}

      {a.suggestion && (
        <div className="mt-2 rounded-lg bg-primary-soft px-3 py-2 text-sm text-ink">
          <span className="font-semibold">{t("quiz.suggestion")}: </span>
          {a.suggestion}
        </div>
      )}
    </div>
  );
}

export function AttemptHistory({ questionId }: { questionId: number }) {
  const { t } = useTranslation();
  const { data, isLoading, isError } = useQuestionAttempts(questionId);

  if (isLoading)
    return (
      <div className="flex justify-center py-3">
        <Spinner />
      </div>
    );
  if (isError || !data)
    return <p className="py-2 text-sm text-danger">{t("common.error")}</p>;
  if (data.attempts.length === 0)
    return <p className="py-2 text-sm text-faint">{t("questions.noAnswersYet")}</p>;

  return (
    <div className="mt-3 space-y-2">
      {data.attempts.map((a) => (
        <AttemptItem key={a.id} a={a} />
      ))}
    </div>
  );
}
