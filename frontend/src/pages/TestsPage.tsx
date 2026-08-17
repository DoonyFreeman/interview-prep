import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { motion } from "motion/react";
import { useGenerateMix, useRecordMix, useTestTopics } from "../api/hooks";
import type { MixBank, MixMode, TestTopic } from "../api/types";
import { Button } from "../components/Button";
import { EmptyState } from "../components/EmptyState";
import { SkeletonCard } from "../components/Skeleton";
import { TestRunner } from "../components/TestRunner";
import {
  IconClipboardCheck,
  IconRefresh,
  IconSparkles,
  IconTarget,
} from "../components/icons";
import { fade, fadeInUp, staggerContainer } from "../lib/motion";
import { prepareTest, toResultItems, type PreparedMcq } from "../lib/lessonTest";

const COUNTS = [10, 20, 30, 50] as const;

/** The one-tap presets. Each is just a (mode, count) pair — the same knobs the
 *  manual panel exposes, pre-set for the three things people actually want. */
const PRESETS: {
  mode: MixMode;
  count: number;
  labelKey: string;
  noteKey: string;
  Icon: (p: { className?: string }) => React.ReactElement;
  tone: string;
  /** Which topic tally has to be non-zero for this preset to make sense. */
  requires?: "answered" | "weak";
}[] = [
  {
    mode: "random",
    count: 20,
    labelKey: "tests.presetRandom",
    noteKey: "tests.presetRandomNote",
    Icon: IconRefresh,
    tone: "text-primary",
  },
  {
    mode: "smart",
    count: 20,
    labelKey: "tests.presetSmart",
    noteKey: "tests.presetSmartNote",
    Icon: IconSparkles,
    tone: "text-celebrate",
  },
  {
    mode: "mistakes",
    count: 20,
    labelKey: "tests.presetMistakes",
    noteKey: "tests.presetMistakesNote",
    Icon: IconTarget,
    tone: "text-accent",
    requires: "weak",
  },
];

/** A segmented control — the same shape used across the app's settings rows. */
function Segmented<T extends string | number>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
  label: string;
}) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className="inline-flex flex-wrap gap-1 rounded-xl border border-border bg-surface-2 p-1"
    >
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={String(o.value)}
            role="radio"
            aria-checked={active}
            onClick={() => onChange(o.value)}
            className={`relative rounded-lg px-3 py-1.5 text-sm font-semibold transition-colors ${
              active ? "text-primary" : "text-muted hover:text-ink"
            }`}
          >
            {active && (
              <motion.span
                layoutId={`seg-${label}`}
                className="absolute inset-0 rounded-lg bg-surface shadow-card"
                transition={{ type: "spring", stiffness: 480, damping: 38 }}
              />
            )}
            <span className="relative">{o.label}</span>
          </button>
        );
      })}
    </div>
  );
}

export function TestsPage() {
  const { t } = useTranslation();
  const topics = useTestTopics();
  const generate = useGenerateMix();
  const record = useRecordMix();

  const [selected, setSelected] = useState<string[]>([]); // empty = all topics
  const [count, setCount] = useState<number>(20);
  const [mode, setMode] = useState<MixMode>("smart");
  const [banks, setBanks] = useState<MixBank[]>(["lesson", "exam"]);
  const [prepared, setPrepared] = useState<PreparedMcq[] | null>(null);

  const all = topics.data;
  const hasExam = (all?.exam_total ?? 0) > 0;

  /** How many questions the current filter can actually draw from. */
  const pool = useMemo(() => {
    if (!all) return 0;
    const picked: TestTopic[] = selected.length
      ? all.topics.filter((x) => selected.includes(x.slug))
      : all.topics;
    return picked.reduce(
      (n, x) =>
        n +
        (banks.includes("lesson") ? x.lesson_total : 0) +
        (banks.includes("exam") ? x.exam_total : 0),
      0,
    );
  }, [all, selected, banks]);

  async function run(config: { mode: MixMode; count: number }) {
    const mix = await generate.mutateAsync({
      courses: selected,
      banks,
      mode: config.mode,
      count: config.count,
    });
    const q = prepareTest(mix.questions);
    if (q.length > 0) setPrepared(q);
  }

  // ------------------------------------------------------------ run/result ---
  if (prepared) {
    return (
      <TestRunner
        prepared={prepared}
        showOrigin
        onFinish={(answers) => {
          const items = toResultItems(answers);
          if (items.length) record.mutate(items);
        }}
        // Setup and run are two phases of the same route, so leaving is a state
        // change — a link back to /tests would land on the page we're already on.
        onExit={() => setPrepared(null)}
        exitLabel={t("tests.toSetup")}
        // Retry draws a genuinely new set from the server; the old run stays on
        // screen until it lands, so the page never blinks back to setup.
        onRetry={() => void run({ mode, count })}
        onRetryMistakes={(slugs) => {
          // The missed questions are already in hand (options included) — no
          // reason to ask the server for them again.
          const only = new Set(slugs);
          setPrepared(prepared.filter((q) => only.has(q.slug)));
        }}
        saving={record.isPending}
        saveError={record.isError}
      />
    );
  }

  // ---------------------------------------------------------------- setup ---
  if (topics.isLoading) {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <SkeletonCard />
        <SkeletonCard />
      </div>
    );
  }
  if (topics.isError || !all) {
    return <p className="text-danger">{t("common.error")}</p>;
  }
  if (all.total === 0) {
    return (
      <EmptyState
        icon={<IconClipboardCheck className="h-7 w-7 text-faint" />}
        title={t("tests.empty")}
      />
    );
  }

  const busy = generate.isPending;
  const tooFew = pool === 0;

  return (
    <div className="mx-auto max-w-2xl">
      <header>
        <h1 className="font-display text-3xl font-bold tracking-tight text-ink">
          {t("tests.title")}
        </h1>
        <p className="mt-1 text-sm text-muted">
          {t("tests.subtitle", { count: all.total })}
        </p>
      </header>

      {/* One tap = a test. Everything below is for when you want to aim. */}
      <motion.div
        variants={staggerContainer}
        initial="hidden"
        animate="show"
        className="mt-6 grid gap-3 sm:grid-cols-3"
      >
        {PRESETS.map((p) => {
          const blocked = p.requires === "weak" && all.weak === 0;
          const badge =
            p.requires === "weak" && all.weak > 0 ? all.weak : undefined;
          return (
            <motion.button
              key={p.mode}
              variants={fadeInUp}
              disabled={busy || blocked}
              onClick={() => void run({ mode: p.mode, count: p.count })}
              className="group rounded-2xl border border-border bg-surface p-4 text-left shadow-card transition-[transform,box-shadow] hover:shadow-raised active:scale-[0.98] disabled:opacity-45 disabled:hover:shadow-card disabled:active:scale-100"
            >
              <div className="flex items-center justify-between">
                <span className={p.tone} aria-hidden>
                  <p.Icon className="h-6 w-6" />
                </span>
                {badge != null && (
                  <span className="rounded-full bg-accent-soft px-2 py-0.5 text-xs font-bold text-accent">
                    {badge}
                  </span>
                )}
              </div>
              <div className="mt-3 font-display text-base font-bold text-ink">
                {t(p.labelKey)}
              </div>
              <div className="mt-0.5 text-xs text-muted">{t(p.noteKey)}</div>
            </motion.button>
          );
        })}
      </motion.div>

      {/* ------------------------------------------------------- custom run --- */}
      <motion.section
        variants={fade}
        initial="hidden"
        animate="show"
        className="mt-8 rounded-2xl border border-border bg-surface p-5 shadow-card"
      >
        <h2 className="font-display text-lg font-bold text-ink">
          {t("tests.customTitle")}
        </h2>

        <div className="mt-5 space-y-5">
          <div>
            <div className="mb-2 text-xs font-bold uppercase tracking-wide text-faint">
              {t("tests.count")}
            </div>
            <Segmented
              label={t("tests.count")}
              value={count}
              onChange={setCount}
              options={COUNTS.map((c) => ({ value: c, label: String(c) }))}
            />
          </div>

          <div>
            <div className="mb-2 text-xs font-bold uppercase tracking-wide text-faint">
              {t("tests.mode")}
            </div>
            <Segmented
              label={t("tests.mode")}
              value={mode}
              onChange={setMode}
              options={[
                { value: "smart" as MixMode, label: t("tests.modeSmart") },
                { value: "random" as MixMode, label: t("tests.modeRandom") },
                { value: "weak" as MixMode, label: t("tests.modeWeak") },
                { value: "mistakes" as MixMode, label: t("tests.modeMistakes") },
              ]}
            />
            <p className="mt-2 text-xs text-faint">{t(`tests.modeHint.${mode}`)}</p>
          </div>

          {hasExam && (
            <div>
              <div className="mb-2 text-xs font-bold uppercase tracking-wide text-faint">
                {t("tests.source")}
              </div>
              <div className="flex flex-wrap gap-2">
                {(["lesson", "exam"] as MixBank[]).map((b) => {
                  const on = banks.includes(b);
                  return (
                    <button
                      key={b}
                      aria-pressed={on}
                      onClick={() =>
                        setBanks((prev) => {
                          const next = on
                            ? prev.filter((x) => x !== b)
                            : [...prev, b];
                          return next.length ? next : prev; // never empty
                        })
                      }
                      className={`rounded-full border px-3 py-1.5 text-sm font-semibold transition-colors ${
                        on
                          ? "border-primary/40 bg-primary-soft text-primary"
                          : "border-border bg-surface text-muted hover:bg-surface-2"
                      }`}
                    >
                      {t(`tests.source_${b}`)}
                      <span className="ml-1.5 text-xs font-bold opacity-60">
                        {b === "lesson" ? all.lesson_total : all.exam_total}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          <div>
            <div className="mb-2 flex items-center justify-between gap-3">
              <span className="text-xs font-bold uppercase tracking-wide text-faint">
                {t("tests.topics")}
              </span>
              {selected.length > 0 && (
                <button
                  onClick={() => setSelected([])}
                  className="text-xs font-semibold text-primary hover:underline"
                >
                  {t("tests.allTopics")}
                </button>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              {all.topics.map((topic) => {
                const on = selected.includes(topic.slug);
                return (
                  <button
                    key={topic.slug}
                    aria-pressed={on}
                    onClick={() =>
                      setSelected((prev) =>
                        on
                          ? prev.filter((s) => s !== topic.slug)
                          : [...prev, topic.slug],
                      )
                    }
                    className={`rounded-full border px-3 py-1.5 text-sm font-medium transition-colors ${
                      on
                        ? "border-primary/40 bg-primary-soft text-primary"
                        : "border-border bg-surface text-muted hover:bg-surface-2"
                    }`}
                  >
                    {topic.title}
                    <span className="ml-1.5 text-xs font-bold opacity-60">
                      {topic.total}
                    </span>
                  </button>
                );
              })}
            </div>
            <p className="mt-2 text-xs text-faint">
              {selected.length === 0
                ? t("tests.allTopicsHint")
                : t("tests.selectedHint", { count: selected.length })}
            </p>
          </div>
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-border pt-5">
          <Button
            onClick={() => void run({ mode, count })}
            loading={busy}
            disabled={tooFew}
            className="sm:px-8"
          >
            {t("tests.start")} →
          </Button>
          <span className="text-sm text-muted">
            {tooFew
              ? t("tests.poolEmpty")
              : t("tests.poolInfo", { count: Math.min(count, pool), pool })}
          </span>
        </div>
        {generate.isError && (
          <p className="mt-3 text-sm text-danger">{t("common.error")}</p>
        )}
      </motion.section>
    </div>
  );
}
