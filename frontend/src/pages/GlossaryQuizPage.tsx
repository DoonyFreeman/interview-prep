import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  useGlossary,
  useGlossaryProgress,
  useRecordQuizResult,
} from "../api/hooks";
import { PageLoader, Spinner } from "../components/Spinner";
import { Button } from "../components/Button";
import { Markdown } from "../components/Markdown";
import { ScoreGauge } from "../components/ScoreGauge";
import {
  buildQuiz,
  eligibleCount,
  toResultItems,
  type QuestionType,
  type QuizConfig,
  type QuizQuestion,
  type SelectionMode,
  type StatMap,
} from "../lib/glossaryQuiz";

type Phase = "setup" | "run" | "result";
interface Answer {
  termSlug: string;
  term: string;
  correct: boolean;
}

const COUNT_OPTIONS = [10, 20, 30, 0]; // 0 = all (clamped to pool)
const MODES: SelectionMode[] = ["smart", "weak", "mistakes", "random"];
const TYPES: QuestionType[] = ["def-to-term", "term-to-def"];

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full px-3 py-1.5 text-xs font-semibold transition-colors ${
        active
          ? "bg-primary text-primary-fg"
          : "border border-border bg-surface text-muted hover:bg-surface-2"
      }`}
    >
      {children}
    </button>
  );
}

function catLabel(t: (k: string) => string, slug: string): string {
  const key = `glossary.cat.${slug}`;
  const label = t(key);
  return label === key ? slug : label;
}

export function GlossaryQuizPage({
  kind = "reference",
}: {
  /** "slang" reuses the same engine/stats over the slang dictionary. */
  kind?: "reference" | "slang";
}) {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const glossary = useGlossary(null, "", kind);
  const progress = useGlossaryProgress();
  const record = useRecordQuizResult();

  const isSlang = kind === "slang";
  const basePath = isSlang ? "/slang" : "/glossary";
  const i18nNs = isSlang ? "slangQuiz" : "glossaryQuiz";

  const allTerms = glossary.data?.terms ?? [];
  const categories = glossary.data?.categories ?? [];
  const statMap: StatMap = useMemo(() => {
    const m: StatMap = {};
    for (const s of progress.data?.terms ?? []) m[s.term_slug] = s;
    return m;
  }, [progress.data]);

  // --- config ---
  const preset = params.get("cat");
  const [selectedCats, setSelectedCats] = useState<string[]>([]);
  const [count, setCount] = useState(10);
  const [types, setTypes] = useState<QuestionType[]>([...TYPES]);
  const [mode, setMode] = useState<SelectionMode>("smart");

  // Default category selection once data arrives (all, or the ?cat= preset).
  const initedCats = useRef(false);
  useEffect(() => {
    if (initedCats.current || categories.length === 0) return;
    initedCats.current = true;
    setSelectedCats(
      preset && categories.includes(preset) ? [preset] : [...categories],
    );
  }, [categories, preset]);

  const config: QuizConfig = useMemo(
    () => ({ categories: selectedCats, count: count || 9999, types, mode }),
    [selectedCats, count, types, mode],
  );
  const poolCount = useMemo(
    () => (allTerms.length ? eligibleCount(allTerms, statMap, config) : 0),
    [allTerms, statMap, config],
  );

  // --- run state ---
  const [phase, setPhase] = useState<Phase>("setup");
  const [questions, setQuestions] = useState<QuizQuestion[]>([]);
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, Answer>>({});
  const [picked, setPicked] = useState<string | null>(null);

  function start(cfg: QuizConfig = config) {
    const q = buildQuiz(allTerms, statMap, cfg);
    if (q.length === 0) return;
    setQuestions(q);
    setIndex(0);
    setAnswers({});
    setPicked(null);
    setPhase("run");
  }

  function choose(slug: string) {
    if (picked) return;
    const q = questions[index];
    const correct = q.options.find((o) => o.slug === slug)?.correct ?? false;
    setPicked(slug);
    setAnswers((a) => ({
      ...a,
      [q.id]: { termSlug: q.termSlug, term: q.term, correct },
    }));
  }

  function next() {
    if (index + 1 >= questions.length) {
      setPhase("result");
    } else {
      setIndex((i) => i + 1);
      setPicked(null);
    }
  }

  // Persist the result once when entering the result phase.
  const recorded = useRef(false);
  useEffect(() => {
    if (phase !== "result" || recorded.current) return;
    recorded.current = true;
    const items = toResultItems(Object.values(answers));
    if (items.length) record.mutate(items);
  }, [phase, answers, record]);

  if (glossary.isLoading) return <PageLoader label={t("common.loading")} />;
  if (glossary.isError || !glossary.data)
    return <p className="text-danger">{t("common.error")}</p>;

  // ---------------------------------------------------------------- setup ---
  if (phase === "setup") {
    const toggleCat = (c: string) =>
      setSelectedCats((cur) =>
        cur.includes(c) ? cur.filter((x) => x !== c) : [...cur, c],
      );
    const allSelected = selectedCats.length === categories.length;
    const canStart = selectedCats.length > 0 && types.length > 0 && poolCount > 0;

    return (
      <div className="mx-auto max-w-2xl">
        <Link to={basePath} className="text-sm font-medium text-muted hover:text-ink">
          ← {t(`${i18nNs}.back`)}
        </Link>
        <h1 className="mt-2 text-2xl font-bold text-ink">{t(`${i18nNs}.title`)}</h1>
        <p className="mt-1 mb-6 text-muted">{t(`${i18nNs}.subtitle`)}</p>

        <div className="space-y-6 rounded-2xl border border-border bg-surface p-5 shadow-sm">
          {/* Categories (hidden for slang — it is a single flat dictionary) */}
          {!isSlang && (
            <section>
              <div className="mb-2 flex items-center justify-between">
                <h2 className="text-sm font-bold text-ink">{t("glossaryQuiz.categories")}</h2>
                <Chip
                  active={allSelected}
                  onClick={() =>
                    setSelectedCats(allSelected ? [] : [...categories])
                  }
                >
                  {t("glossaryQuiz.selectAll")}
                </Chip>
              </div>
              <div className="flex flex-wrap gap-2">
                {categories.map((c) => (
                  <Chip key={c} active={selectedCats.includes(c)} onClick={() => toggleCat(c)}>
                    {catLabel(t, c)}
                  </Chip>
                ))}
              </div>
              {selectedCats.length === 0 && (
                <p className="mt-2 text-xs text-danger">{t("glossaryQuiz.needCategory")}</p>
              )}
            </section>
          )}

          {/* Count */}
          <section>
            <h2 className="mb-2 text-sm font-bold text-ink">{t("glossaryQuiz.count")}</h2>
            <div className="flex flex-wrap gap-2">
              {COUNT_OPTIONS.map((c) => (
                <Chip key={c} active={count === c} onClick={() => setCount(c)}>
                  {c === 0 ? t("glossaryQuiz.all") : c}
                </Chip>
              ))}
            </div>
          </section>

          {/* Types */}
          <section>
            <h2 className="mb-2 text-sm font-bold text-ink">{t("glossaryQuiz.types")}</h2>
            <div className="flex flex-wrap gap-2">
              <Chip
                active={types.includes("def-to-term")}
                onClick={() =>
                  setTypes((cur) =>
                    cur.includes("def-to-term")
                      ? cur.filter((x) => x !== "def-to-term")
                      : [...cur, "def-to-term"],
                  )
                }
              >
                {t("glossaryQuiz.typeDefToTerm")}
              </Chip>
              <Chip
                active={types.includes("term-to-def")}
                onClick={() =>
                  setTypes((cur) =>
                    cur.includes("term-to-def")
                      ? cur.filter((x) => x !== "term-to-def")
                      : [...cur, "term-to-def"],
                  )
                }
              >
                {t("glossaryQuiz.typeTermToDef")}
              </Chip>
            </div>
            {types.length === 0 && (
              <p className="mt-2 text-xs text-danger">{t("glossaryQuiz.needType")}</p>
            )}
          </section>

          {/* Mode */}
          <section>
            <h2 className="mb-2 text-sm font-bold text-ink">{t("glossaryQuiz.mode")}</h2>
            <div className="flex flex-wrap gap-2">
              {MODES.map((m) => (
                <Chip key={m} active={mode === m} onClick={() => setMode(m)}>
                  {t(`glossaryQuiz.mode${m[0].toUpperCase()}${m.slice(1)}`)}
                </Chip>
              ))}
            </div>
            <p className="mt-2 text-xs text-faint">
              {t(`glossaryQuiz.mode${mode[0].toUpperCase()}${mode.slice(1)}Hint`)}
            </p>
          </section>

          <div className="flex items-center justify-between gap-3 border-t border-border pt-4">
            <span className="text-xs text-faint">
              {t("glossaryQuiz.poolSize", { count: poolCount })}
            </span>
            <Button onClick={() => start()} disabled={!canStart}>
              {t("glossaryQuiz.start")}
            </Button>
          </div>
          {selectedCats.length > 0 && types.length > 0 && poolCount === 0 && (
            <p className="text-sm text-danger">{t("glossaryQuiz.emptyPool")}</p>
          )}
        </div>
      </div>
    );
  }

  // ------------------------------------------------------------------ run ---
  if (phase === "run") {
    const q = questions[index];
    return (
      <div className="mx-auto max-w-2xl">
        <div className="mb-3 flex items-center justify-between">
          <span className="text-xs font-semibold text-faint">
            {t("glossaryQuiz.progress", {
              current: index + 1,
              total: questions.length,
            })}
          </span>
          <Link to={basePath} className="text-xs font-medium text-muted hover:text-ink">
            ✕
          </Link>
        </div>

        <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
          {q.promptIsMarkdown ? (
            <div className="prose-sm">
              <Markdown markdown={q.prompt} />
            </div>
          ) : (
            <p className="text-xl font-bold text-ink">{q.prompt}</p>
          )}
        </div>

        <div className="mt-4 space-y-2">
          {q.options.map((o) => {
            const isPicked = picked === o.slug;
            const reveal = picked != null;
            let cls =
              "border-border bg-surface hover:bg-surface-2 text-ink";
            if (reveal && o.correct)
              cls = "border-success/40 bg-success-soft text-success";
            else if (reveal && isPicked)
              cls = "border-danger/40 bg-danger-soft text-danger";
            else if (reveal) cls = "border-border bg-surface text-muted";
            return (
              <button
                key={o.slug}
                onClick={() => choose(o.slug)}
                disabled={reveal}
                className={`flex w-full items-center gap-3 rounded-xl border px-4 py-3 text-left text-sm font-medium transition-colors disabled:cursor-default ${cls}`}
              >
                <span className="w-4 shrink-0 text-center">
                  {reveal && o.correct ? "✓" : reveal && isPicked ? "✗" : ""}
                </span>
                <span>{o.label}</span>
              </button>
            );
          })}
        </div>

        {picked != null && (
          <div className="mt-4 rounded-2xl border border-border bg-surface-2 p-4">
            <h3 className="text-sm font-bold text-ink">{q.term}</h3>
            <div className="prose-sm mt-1">
              <Markdown markdown={q.definition} />
            </div>
            <div className="mt-3 flex justify-end">
              <Button onClick={next}>
                {index + 1 >= questions.length
                  ? t("glossaryQuiz.finish")
                  : t("glossaryQuiz.next")}{" "}
                →
              </Button>
            </div>
          </div>
        )}
      </div>
    );
  }

  // --------------------------------------------------------------- result ---
  const answeredList = questions
    .map((q) => answers[q.id])
    .filter((a): a is Answer => a != null);
  const correctCount = answeredList.filter((a) => a.correct).length;
  const total = answeredList.length;
  const pct = total ? Math.round((correctCount / total) * 100) : 0;
  const missed = answeredList.filter((a) => !a.correct);

  return (
    <div className="mx-auto max-w-2xl text-center">
      <h1 className="text-2xl font-bold text-ink">{t("glossaryQuiz.resultTitle")}</h1>

      <div className="mt-6 flex flex-col items-center gap-3">
        <ScoreGauge score={pct} size={120} />
        <p className="text-lg font-semibold text-ink">
          {t("glossaryQuiz.score", { correct: correctCount, total })}
        </p>
        {record.isPending && <Spinner />}
        {record.isError && (
          <p className="text-sm text-danger">{t("glossaryQuiz.savingError")}</p>
        )}
      </div>

      {missed.length === 0 ? (
        <p className="mt-6 font-semibold text-success">🎉 {t("glossaryQuiz.perfect")}</p>
      ) : (
        <div className="mt-8 text-left">
          <h2 className="mb-3 text-xs font-bold uppercase tracking-wide text-faint">
            {t("glossaryQuiz.missedTitle")}
          </h2>
          <div className="flex flex-wrap gap-2">
            {missed.map((a) => (
              <Link
                key={a.termSlug}
                to={`${basePath}#${a.termSlug}`}
                className="rounded-full bg-danger-soft px-3 py-1 text-xs font-semibold text-danger hover:opacity-80"
              >
                {a.term}
              </Link>
            ))}
          </div>
        </div>
      )}

      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <Button
          onClick={() => {
            recorded.current = false;
            start();
          }}
        >
          ↻ {t("glossaryQuiz.retry")}
        </Button>
        <Button
          variant="secondary"
          onClick={() => {
            recorded.current = false;
            setPhase("setup");
          }}
        >
          {t("glossaryQuiz.toSetup")}
        </Button>
        <Link to={basePath}>
          <Button variant="ghost">
            {t(isSlang ? "slangQuiz.toList" : "glossaryQuiz.toGlossary")}
          </Button>
        </Link>
      </div>
    </div>
  );
}
