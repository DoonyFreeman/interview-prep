import { describe, expect, it } from "vitest";
import {
  filterQuestions,
  interviewQuestions,
  interviewSources,
  interviewTopics,
  sourceCoverage,
} from "./pythonAiInterview";

describe("Python AI interview cheatsheet", () => {
  it("keeps the preparation order across filters with unique question ranks", () => {
    expect(interviewQuestions.length).toBeGreaterThanOrEqual(60);
    expect(interviewQuestions.map(({ rank }) => rank)).toEqual(
      interviewQuestions.map((_, index) => index + 1),
    );
    expect(new Set(interviewQuestions.map(({ question }) => question)).size).toBe(interviewQuestions.length);
    expect(new Set(interviewQuestions.map(({ id }) => id)).size).toBe(interviewQuestions.length);
    expect(interviewQuestions.every(({ id }) => /^[a-z][a-z0-9-]{0,59}$/.test(id))).toBe(true);
    expect(interviewQuestions.every((question) => interviewTopics.includes(question.topic))).toBe(true);
    for (const topic of interviewTopics) {
      const matches = filterQuestions(topic, "");
      expect(matches.length).toBeGreaterThan(0);
      expect(matches.every((question) => question.topic === topic)).toBe(true);
      expect(matches.map(({ rank }) => rank)).toEqual(matches.map(({ rank }) => rank).sort((a, b) => a - b));
    }
  });

  it("handles mixed-case, spaced terms, empty searches and no matches", () => {
    expect(filterQuestions(null, " ")).toEqual(interviewQuestions);
    expect(filterQuestions("agents", "  Lang Graph  ").length).toBeGreaterThan(0);
    expect(filterQuestions("eval", "recall@10").length).toBeGreaterThan(0);
    expect(filterQuestions("python", "LangGraph")).toEqual([]);
  });

  it("counts each source at most once and keeps interview and role signals separate", () => {
    expect(new Set(interviewSources.map(({ url }) => url)).size).toBe(interviewSources.length);
    const python = sourceCoverage.find(({ topic }) => topic === "python");
    for (const item of sourceCoverage) {
      for (const kind of ["interview", "role"] as const) {
        const sources = interviewSources.filter((source) => source.kind === kind);
        expect(item[kind]).toBe(sources.filter((source) => source.topics.includes(item.topic)).length);
        expect(item[kind]).toBeLessThanOrEqual(sources.length);
      }
    }
    expect(python?.interview).toBeGreaterThan(0);
    expect(python?.role).toBeGreaterThan(0);
  });
});
