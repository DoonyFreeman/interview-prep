"""Load course content from disk into in-memory dataclasses.

Source of truth is the ``content/`` directory: each course is a folder with a
``metadata.json`` (course + lessons + concepts), a ``questions.json`` (question
bank keyed by lesson slug -> concept slug -> list), and one markdown file per
lesson. The loader parses these into a :class:`ContentBundle`; seeding into the
DB and caching markdown is done elsewhere (``seed.py`` / ``registry.py``).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class QuestionData:
    text: str
    reference_answer: str
    difficulty: int = 3
    order_index: int = 0


@dataclass
class ConceptData:
    slug: str
    title: str
    anchor: str = ""
    order_index: int = 0
    questions: list[QuestionData] = field(default_factory=list)


@dataclass
class LessonData:
    slug: str
    title: str
    content_path: str
    markdown: str
    order_index: int = 0
    duration_minutes: int = 0
    concepts: list[ConceptData] = field(default_factory=list)


@dataclass
class CourseData:
    slug: str
    title: str
    description: str = ""
    order_index: int = 0
    lessons: list[LessonData] = field(default_factory=list)


@dataclass
class ContentBundle:
    courses: list[CourseData] = field(default_factory=list)


def load_content(content_dir: str | Path) -> ContentBundle:
    """Parse every course folder under ``content_dir/courses`` into a bundle."""
    root = Path(content_dir)
    courses_dir = root / "courses"
    bundle = ContentBundle()
    if not courses_dir.is_dir():
        return bundle

    for course_path in sorted(p for p in courses_dir.iterdir() if p.is_dir()):
        meta_file = course_path / "metadata.json"
        if not meta_file.is_file():
            continue
        meta = json.loads(meta_file.read_text(encoding="utf-8"))

        questions_file = course_path / "questions.json"
        questions_map: dict = (
            json.loads(questions_file.read_text(encoding="utf-8"))
            if questions_file.is_file()
            else {}
        )

        bundle.courses.append(_parse_course(course_path, meta, questions_map))

    return bundle


def _parse_course(course_path: Path, meta: dict, questions_map: dict) -> CourseData:
    course = CourseData(
        slug=meta["slug"],
        title=meta["title"],
        description=meta.get("description", ""),
        order_index=meta.get("order", 0),
    )

    for lesson_meta in meta.get("lessons", []):
        lesson_slug = lesson_meta["slug"]
        md_path = course_path / lesson_meta["file"]
        markdown = md_path.read_text(encoding="utf-8") if md_path.is_file() else ""

        lesson = LessonData(
            slug=lesson_slug,
            title=lesson_meta["title"],
            content_path=str(md_path),
            markdown=markdown,
            order_index=lesson_meta.get("order", 0),
            duration_minutes=lesson_meta.get("duration_minutes", 0),
        )

        lesson_questions = questions_map.get(lesson_slug, {})
        for concept_meta in lesson_meta.get("concepts", []):
            concept_slug = concept_meta["slug"]
            concept = ConceptData(
                slug=concept_slug,
                title=concept_meta["title"],
                anchor=concept_meta.get("anchor", ""),
                order_index=concept_meta.get("order", 0),
            )
            for i, q in enumerate(lesson_questions.get(concept_slug, [])):
                concept.questions.append(
                    QuestionData(
                        text=q["text"],
                        reference_answer=q["reference_answer"],
                        difficulty=q.get("difficulty", 3),
                        order_index=q.get("order", i),
                    )
                )
            lesson.concepts.append(concept)

        course.lessons.append(lesson)

    return course
