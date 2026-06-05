"""Course listing endpoints (pure DB reads via the content service, no LLM)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas import CourseDetail, CourseSummary
from app.services import content

router = APIRouter()


@router.get("/courses", response_model=list[CourseSummary])
async def list_courses(session: AsyncSession = Depends(get_session)):
    return await content.list_courses(session)


@router.get("/courses/{course_slug}", response_model=CourseDetail)
async def get_course(course_slug: str, session: AsyncSession = Depends(get_session)):
    return await content.get_course(session, course_slug)
