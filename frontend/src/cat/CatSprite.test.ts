import { describe, expect, it } from "vitest";
import { PALETTES } from "./CatSprite";

// Regression for the "Смокинг always closed-eyed" bug: the tuxedo skin had
// eye === face (#f4f4f5), so open eyes were white-on-white and invisible —
// only the dark closed-eye line ever showed. Open eyes must contrast with the
// muzzle (L) and not melt into the body (B) for *every* skin.
describe("cat palettes: open eyes are visible", () => {
  for (const [skin, p] of Object.entries(PALETTES)) {
    it(`${skin}: eye contrasts with face and body`, () => {
      expect(p.eye.toLowerCase()).not.toBe(p.L.toLowerCase());
      expect(p.eye.toLowerCase()).not.toBe(p.B.toLowerCase());
    });
  }
});
