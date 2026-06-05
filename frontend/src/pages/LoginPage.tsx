import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useLogin, useRegister } from "../api/hooks";
import { apiErrorMessage } from "../lib/api";
import { Button } from "../components/Button";
import { Spinner } from "../components/Spinner";
import { LanguageToggle } from "../components/LanguageToggle";

export function LoginPage() {
  const { t } = useTranslation();
  const { login, token } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? "/";

  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const loginM = useLogin();
  const registerM = useRegister();
  const pending = loginM.isPending || registerM.isPending;

  if (token) {
    navigate(from, { replace: true });
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const data =
        mode === "login"
          ? await loginM.mutateAsync({ email, password })
          : await registerM.mutateAsync({
              email,
              password,
              display_name: displayName,
            });
      login(data.access_token);
      navigate(from, { replace: true });
    } catch (err) {
      setError(apiErrorMessage(err, t("common.error")));
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <div className="flex justify-end p-4">
        <LanguageToggle />
      </div>
      <div className="flex flex-1 items-center justify-center px-4 pb-20">
        <div className="w-full max-w-sm">
          <div className="mb-6 text-center">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-primary text-lg font-bold text-primary-fg">
              ip
            </div>
            <h1 className="text-xl font-bold text-ink">{t("app.name")}</h1>
            <p className="mt-1 text-sm text-muted">{t("auth.subtitle")}</p>
          </div>

          <form
            onSubmit={submit}
            className="rounded-2xl border border-border bg-surface p-6 shadow-sm"
          >
            <h2 className="mb-4 text-base font-bold text-ink">
              {mode === "login" ? t("auth.loginTitle") : t("auth.registerTitle")}
            </h2>

            <label className="mb-3 block">
              <span className="mb-1 block text-xs font-semibold text-muted">
                {t("auth.email")}
              </span>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-xl border border-border bg-surface-2 px-3 py-2.5 text-sm outline-none focus:border-primary"
              />
            </label>

            {mode === "register" && (
              <label className="mb-3 block">
                <span className="mb-1 block text-xs font-semibold text-muted">
                  {t("auth.displayName")}
                </span>
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  className="w-full rounded-xl border border-border bg-surface-2 px-3 py-2.5 text-sm outline-none focus:border-primary"
                />
              </label>
            )}

            <label className="mb-1 block">
              <span className="mb-1 block text-xs font-semibold text-muted">
                {t("auth.password")}
              </span>
              <input
                type="password"
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-xl border border-border bg-surface-2 px-3 py-2.5 text-sm outline-none focus:border-primary"
              />
            </label>
            <p className="mb-4 text-xs text-faint">{t("auth.passwordHint")}</p>

            {error && (
              <p className="mb-3 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">
                {error}
              </p>
            )}

            <Button type="submit" disabled={pending} className="w-full">
              {pending && <Spinner />}
              {mode === "login" ? t("auth.loginBtn") : t("auth.registerBtn")}
            </Button>

            <button
              type="button"
              onClick={() => {
                setMode(mode === "login" ? "register" : "login");
                setError(null);
              }}
              className="mt-4 w-full text-center text-sm font-medium text-primary hover:underline"
            >
              {mode === "login" ? t("auth.toRegister") : t("auth.toLogin")}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
