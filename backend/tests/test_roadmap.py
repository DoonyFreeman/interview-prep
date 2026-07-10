"""Public roadmap endpoint: stage grouping enriched with courses/lessons from DB."""
from __future__ import annotations


async def test_roadmap_is_public_and_complete(client):
    r = await client.get("/api/roadmap")
    assert r.status_code == 200
    stages = r.json()["stages"]

    assert [s["slug"] for s in stages] == [
        "core", "concurrency", "data", "web", "quality", "infra", "senior",
    ]
    # every published course appears exactly once across stages
    course_slugs = [c["slug"] for s in stages for c in s["courses"]]
    assert len(course_slugs) == len(set(course_slugs)) == 22

    for stage in stages:
        assert stage["title"] and stage["summary"]
        for course in stage["courses"]:
            assert course["title"] and course["summary"]
            assert course["lessons"], f"course {course['slug']} has no lessons"


async def test_roadmap_courses_enriched_from_db(client):
    stages = (await client.get("/api/roadmap")).json()["stages"]
    core = next(s for s in stages if s["slug"] == "core")
    python_core = next(c for c in core["courses"] if c["slug"] == "python-core")

    assert python_core["title"] == "Python Core"  # from DB, not roadmap.json
    assert len(python_core["lessons"]) == 10
    lesson = python_core["lessons"][0]
    assert lesson["slug"] and lesson["title"] and lesson["duration_minutes"] > 0
    # lessons are ordered
    orders = [l["order"] for l in python_core["lessons"]]
    assert orders == sorted(orders)


async def test_roadmap_extra_node_has_resources_and_no_lessons(client):
    stages = (await client.get("/api/roadmap")).json()["stages"]
    senior = next(s for s in stages if s["slug"] == "senior")
    extras = senior["extra_nodes"]
    assert [n["slug"] for n in extras] == ["interview-process"]

    node = extras[0]
    assert node["title"] and node["summary"]
    assert len(node["resources"]) >= 2
    for res in node["resources"]:
        assert res["type"] in ("video", "article", "docs")
        assert res["lang"] in ("ru", "en")
        assert res["url"].startswith("https://")
        assert res["title"] and res["source"]
    assert "lessons" not in node  # external topic — no internal content


async def test_roadmap_reference_answers_never_leak(client):
    r = await client.get("/api/roadmap")
    assert "reference_answer" not in r.text
