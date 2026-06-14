// Minimal stroke icons in the lucide visual style (24×24, currentColor,
// stroke-width 2, round caps/joins). No external dependency — a handful of
// inline SVGs is lighter than pulling in an icon library.

type IconProps = {
  className?: string;
};

function Svg({
  className,
  children,
}: IconProps & { children: React.ReactNode }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

/** Courses — graduation cap (academic / learning a topic). */
export function IconCourses({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M22 10 12 5 2 10l10 5 10-5z" />
      <path d="M6 12v5c0 1 2.5 3 6 3s6-2 6-3v-5" />
      <path d="M22 10v6" />
    </Svg>
  );
}

/** Glossary — a closed reference book (dictionary). */
export function IconGlossary({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
    </Svg>
  );
}

/** Slang — a speech bubble (everyday spoken jargon). */
export function IconSlang({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </Svg>
  );
}

/** Progress — a bar chart. */
export function IconProgress({ className }: IconProps) {
  return (
    <Svg className={className}>
      <line x1="18" y1="20" x2="18" y2="10" />
      <line x1="12" y1="20" x2="12" y2="4" />
      <line x1="6" y1="20" x2="6" y2="14" />
    </Svg>
  );
}

/** Profile / settings — a person. */
export function IconUser({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </Svg>
  );
}

/** AI interview — a microphone. */
export function IconMic({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="22" />
    </Svg>
  );
}

/** Lesson test — a clipboard with a checkmark. */
export function IconClipboardCheck({ className }: IconProps) {
  return (
    <Svg className={className}>
      <rect x="8" y="2" width="8" height="4" rx="1" ry="1" />
      <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
      <path d="m9 14 2 2 4-4" />
    </Svg>
  );
}

/** Quiz — a target. */
export function IconTarget({ className }: IconProps) {
  return (
    <Svg className={className}>
      <circle cx="12" cy="12" r="10" />
      <circle cx="12" cy="12" r="6" />
      <circle cx="12" cy="12" r="2" />
    </Svg>
  );
}

/** Retry — a counter-clockwise arrow. */
export function IconRefresh({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
      <path d="M3 3v5h5" />
    </Svg>
  );
}

/** Search — a magnifier. */
export function IconSearch({ className }: IconProps) {
  return (
    <Svg className={className}>
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.3-4.3" />
    </Svg>
  );
}

/** Reward — sparkles (perfect result). */
export function IconSparkles({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M12 3 13.9 8.6 19.5 10.5 13.9 12.4 12 18 10.1 12.4 4.5 10.5 10.1 8.6z" />
      <path d="M19 15v4" />
      <path d="M21 17h-4" />
    </Svg>
  );
}

/**
 * Brand glyph — a rising "mastery" curve to a sparkle at the apex. Matches the
 * app icon (`public/favicon.svg`). Drawn on a solid primary tile by the caller;
 * the curve is stroked and the sparkle filled, both in `currentColor`.
 */
export function BrandMark({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M4 17.5 L9.5 11.5 L13 14.5 L18.5 8.5"
        stroke="currentColor"
        strokeWidth={2.3}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M18.5 5.5 L19.6 7.4 L21.5 8.5 L19.6 9.6 L18.5 11.5 L17.4 9.6 L15.5 8.5 L17.4 7.4 Z"
        fill="currentColor"
      />
    </svg>
  );
}
