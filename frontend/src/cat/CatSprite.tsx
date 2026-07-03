import { useMemo } from "react";
import type { CatHat, CatSkin, CatStage } from "../lib/cat";
import type { CatMood } from "./useCatMood";

type HatPixel = { x: number; y: number; w: number; h: number; fill: string };

// Each hat as a little list of pixel rects in the 12-wide grid; negative y sits
// above the head. Rendered above the body, so a hat can lift into the extended
// viewBox. "none" is bare. `wizard` is also the wizard-stage default hat.
const HATS: Record<CatHat, HatPixel[]> = {
  none: [],
  wizard: [
    { x: 2, y: -1, w: 8, h: 1, fill: "#352a5e" },
    { x: 4, y: -2, w: 4, h: 1, fill: "#3f3270" },
    { x: 5, y: -3, w: 2, h: 1, fill: "#3f3270" },
    { x: 6, y: -4, w: 1, h: 1, fill: "#f2c94c" },
  ],
  grad: [
    { x: 1, y: -1, w: 10, h: 1, fill: "#2b2f3a" },
    { x: 4, y: -2, w: 4, h: 1, fill: "#3a3f4d" },
    { x: 10, y: -1, w: 1, h: 1, fill: "#f2c94c" },
    { x: 10, y: 0, w: 1, h: 1, fill: "#f2c94c" },
  ],
  crown: [
    { x: 3, y: -1, w: 6, h: 1, fill: "#e8c352" },
    { x: 3, y: -2, w: 1, h: 1, fill: "#e8c352" },
    { x: 5, y: -2, w: 2, h: 1, fill: "#e8c352" },
    { x: 8, y: -2, w: 1, h: 1, fill: "#e8c352" },
    { x: 5.5, y: -1, w: 1, h: 1, fill: "#d64550" },
  ],
  flower: [
    { x: 8, y: -2, w: 1, h: 1, fill: "#f2a4bd" },
    { x: 7, y: -1, w: 1, h: 1, fill: "#f2a4bd" },
    { x: 9, y: -1, w: 1, h: 1, fill: "#f2a4bd" },
    { x: 8, y: 0, w: 1, h: 1, fill: "#f2a4bd" },
    { x: 8, y: -1, w: 1, h: 1, fill: "#f2c94c" },
  ],
  beanie: [
    { x: 3, y: -1, w: 6, h: 1, fill: "#3b8ea5" },
    { x: 4, y: -2, w: 4, h: 1, fill: "#f4ead2" },
    { x: 5, y: -3, w: 2, h: 1, fill: "#3b8ea5" },
    { x: 5.5, y: -4, w: 1, h: 1, fill: "#f4ead2" },
  ],
  headphones: [
    { x: 3, y: -1, w: 6, h: 1, fill: "#3a3f4a" },
    { x: 1, y: 0, w: 1, h: 2, fill: "#3a3f4a" },
    { x: 10, y: 0, w: 1, h: 2, fill: "#3a3f4a" },
    { x: 1, y: 1, w: 1, h: 1, fill: "#7a86f0" },
    { x: 10, y: 1, w: 1, h: 1, fill: "#7a86f0" },
  ],
};

interface Palette {
  B: string; // body base
  D: string; // outline / stripes
  L: string; // belly / face light
  P: string; // inner ear / paw pads
  eye: string;
  mouth: string;
}

// Cat keeps its *own* colour identity (so it pops on either theme); each skin
// is a hand-tuned little palette. Unlocked by streak milestones.
// Invariant (guarded in CatSprite.test.ts): `eye` must contrast with the face
// `L` — otherwise open eyes vanish into the muzzle and the cat looks perpetually
// closed-eyed (this was the tuxedo bug: eye was #f4f4f5, same as its white face).
export const PALETTES: Record<CatSkin, Palette> = {
  classic: { B: "#f0a84a", D: "#6b4a2b", L: "#ffe2b0", P: "#e98b8b", eye: "#3a2a18", mouth: "#c65f5f" },
  tabby: { B: "#9aa3ad", D: "#3c434c", L: "#e7ebef", P: "#d99", eye: "#222831", mouth: "#c65f5f" },
  tuxedo: { B: "#2d2f36", D: "#15161a", L: "#f4f4f5", P: "#d88", eye: "#4fae54", mouth: "#d88" },
  calico: { B: "#efe7da", D: "#7a5638", L: "#ffffff", P: "#e98b8b", eye: "#5a3d24", mouth: "#c65f5f" },
  void: { B: "#4b3b6b", D: "#241a38", L: "#cdbff0", P: "#b58be0", eye: "#9be8d8", mouth: "#b58be0" },
  sakura: { B: "#f2b8c6", D: "#8a4a5e", L: "#ffe9ef", P: "#e87a9a", eye: "#5e2a3a", mouth: "#d16a8a" },
  mint: { B: "#8fd8c8", D: "#2f6b5e", L: "#eafff8", P: "#f0a0a0", eye: "#234f45", mouth: "#d97f7f" },
  snow: { B: "#f5f5f7", D: "#9aa4b5", L: "#ffffff", P: "#f2b8c0", eye: "#4a90d9", mouth: "#e08a95" },
  ember: { B: "#5a3230", D: "#2a1512", L: "#f0c090", P: "#e06040", eye: "#7a2e12", mouth: "#c05038" },
  golden: { B: "#e8c352", D: "#8a6a1f", L: "#fff3cf", P: "#e89a6a", eye: "#6b4a10", mouth: "#c9803a" },
};

// 12×12 sitting cat. Eyes/nose/mouth get stamped in per mood.
const BASE = [
  ".D........D.",
  ".DD......DD.",
  ".DPD....DPD.",
  ".DBBDDDDBBD.",
  ".DBBBBBBBBD.",
  ".DBLLLLLLBD.",
  ".DBLLLLLLBD.",
  ".DBLLLLLLBD.",
  ".DBLLLLLLBD.",
  ".DBBBBBBBBD.",
  "..DBBBBBBD..",
  "..D.DDDD.D..",
];

function set(rows: string[], r: number, c: number, ch: string) {
  rows[r] = rows[r].slice(0, c) + ch + rows[r].slice(c + 1);
}

function gridFor(mood: CatMood): string[] {
  const rows = BASE.slice();
  // Eyes: open & forward when idle/stretch, glancing aside when "look", a
  // happy/closed line when playing/grooming/sleeping.
  if (mood === "idle" || mood === "stretch") {
    set(rows, 6, 4, "E");
    set(rows, 6, 7, "E");
  } else if (mood === "look") {
    set(rows, 6, 5, "E"); // both eyes shifted one column → a glance
    set(rows, 6, 8, "E");
  } else {
    set(rows, 6, 4, "C");
    set(rows, 6, 7, "C");
  }
  // Nose.
  set(rows, 7, 5, "N");
  set(rows, 7, 6, "N");
  // Open mouth only while playing.
  if (mood === "play") {
    set(rows, 8, 5, "O");
    set(rows, 8, 6, "O");
  }
  // Grooming: a raised paw to the cheek.
  if (mood === "groom") {
    set(rows, 7, 8, "P");
    set(rows, 8, 8, "P");
  }
  return rows;
}

function colorFor(ch: string, p: Palette): string | null {
  switch (ch) {
    case "B":
      return p.B;
    case "D":
      return p.D;
    case "L":
      return p.L;
    case "P":
      return p.P;
    case "E":
      return p.eye;
    case "C":
      return p.D;
    case "N":
      return p.D;
    case "O":
      return p.mouth;
    default:
      return null;
  }
}

export interface CatSpriteProps {
  skin: CatSkin;
  stage: CatStage;
  mood: CatMood;
  /** Enable idle blink / sleep z's animation (caller passes !reducedMotion). */
  animate: boolean;
  /** Explicit hat: null → wizard-stage default; "none" → bare. */
  hat?: CatHat | null;
  size?: number;
}

export function CatSprite({ skin, stage, mood, animate, hat = null, size = 64 }: CatSpriteProps) {
  const p = PALETTES[skin] ?? PALETTES.classic;
  // Explicit choice wins; "none" = bare; no choice → the wizard stage still
  // gets its signature hat (unchanged behavior).
  const activeHat: CatHat | null =
    hat === "none" ? null : (hat ?? (stage === "wizard" ? "wizard" : null));
  const hatPixels = activeHat ? HATS[activeHat] : [];
  const collared = stage === "bigcat" || stage === "wizard";

  const cells = useMemo(() => {
    const rows = gridFor(mood);
    const out: { x: number; y: number; fill: string; eye: boolean }[] = [];
    rows.forEach((row, r) => {
      for (let c = 0; c < row.length; c++) {
        const fill = colorFor(row[c], p);
        if (fill) out.push({ x: c, y: r, fill, eye: row[c] === "E" });
      }
    });
    return out;
  }, [mood, p]);

  // viewBox grows upward when a hat is on (all hats fit within 4px of headroom).
  const top = activeHat ? -4 : 0;
  const height = activeHat ? 16 : 12;

  return (
    <svg
      viewBox={`0 ${top} 12 ${height}`}
      width={size}
      height={(size * height) / 12}
      shapeRendering="crispEdges"
      role="img"
      aria-hidden
      style={{ overflow: "visible" }}
    >
      {animate && (
        <style>{`
          @keyframes cat-blink { 0%,92%,100% { transform: scaleY(1); } 96% { transform: scaleY(0.1); } }
          .cat-eye { animation: cat-blink 4.5s ease-in-out infinite; transform-box: fill-box; transform-origin: center; }
          @keyframes cat-z { 0% { opacity: 0; transform: translateY(0); } 30% { opacity: 1; } 100% { opacity: 0; transform: translateY(-2px); } }
          .cat-z { animation: cat-z 2.4s ease-out infinite; }
          @keyframes cat-tail { 0%,100% { transform: rotate(-9deg); } 50% { transform: rotate(11deg); } }
          .cat-tail { transform-box: view-box; transform-origin: 2px 10px; animation: cat-tail 2.8s ease-in-out infinite; }
          .cat-tail-play { animation-duration: 0.55s; }
        `}</style>
      )}

      {/* Swishing tail (curls off the lower-left, behind the body) */}
      <g
        className={
          animate ? `cat-tail ${mood === "play" ? "cat-tail-play" : ""}` : undefined
        }
      >
        <rect x={1} y={10} width={1} height={1} fill={p.B} />
        <rect x={0} y={9} width={1} height={1} fill={p.B} />
        <rect x={0} y={8} width={1} height={1} fill={p.B} />
        <rect x={-1} y={7} width={1} height={1} fill={p.B} />
        <rect x={-1} y={6} width={1} height={1} fill={p.D} />
      </g>

      {/* Hat (chosen, or the wizard-stage default) */}
      {hatPixels.length > 0 && (
        <g>
          {hatPixels.map((h, i) => (
            <rect key={i} x={h.x} y={h.y} width={h.w} height={h.h} fill={h.fill} />
          ))}
        </g>
      )}

      {cells.map((cell, i) => (
        <rect
          key={i}
          x={cell.x}
          y={cell.y}
          width={1}
          height={1}
          fill={cell.fill}
          className={cell.eye && animate ? "cat-eye" : undefined}
        />
      ))}

      {/* Collar from bigcat onward */}
      {collared && <rect x={3} y={8.6} width={6} height={0.5} rx={0.2} fill="#e08a00" />}

      {/* Sleep z's */}
      {mood === "sleep" && (
        <g fill={p.D} fontSize={3} fontFamily="monospace">
          <text x={10} y={4} className={animate ? "cat-z" : undefined}>
            z
          </text>
        </g>
      )}
    </svg>
  );
}
