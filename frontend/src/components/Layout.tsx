import { Link, NavLink, useLocation, useOutlet } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useAuth } from "../auth/AuthContext";
import { useProgress } from "../api/hooks";
import { useCat } from "../cat/useCat";
import { LanguageToggle } from "./LanguageToggle";
import { ThemeToggle } from "./ThemeToggle";
import { ShortcutsHelp } from "./ShortcutsHelp";
import { SearchModal } from "./SearchModal";
import { BottomNavBar } from "./BottomNavBar";
import { WhatsNew } from "./WhatsNew";
import { CatWidget } from "../cat/CatWidget";
import { BrandMark, BrandWord, IconFlame, IconSettings } from "./icons";
import { routeTransition } from "../lib/motion";

/** A desktop nav link with an animated "pill" that glides to the active item. */
function NavItem({ to, end, label }: { to: string; end?: boolean; label: string }) {
  return (
    <NavLink to={to} end={end} className="relative px-3 py-1.5 text-sm font-semibold">
      {({ isActive }) => (
        <>
          {isActive && (
            <motion.span
              layoutId="nav-pill"
              className="absolute inset-0 rounded-lg bg-primary-soft"
              transition={{ type: "spring", stiffness: 480, damping: 38 }}
            />
          )}
          <span
            className={`relative transition-colors ${
              isActive ? "text-primary" : "text-muted hover:text-ink"
            }`}
          >
            {label}
          </span>
        </>
      )}
    </NavLink>
  );
}

/** Single "to review" indicator — accent when due, calm when clear. */
function DueBadge() {
  const { t } = useTranslation();
  const { data } = useProgress();
  const due = data?.due_concepts ?? 0;
  const hot = due > 0;
  return (
    <NavLink
      to="/review"
      className={({ isActive }) =>
        `inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border px-3 py-1 text-xs font-semibold transition-colors ${
          isActive
            ? "border-primary/40 bg-primary-soft text-primary"
            : hot
              ? "border-accent/40 bg-accent-soft text-accent"
              : "border-border bg-surface text-muted hover:bg-surface-2"
        }`
      }
    >
      <span
        className={`inline-block h-1.5 w-1.5 rounded-full ${
          hot ? "bg-accent" : "bg-faint"
        }`}
      />
      {t("nav.review")}
      <span className={hot ? "text-accent" : "text-faint"}>{due}</span>
    </NavLink>
  );
}

/** A streak flame — quiet motivation, shown only when there's an active run. */
function StreakBadge() {
  const { t } = useTranslation();
  const { pet, loaded } = useCat();
  const reduce = useReducedMotion();
  if (!loaded || pet.hidden || pet.streak <= 0) return null;
  return (
    <span
      title={t("cat.streakDays", { count: pet.streak })}
      className="inline-flex shrink-0 items-center gap-1 rounded-full border border-accent/30 bg-accent-soft px-2.5 py-1 text-xs font-bold text-accent"
    >
      {/* A slow flicker, not a loop that demands attention — the streak should
          register in peripheral vision and then get out of the way. */}
      <motion.span
        aria-hidden
        className="inline-flex"
        animate={reduce ? {} : { scale: [1, 1.15, 0.97, 1], opacity: [1, 0.8, 1] }}
        transition={{ duration: 2.6, repeat: Infinity, ease: "easeInOut" }}
      >
        <IconFlame className="h-3.5 w-3.5" />
      </motion.span>
      {pet.streak}
    </span>
  );
}

export function Layout() {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const location = useLocation();
  const outlet = useOutlet();

  // Glossary and Slang live in one shared shell (DictLayout); collapse them to
  // a single transition key so switching tabs doesn't replay the page fade —
  // the shell stays mounted and only its inner list swaps.
  const path = location.pathname;
  const transitionKey =
    path === "/glossary" || path === "/slang" ? "dict-section" : path;

  return (
    <div className="min-h-screen">
      <header className="glass sticky top-0 z-20 border-b border-border">
        <div className="mx-auto flex h-15 max-w-6xl items-center gap-4 px-4">
          {/* Logo lockup: glyph always, wordmark from sm up (the phone header is
              already tight). Both are transparent SVGs — no wrapper chip. */}
          <Link to="/" className="flex items-center gap-2" aria-label={t("app.name")}>
            <BrandMark className="h-9 w-9 shrink-0" />
            <BrandWord className="hidden h-5 w-auto sm:block" />
          </Link>

          <nav className="ml-2 hidden items-center gap-1 sm:flex">
            <NavItem to="/" end label={t("nav.courses")} />
            <NavItem to="/roadmap" label={t("nav.roadmap")} />
            <NavItem to="/glossary" label={t("nav.glossary")} />
            <NavItem to="/tests" label={t("nav.tests")} />
            <NavItem to="/progress" label={t("nav.progress")} />
          </nav>

          <div className="ml-auto flex items-center gap-2 sm:gap-3">
            <StreakBadge />
            <div className="hidden sm:block">
              <DueBadge />
            </div>
            <SearchModal />
            <ShortcutsHelp />
            <ThemeToggle />
            <LanguageToggle />
            <NavLink
              to="/settings"
              title={t("nav.settings")}
              className={({ isActive }) =>
                `group flex items-center gap-2 rounded-[10px] px-2.5 py-1.5 text-sm font-semibold transition-colors ${
                  isActive
                    ? "bg-primary-soft text-primary"
                    : "text-muted hover:bg-surface-2 hover:text-ink"
                }`
              }
            >
              {/* The gear turns a quarter on hover — the one place a literal
                  "settings" metaphor can afford to be playful. Driven by the
                  link's `group` so it reacts to the whole target, not just the
                  16px icon; plain CSS, so the global reduced-motion reset
                  already flattens it. */}
              <span
                aria-hidden
                className="inline-flex transition-transform duration-300 ease-out group-hover:rotate-90"
              >
                <IconSettings className="h-4 w-4" />
              </span>
              <span className="hidden max-w-[150px] truncate md:inline">
                {user?.display_name || user?.email}
              </span>
            </NavLink>
            <button
              onClick={logout}
              className="hidden rounded-lg px-2.5 py-1.5 text-sm font-semibold text-muted transition-colors hover:bg-surface-2 hover:text-ink sm:block"
            >
              {t("nav.logout")}
            </button>
          </div>
        </div>
      </header>

      {/* Bottom padding clears the floating tab-bar island (56px tall, 8px off
          the safe area) plus breathing room — content scrolls *under* it. */}
      <main className="mx-auto max-w-6xl px-4 pb-[calc(6rem+env(safe-area-inset-bottom))] pt-8 sm:pb-12">
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={transitionKey}
            variants={routeTransition}
            initial="hidden"
            animate="show"
            exit="exit"
          >
            {outlet}
          </motion.div>
        </AnimatePresence>
      </main>

      <BottomNavBar />
      <CatWidget />
      <WhatsNew />
    </div>
  );
}
