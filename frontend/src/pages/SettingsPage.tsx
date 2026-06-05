import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../auth/AuthContext";
import { useChangePassword, useUpdateProfile } from "../api/hooks";
import { apiErrorMessage } from "../lib/api";
import { Button } from "../components/Button";
import { Spinner, PageLoader } from "../components/Spinner";
import { LanguageToggle } from "../components/LanguageToggle";

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-border bg-surface p-5 shadow-sm sm:p-6">
      <h2 className="mb-4 text-base font-bold text-ink">{title}</h2>
      {children}
    </section>
  );
}

const inputCls =
  "w-full rounded-xl border border-border bg-surface-2 px-3 py-2.5 text-sm outline-none focus:border-primary";
const labelCls = "mb-1 block text-xs font-semibold text-muted";

export function SettingsPage() {
  const { t, i18n } = useTranslation();
  const { user, logout } = useAuth();

  const updateProfile = useUpdateProfile();
  const changePassword = useChangePassword();

  const [name, setName] = useState(user?.display_name ?? "");
  const [profileSaved, setProfileSaved] = useState(false);

  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [pwError, setPwError] = useState<string | null>(null);
  const [pwSaved, setPwSaved] = useState(false);

  if (!user) return <PageLoader />;

  const since = new Date(user.created_at).toLocaleDateString(
    i18n.resolvedLanguage,
    { year: "numeric", month: "long", day: "numeric" },
  );

  async function saveProfile(e: React.FormEvent) {
    e.preventDefault();
    setProfileSaved(false);
    await updateProfile.mutateAsync({ display_name: name });
    setProfileSaved(true);
  }

  async function savePassword(e: React.FormEvent) {
    e.preventDefault();
    setPwError(null);
    setPwSaved(false);
    try {
      await changePassword.mutateAsync({
        current_password: currentPw,
        new_password: newPw,
      });
      setPwSaved(true);
      setCurrentPw("");
      setNewPw("");
    } catch (err) {
      setPwError(apiErrorMessage(err, t("common.error")));
    }
  }

  return (
    <div className="mx-auto max-w-xl">
      <h1 className="mb-6 text-2xl font-bold text-ink">{t("settings.title")}</h1>

      <div className="space-y-5">
        {/* Profile */}
        <Section title={t("settings.profile")}>
          <form onSubmit={saveProfile} className="space-y-4">
            <div>
              <span className={labelCls}>{t("settings.email")}</span>
              <input value={user.email} disabled className={`${inputCls} opacity-60`} />
              <p className="mt-1 text-xs text-faint">{t("settings.emailReadonly")}</p>
            </div>
            <label className="block">
              <span className={labelCls}>{t("settings.displayName")}</span>
              <input
                value={name}
                onChange={(e) => {
                  setName(e.target.value);
                  setProfileSaved(false);
                }}
                className={inputCls}
              />
            </label>
            <div className="flex items-center gap-3">
              <Button type="submit" disabled={updateProfile.isPending}>
                {updateProfile.isPending && <Spinner />}
                {t("settings.save")}
              </Button>
              {profileSaved && (
                <span className="text-sm font-medium text-success">
                  ✓ {t("settings.saved")}
                </span>
              )}
            </div>
            <p className="text-xs text-faint">
              {t("settings.memberSince", { date: since })}
            </p>
          </form>
        </Section>

        {/* Password */}
        <Section title={t("settings.password")}>
          <form onSubmit={savePassword} className="space-y-4">
            <label className="block">
              <span className={labelCls}>{t("settings.currentPassword")}</span>
              <input
                type="password"
                required
                value={currentPw}
                onChange={(e) => setCurrentPw(e.target.value)}
                className={inputCls}
              />
            </label>
            <label className="block">
              <span className={labelCls}>{t("settings.newPassword")}</span>
              <input
                type="password"
                required
                minLength={6}
                value={newPw}
                onChange={(e) => setNewPw(e.target.value)}
                className={inputCls}
              />
              <p className="mt-1 text-xs text-faint">{t("auth.passwordHint")}</p>
            </label>
            {pwError && (
              <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">
                {pwError}
              </p>
            )}
            <div className="flex items-center gap-3">
              <Button type="submit" disabled={changePassword.isPending}>
                {changePassword.isPending && <Spinner />}
                {t("settings.changePassword")}
              </Button>
              {pwSaved && (
                <span className="text-sm font-medium text-success">
                  ✓ {t("settings.passwordChanged")}
                </span>
              )}
            </div>
          </form>
        </Section>

        {/* Language */}
        <Section title={t("settings.language")}>
          <LanguageToggle />
        </Section>

        {/* Account */}
        <Section title={t("settings.account")}>
          <Button variant="secondary" onClick={logout}>
            {t("settings.logout")}
          </Button>
        </Section>
      </div>
    </div>
  );
}
