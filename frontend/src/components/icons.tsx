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
