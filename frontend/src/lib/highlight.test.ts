import { describe, it, expect } from "vitest";
import { splitMatch } from "./highlight";

describe("splitMatch", () => {
  it("returns the whole text unmatched when query is empty", () => {
    expect(splitMatch("Generator", "")).toEqual([
      { text: "Generator", match: false },
    ]);
    expect(splitMatch("Generator", "   ")).toEqual([
      { text: "Generator", match: false },
    ]);
  });

  it("marks a single case-insensitive match", () => {
    expect(splitMatch("Generator", "gen")).toEqual([
      { text: "Gen", match: true },
      { text: "erator", match: false },
    ]);
  });

  it("marks all occurrences", () => {
    expect(splitMatch("ababa", "a")).toEqual([
      { text: "a", match: true },
      { text: "b", match: false },
      { text: "a", match: true },
      { text: "b", match: false },
      { text: "a", match: true },
    ]);
  });

  it("handles a match at the very end", () => {
    expect(splitMatch("decorator", "tor")).toEqual([
      { text: "decora", match: false },
      { text: "tor", match: true },
    ]);
  });

  it("returns a single unmatched segment when nothing matches", () => {
    expect(splitMatch("mutex", "zzz")).toEqual([{ text: "mutex", match: false }]);
  });

  it("preserves the original casing of the matched slice", () => {
    expect(splitMatch("GIL", "gil")).toEqual([{ text: "GIL", match: true }]);
  });
});
