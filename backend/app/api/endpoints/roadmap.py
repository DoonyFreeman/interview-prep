"""Roadmap endpoint — public, like the course catalog it visualises."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas import RoadmapOut
from app.services import roadmap

router = APIRouter()


@router.get("/roadmap", response_model=RoadmapOut)
async def get_roadmap(session: AsyncSession = Depends(get_session)):
    return await roadmap.get_roadmap(session)
