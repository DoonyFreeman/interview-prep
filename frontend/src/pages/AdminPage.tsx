import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "../auth/AuthContext";
import {
  useAdminUpdatePet,
  useAdminUser,
  useAdminUsers,
} from "../api/hooks";
import type { AdminUser, PetState } from "../api/types";
import { apiErrorMessage } from "../lib/api";
import { HAT_MILESTONES, SKIN_MILESTONES } from "../lib/cat";
import { Button } from "../components/Button";
import { PageLoader } from "../components/Spinner";
import { useToast } from "../components/Toast";

const inputCls =
  "w-full rounded-xl border border-border bg-surface-2 px-3 py-2.5 text-sm outline-none transition-colors focus:border-primary";
const labelCls = "mb-1 block text-xs font-semibold text-muted";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-surface-2 px-3 py-2">
      <div className="text-[11px] font-semibold text-muted">{label}</div>
      <div className="text-sm font-bold text-ink">{value}</div>
    </div>
  );
}

/** Editable pet card — admin writes bypass the unlock clamp server-side. */
function PetEditor({ userId, pet }: { userId: number; pet: PetState }) {
  const { t } = useTranslation();
  const toast = useToast();
  const update = useAdminUpdatePet();

  const [name, setName] = useState(pet.name);
  const [streak, setStreak] = useState(String(pet.streak));
  const [best, setBest] = useState(String(pet.best_streak));
  const [lastActive, setLastActive] = useState(pet.last_active_day ?? "");
  const [skin, setSkin] = useState(pet.skin);
  const [hat, setHat] = useState(pet.hat ?? "");

  useEffect(() => {
    setName(pet.name);
    setStreak(String(pet.streak));
    setBest(String(pet.best_streak));
    setLastActive(pet.last_active_day ?? "");
    setSkin(pet.skin);
    setHat(pet.hat ?? "");
  }, [pet]);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    try {
      await update.mutateAsync({
        userId,
        patch: {
          name,
          streak: Math.max(0, Number(streak) || 0),
          best_streak: Math.max(0, Number(best) || 0),
          last_active_day: lastActive || null,
          skin,
          hat: hat || null,
        },
      });
      toast.success(t("admin.saved"));
    } catch (err) {
      toast.error(apiErrorMessage(err, t("common.error")));
    }
  }

  return (
    <form onSubmit={save} className="space-y-3">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <label className="col-span-2 block sm:col-span-1">
          <span className={labelCls}>{t("settings.petName")}</span>
          <input value={name} maxLength={40} onChange={(e) => setName(e.target.value)} className={inputCls} />
        </label>
        <label className="block">
          <span className={labelCls}>{t("admin.petStreak")}</span>
          <input type="number" min={0} value={streak} onChange={(e) => setStreak(e.target.value)} className={inputCls} />
        </label>
        <label className="block">
          <span className={labelCls}>{t("admin.petBest")}</span>
          <input type="number" min={0} value={best} onChange={(e) => setBest(e.target.value)} className={inputCls} />
        </label>
        <label className="block">
          <span className={labelCls}>{t("admin.petLastActive")}</span>
          <input type="date" value={lastActive} onChange={(e) => setLastActive(e.target.value)} className={inputCls} />
        </label>
        <label className="block">
          <span className={labelCls}>{t("settings.petSkin")}</span>
          <select value={skin} onChange={(e) => setSkin(e.target.value)} className={inputCls}>
            {SKIN_MILESTONES.map(({ skin: s }) => (
              <option key={s} value={s}>
                {t(`cat.skins.${s}`)}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className={labelCls}>{t("settings.petHat")}</span>
          <select value={hat} onChange={(e) => setHat(e.target.value)} className={inputCls}>
            <option value="">—</option>
            {HAT_MILESTONES.map(({ hat: h }) => (
              <option key={h} value={h}>
                {t(`cat.hats.${h}`)}
              </option>
            ))}
          </select>
        </label>
      </div>
      <Button type="submit" loading={update.isPending}>
        {t("settings.save")}
      </Button>
    </form>
  );
}

/** Per-course lesson breakdown + pet editor for one user. */
function UserDetail({ userId }: { userId: number }) {
  const { t } = useTranslation();
  const { data, isLoading } = useAdminUser(userId);

  if (isLoading || !data) return <PageLoader />;

  const testsByCourse = new Map(data.tests.courses.map((c) => [c.slug, c]));

  return (
    <div className="space-y-4">
      <div>
        <h3 className="mb-2 font-display text-sm font-bold text-ink">
          {t("admin.petTitle")}
        </h3>
        <PetEditor userId={userId} pet={data.user.pet} />
      </div>

      <div>
        <h3 className="mb-2 font-display text-sm font-bold text-ink">
          {t("admin.progressTitle")}
        </h3>
        <div className="space-y-1.5">
          {data.progress.courses.map((course) => {
            const done = course.lessons.filter((l) => l.completed).length;
            const tests = testsByCourse.get(course.slug);
            const idle = done === 0 && course.attempted_concepts === 0;
            return (
              <details
                key={course.slug}
                className={`rounded-xl border border-border bg-surface-2 ${idle ? "opacity-60" : ""}`}
              >
                <summary className="flex cursor-pointer flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 text-sm">
                  <span className="font-semibold text-ink">{course.title}</span>
                  <span className="ml-auto flex items-center gap-3 text-xs text-muted">
                    <span>
                      {t("admin.lessons")} {done}/{course.lessons.length}
                    </span>
                    <span>
                      {t("admin.concepts")} {course.mastered_concepts}/
                      {course.total_concepts}
                    </span>
                    {tests && (
                      <span>
                        {t("admin.tests")} {tests.passed}/{tests.total}
                      </span>
                    )}
                  </span>
                </summary>
                <ul className="space-y-1 px-3 pb-2.5">
                  {course.lessons.map((lesson) => (
                    <li
                      key={lesson.slug}
                      className="flex items-center gap-2 text-xs text-muted"
                    >
                      <span
                        className={
                          lesson.completed ? "text-accent" : "text-border"
                        }
                        aria-hidden
                      >
                        {lesson.completed ? "✓" : "○"}
                      </span>
                      <span className={lesson.completed ? "text-ink" : ""}>
                        {lesson.title}
                      </span>
                      <span className="ml-auto tabular-nums">
                        {lesson.mastered_concepts}/{lesson.total_concepts}
                      </span>
                    </li>
                  ))}
                </ul>
              </details>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function UserRow({
  u,
  open,
  onToggle,
}: {
  u: AdminUser;
  open: boolean;
  onToggle: () => void;
}) {
  const { t, i18n } = useTranslation();
  const lastActive = u.pet.last_active_day
    ? new Date(u.pet.last_active_day).toLocaleDateString(i18n.resolvedLanguage)
    : t("admin.never");

  return (
    <div className="rounded-2xl border border-border bg-surface shadow-card">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full flex-wrap items-baseline gap-x-3 gap-y-0.5 px-4 py-3 text-left"
      >
        <span className="font-display text-sm font-bold text-ink">
          {u.display_name || u.email}
        </span>
        <span className="text-xs text-muted">{u.email}</span>
        <span className="ml-auto text-xs text-muted">
          🔥 {u.pet.streak} · {t("settings.petBest", { count: u.pet.best_streak })}{" "}
          · {lastActive}
        </span>
      </button>
      <div className="grid grid-cols-2 gap-2 px-4 pb-3 sm:grid-cols-5">
        <Stat
          label={t("admin.lessons")}
          value={`${u.completed_lessons}/${u.total_lessons}`}
        />
        <Stat
          label={t("admin.concepts")}
          value={`${u.mastered_concepts}/${u.total_concepts}`}
        />
        <Stat
          label={t("admin.tests")}
          value={`${u.tests_passed}/${u.tests_total}`}
        />
        <Stat label={t("admin.attempts")} value={String(u.attempts_count)} />
        <Stat label={t("admin.avgScore")} value={String(u.avg_score)} />
      </div>
      {open && (
        <div className="border-t border-border px-4 py-4">
          <UserDetail userId={u.id} />
        </div>
      )}
    </div>
  );
}

export function AdminPage() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const isAdmin = user?.is_admin ?? false;
  const { data, isLoading } = useAdminUsers(isAdmin);
  const [openId, setOpenId] = useState<number | null>(null);

  if (user && !isAdmin) return <Navigate to="/" replace />;
  if (isLoading || !data) return <PageLoader />;

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-1 font-display text-2xl font-bold tracking-tight text-ink">
        {t("admin.title")}
      </h1>
      <p className="mb-6 text-sm text-muted">
        {t("admin.subtitle", { count: data.users.length })}
      </p>
      <div className="space-y-3">
        {data.users.map((u) => (
          <UserRow
            key={u.id}
            u={u}
            open={openId === u.id}
            onToggle={() => setOpenId(openId === u.id ? null : u.id)}
          />
        ))}
      </div>
    </div>
  );
}
