import { useMemo } from "react";
import type { CatSkin, CatStage } from "../lib/cat";
import type { CatMood } from "./useCatMood";

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
const PALETTES: Record<CatSkin, Palette> = {
  classic: { B: "#f0a84a", D: "#6b4a2b", L: "#ffe2b0", P: "#e98b8b", eye: "#3a2a18", mouth: "#c65f5f" },
  tabby: { B: "#9aa3ad", D: "#3c434c", L: "#e7ebef", P: "#d99", eye: "#222831", mouth: "#c65f5f" },
  tuxedo: { B: "#2d2f36", D: "#15161a", L: "#f4f4f5", P: "#d88", eye: "#f4f4f5", mouth: "#d88" },
  calico: { B: "#efe7da", D: "#7a5638", L: "#ffffff", P: "#e98b8b", eye: "#5a3d24", mouth: "#c65f5f" },
  void: { B: "#4b3b6b", D: "#241a38", L: "#cdbff0", P: "#b58be0", eye: "#9be8d8", mouth: "#b58be0" },
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
  size?: number;
}

export function CatSprite({ skin, stage, mood, animate, size = 64 }: CatSpriteProps) {
  const p = PALETTES[skin] ?? PALETTES.classic;
  const wizard = stage === "wizard";
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

  // viewBox grows upward when the wizard hat is on.
  const top = wizard ? -4 : 0;
  const height = wizard ? 16 : 12;

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
        `}</style>
      )}

      {/* Wizard hat */}
      {wizard && (
        <g>
          <rect x={2} y={-1} width={8} height={1} fill="#352a5e" />
          <rect x={4} y={-2} width={4} height={1} fill="#3f3270" />
          <rect x={5} y={-3} width={2} height={1} fill="#3f3270" />
          <rect x={6} y={-4} width={1} height={1} fill="#f2c94c" />
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
