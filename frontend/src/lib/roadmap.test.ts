import { describe, expect, it } from "vitest";
import type {
  ProgressOverviewOut,
  RoadmapCourse,
  RoadmapStage,
} from "../api/types";
import {
  courseCounts,
  lessonStatus,
  overallCounts,
  resourcesFor,
  sortResources,
  stageCounts,
} from "./roadmap";

const res = (type: string, title = type) => ({
  type,
  lang: "ru",
  title,
  url: "https://example.com",
  source: "src",
});

const course = (
  slug: string,
  lessons: { slug: string; resources?: ReturnType<typeof res>[] }[],
  resources: ReturnType<typeof res>[] = [],
): RoadmapCourse => ({
  slug,
  title: slug,
  description: "",
  summary: "",
  resources,
  lessons: lessons.map((l, i) => ({
    slug: l.slug,
    title: l.slug,
    order: i + 1,
    duration_minutes: 20,
    resources: l.resources ?? [],
  })),
});

const progressWith = (
  courseSlug: string,
  lessons: { slug: string; completed: boolean; attempted_concepts: number }[],
): ProgressOverviewOut =>
  ({
    total_concepts: 0,
    attempted_concepts: 0,
    mastered_concepts: 0,
    due_concepts: 0,
    courses: [
      {
        slug: courseSlug,
        title: courseSlug,
        total_concepts: 0,
        attempted_concepts: 0,
        mastered_concepts: 0,
        due_concepts: 0,
        lessons: lessons.map((l) => ({
          slug: l.slug,
          title: l.slug,
          completed: l.completed,
          total_concepts: 3,
          attempted_concepts: l.attempted_concepts,
          mastered_concepts: 0,
          due_concepts: 0,
          concepts: [],
        })),
      },
    ],
  }) as ProgressOverviewOut;

describe("lessonStatus", () => {
  const progress = progressWith("kafka", [
    { slug: "architecture", completed: true, attempted_concepts: 3 },
    { slug: "producers-consumers", completed: false, attempted_concepts: 1 },
    { slug: "kafka-in-python", completed: false, attempted_concepts: 0 },
  ]);

  it("maps completed / attempted / untouched", () => {
    expect(lessonStatus(progress, "kafka", "architecture")).toBe("done");
    expect(lessonStatus(progress, "kafka", "producers-consumers")).toBe(
      "attempted",
    );
    expect(lessonStatus(progress, "kafka", "kafka-in-python")).toBe("none");
  });

  it("is 'none' for unknown course/lesson or missing progress", () => {
    expect(lessonStatus(progress, "nginx", "whatever")).toBe("none");
    expect(lessonStatus(progress, "kafka", "ghost")).toBe("none");
    expect(lessonStatus(undefined, "kafka", "architecture")).toBe("none");
  });
});

describe("counts", () => {
  const kafka = course("kafka", [
    { slug: "a" },
    { slug: "b" },
    { slug: "c" },
  ]);
  const nginx = course("nginx", [{ slug: "x" }, { slug: "y" }]);
  const stage: RoadmapStage = {
    slug: "s",
    title: "s",
    summary: "",
    courses: [kafka, nginx],
    extra_nodes: [],
  };
  const progress = progressWith("kafka", [
    { slug: "a", completed: true, attempted_concepts: 3 },
    { slug: "b", completed: true, attempted_concepts: 3 },
    { slug: "c", completed: false, attempted_concepts: 0 },
  ]);

  it("totals come from the roadmap, done from progress", () => {
    expect(courseCounts(progress, kafka)).toEqual({ done: 2, total: 3 });
    expect(courseCounts(progress, nginx)).toEqual({ done: 0, total: 2 });
    expect(stageCounts(progress, stage)).toEqual({ done: 2, total: 5 });
    expect(overallCounts(progress, [stage])).toEqual({ done: 2, total: 5 });
  });

  it("works with no progress at all", () => {
    expect(stageCounts(undefined, stage)).toEqual({ done: 0, total: 5 });
  });
});

describe("resourcesFor", () => {
  const c = course(
    "kafka",
    [
      { slug: "own", resources: [res("docs"), res("video")] },
      { slug: "bare" },
    ],
    [res("article", "course-level")],
  );

  it("prefers the lesson's own resources, sorted video→article→docs", () => {
    const { resources, fromCourse } = resourcesFor(c, "own");
    expect(fromCourse).toBe(false);
    expect(resources.map((r) => r.type)).toEqual(["video", "docs"]);
  });

  it("falls back to course resources with a flag", () => {
    const { resources, fromCourse } = resourcesFor(c, "bare");
    expect(fromCourse).toBe(true);
    expect(resources[0].title).toBe("course-level");
  });

  it("sortResources orders video→article→docs", () => {
    expect(
      sortResources([res("docs"), res("article"), res("video")]).map(
        (r) => r.type,
      ),
    ).toEqual(["video", "article", "docs"]);
  });
});
