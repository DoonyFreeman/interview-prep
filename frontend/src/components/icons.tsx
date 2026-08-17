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

/** Copy — two stacked sheets (copy to clipboard). */
export function IconCopy({ className }: IconProps) {
  return (
    <Svg className={className}>
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </Svg>
  );
}

/** Check — a bare checkmark (copied / done). */
export function IconCheck({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M20 6 9 17l-5-5" />
    </Svg>
  );
}

/** Keyboard — for the shortcuts helper. */
export function IconKeyboard({ className }: IconProps) {
  return (
    <Svg className={className}>
      <rect x="2" y="6" width="20" height="12" rx="2" ry="2" />
      <path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M8 14h8" />
    </Svg>
  );
}

/**
 * Brand glyph — the iprep snake, whose body forms a terminal `>` and whose tail
 * becomes the underscore. Transparent by design (no tile), and self-coloured in
 * the brand violet, so it reads on both themes without a wrapper.
 * `public/favicon.svg` is the same drawing on a light tile — a bare icon turns
 * to mush against arbitrary browser-tab chrome.
 */
export function BrandMark({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox="0 0 240 240"
      fill="none"
      aria-hidden="true"
    >
      <defs>
        <linearGradient
          id="iprep-icon-grad"
          x1="29"
          y1="23"
          x2="211"
          y2="222"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset="0" stopColor="#9B7CFF" />
          <stop offset="0.48" stopColor="#7651E8" />
          <stop offset="1" stopColor="#4B218E" />
        </linearGradient>
      </defs>

      <path
        d="M55 48 C73 32 101 31 121 45 L178 95 C197 112 197 139 178 156 L116 209"
        fill="none"
        stroke="url(#iprep-icon-grad)"
        strokeWidth={42}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M178 156 L117 103 C105 93 90 89 75 92"
        fill="none"
        stroke="url(#iprep-icon-grad)"
        strokeWidth={42}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M151 211 H211"
        fill="none"
        stroke="#4B218E"
        strokeWidth={20}
        strokeLinecap="round"
      />

      <circle cx="72" cy="44" r="6" fill="#24103F" />
      <path
        d="M55 59 C62 66 73 68 82 63"
        fill="none"
        stroke="#24103F"
        strokeWidth={4.5}
        strokeLinecap="round"
      />
      <path
        d="M47 45 L37 40"
        fill="none"
        stroke="#9B7CFF"
        strokeWidth={4.5}
        strokeLinecap="round"
      />

      <circle cx="123" cy="73" r="4.5" fill="#CDBEFF" opacity="0.8" />
      <circle cx="157" cy="103" r="4.5" fill="#CDBEFF" opacity="0.65" />
      <circle cx="125" cy="157" r="4.5" fill="#CDBEFF" opacity="0.55" />
    </svg>
  );
}

/** The "iprep_" wordmark. Ink comes from --logo-word-* so it flips with theme. */
export function BrandWord({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox="282 58 606 184"
      fill="none"
      role="img"
      aria-label="iprep"
    >
      <defs>
        <linearGradient
          id="iprep-word-grad"
          x1="294"
          y1="68"
          x2="888"
          y2="202"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset="0" stopColor="var(--logo-word-a)" />
          <stop offset="1" stopColor="var(--logo-word-b)" />
        </linearGradient>
      </defs>
      <g
        fill="none"
        stroke="url(#iprep-word-grad)"
        strokeWidth={22}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M300 112 V190" />
        <circle cx="300" cy="78" r="11" fill="#7651E8" stroke="none" />
        <path d="M356 112 V218" />
        <path d="M357 126 C371 111 396 107 413 119 C430 131 431 160 416 175 C401 190 373 187 357 173" />
        <path d="M470 112 V190" />
        <path d="M471 135 C482 117 500 110 521 115" />
        <path d="M574 153 H648 C647 127 630 111 607 111 C580 111 563 130 563 152 C563 176 582 192 609 192 C625 192 638 187 648 178" />
        <path d="M703 112 V218" />
        <path d="M704 126 C718 111 743 107 760 119 C777 131 778 160 763 175 C748 190 720 187 704 173" />
      </g>
      <path
        d="M813 190 H871"
        fill="none"
        stroke="#7651E8"
        strokeWidth={14}
        strokeLinecap="round"
      />
    </svg>
  );
}

/** Roadmap — a winding route between two milestones. */
export function IconRoadmap({ className }: IconProps) {
  return (
    <Svg className={className}>
      <circle cx="6" cy="19" r="3" />
      <circle cx="18" cy="5" r="3" />
      <path d="M12 19h4.5a3.5 3.5 0 0 0 0-7h-9a3.5 3.5 0 0 1 0-7H11" />
    </Svg>
  );
}

/** Video resource — a play button in a frame. */
export function IconVideo({ className }: IconProps) {
  return (
    <Svg className={className}>
      <rect x="2" y="4" width="20" height="16" rx="2" />
      <path d="m10 9 5 3-5 3z" />
    </Svg>
  );
}

/** Article resource — a text document. */
export function IconArticle({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
      <path d="M8 13h8M8 17h5" />
    </Svg>
  );
}

/** Docs resource — an open book (official documentation). */
export function IconDocs({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M2 4h6a4 4 0 0 1 4 4v12a3 3 0 0 0-3-3H2z" />
      <path d="M22 4h-6a4 4 0 0 0-4 4v12a3 3 0 0 1 3-3h7z" />
    </Svg>
  );
}

/* ------------------------------------------------------------------ */
/* Header-cluster + cat-burst icons. These replace raw emoji and text
   glyphs (🔥 ⚙ ☀ ☾ 🐾 ❤️ ⭐ 🎵), which rendered at the mercy of the
   platform emoji font — inconsistent weight, size, baseline and colour
   next to the stroked lucide set, and impossible to tint or animate.   */
/* ------------------------------------------------------------------ */

/** Streak — a flame. */
export function IconFlame({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.07-2.14-.22-4.05 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.15.43-2.29 1-3a2.5 2.5 0 0 0 2.5 2.5z" />
    </Svg>
  );
}

/** Light theme — a sun. */
export function IconSun({ className }: IconProps) {
  return (
    <Svg className={className}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
    </Svg>
  );
}

/** Dark theme — a crescent moon. */
export function IconMoon({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9z" />
    </Svg>
  );
}

/** Settings — a gear. */
export function IconSettings({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
      <circle cx="12" cy="12" r="3" />
    </Svg>
  );
}

/** A paw print — collapsed-cat button, and a burst particle. Filled. */
export function IconPaw({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
    >
      <ellipse cx="6.4" cy="10.4" rx="1.9" ry="2.4" />
      <ellipse cx="10" cy="7.6" rx="1.9" ry="2.5" />
      <ellipse cx="14" cy="7.6" rx="1.9" ry="2.5" />
      <ellipse cx="17.6" cy="10.4" rx="1.9" ry="2.4" />
      <path d="M12 12.6c-2.7 0-4.9 2.1-4.9 4.5 0 1.8 1.4 2.9 3.1 2.9.9 0 1.4-.3 1.8-.3s.9.3 1.8.3c1.7 0 3.1-1.1 3.1-2.9 0-2.4-2.2-4.5-4.9-4.5z" />
    </svg>
  );
}

/** A heart — burst particle. Filled. */
export function IconHeart({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7z" />
    </svg>
  );
}

/** A star — burst particle. Filled. */
export function IconStar({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M12 2.2l2.9 6.1 6.7.9-4.9 4.6 1.2 6.6-5.9-3.2-5.9 3.2 1.2-6.6L2.4 9.2l6.7-.9z" />
    </svg>
  );
}

/** A music note — burst particle. Filled. */
export function IconNote({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M20 3.2v11.1a3 3 0 1 1-2-2.8V7.1L10 8.7v8.6a3 3 0 1 1-2-2.8V6.2z" />
    </svg>
  );
}
