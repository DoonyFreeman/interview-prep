"""Roadmap service: merge the static roadmap.json with course/lesson content.

``content/roadmap.json`` holds only what the DB doesn't: stage grouping,
"why this matters for the interview" summaries and curated external resources.
Course titles/descriptions and lesson lists are enriched from the content
tables here, so there is a single source of truth for them.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.content import registry
from app.models import Course
from app.repositories import CourseRepository
from app.schemas import (
    RoadmapCourseOut,
    RoadmapExtraNodeOut,
    RoadmapLessonOut,
    RoadmapOut,
    RoadmapResourceOut,
    RoadmapStageOut,
)


def _resources(raw: list | None) -> list[RoadmapResourceOut]:
    return [RoadmapResourceOut(**r) for r in (raw or [])]


def _course_out(node: dict, course: Course) -> RoadmapCourseOut:
    lesson_resources: dict = node.get("lesson_resources") or {}
    lessons = [
        RoadmapLessonOut(
            slug=lesson.slug,
            title=lesson.title,
            order=lesson.order_index,
            duration_minutes=lesson.duration_minutes,
            resources=_resources(lesson_resources.get(lesson.slug)),
        )
        for lesson in sorted(course.lessons, key=lambda l: l.order_index)
    ]
    return RoadmapCourseOut(
        slug=course.slug,
        title=course.title,
        description=course.description,
        summary=node.get("summary", ""),
        resources=_resources(node.get("resources")),
        lessons=lessons,
    )


async def get_roadmap(session: AsyncSession) -> RoadmapOut:
    data = registry.get_roadmap() or {"stages": []}
    courses = await CourseRepository(session).list_published_with_lessons_concepts()
    by_slug = {c.slug: c for c in courses}

    stages: list[RoadmapStageOut] = []
    for stage in data["stages"]:
        stages.append(
            RoadmapStageOut(
                slug=stage["slug"],
                title=stage["title"],
                summary=stage.get("summary", ""),
                courses=[
                    _course_out(node, by_slug[node["slug"]])
                    for node in stage.get("courses", [])
                    # unknown slug: skip silently — the integrity test is the guard
                    if node["slug"] in by_slug
                ],
                extra_nodes=[
                    RoadmapExtraNodeOut(
                        slug=n["slug"],
                        title=n["title"],
                        summary=n.get("summary", ""),
                        resources=_resources(n.get("resources")),
                    )
                    for n in stage.get("extra_nodes", [])
                ],
            )
        )
    return RoadmapOut(stages=stages)
