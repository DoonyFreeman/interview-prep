import { Link, NavLink, Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "../auth/AuthContext";
import { useProgress } from "../api/hooks";
import { LanguageToggle } from "./LanguageToggle";
import { ThemeToggle } from "./ThemeToggle";

function DueBadge() {
  const { t } = useTranslation();
  const { data } = useProgress();
  const due = data?.due_concepts ?? 0;
  return (
    <NavLink
      to="/review"
      className={({ isActive }) =>
        `inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold transition-colors ${
          isActive
            ? "border-primary/40 bg-primary-soft text-primary"
            : "border-border bg-surface text-muted hover:bg-surface-2"
        }`
      }
    >
      <span className={due > 0 ? "text-accent" : "text-faint"}>●</span>
      {t("nav.review")}: <span className="text-ink">{due}</span>
    </NavLink>
  );
}

export function Layout() {
  const { t } = useTranslation();
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-border bg-bg/80 backdrop-blur">
        <div className="mx-auto flex h-15 max-w-6xl items-center gap-4 px-4 py-3">
          <Link to="/" className="flex items-center gap-2 font-bold text-ink">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary text-sm text-primary-fg">
              ip
            </span>
            <span className="hidden sm:inline">{t("app.name")}</span>
          </Link>

          <nav className="ml-2 flex items-center gap-1">
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                `rounded-lg px-3 py-1.5 text-sm font-semibold transition-colors ${
                  isActive
                    ? "bg-primary-soft text-primary"
                    : "text-muted hover:text-ink"
                }`
              }
            >
              {t("nav.courses")}
            </NavLink>
            <NavLink
              to="/glossary"
              className={({ isActive }) =>
                `rounded-lg px-3 py-1.5 text-sm font-semibold transition-colors ${
                  isActive
                    ? "bg-primary-soft text-primary"
                    : "text-muted hover:text-ink"
                }`
              }
            >
              {t("nav.glossary")}
            </NavLink>
          </nav>

          <div className="ml-auto flex items-center gap-3">
            <div className="hidden sm:block">
              <DueBadge />
            </div>
            <ThemeToggle />
            <LanguageToggle />
            <div className="flex items-center gap-1">
              <NavLink
                to="/settings"
                title={t("nav.settings")}
                className={({ isActive }) =>
                  `flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-sm font-semibold transition-colors ${
                    isActive
                      ? "bg-primary-soft text-primary"
                      : "text-muted hover:bg-surface-2 hover:text-ink"
                  }`
                }
              >
                <span aria-hidden>⚙</span>
                <span className="hidden max-w-[150px] truncate md:inline">
                  {user?.display_name || user?.email}
                </span>
              </NavLink>
              <button
                onClick={logout}
                className="rounded-lg px-2.5 py-1.5 text-sm font-semibold text-muted transition-colors hover:bg-surface-2 hover:text-ink"
              >
                {t("nav.logout")}
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
