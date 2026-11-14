"""Read a user's private rehearsal notes from the persistent server volume."""
from datetime import datetime
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, ValidationError

PRIVATE_HR_DIR = Path("data/private-hr")
MAX_FILE_BYTES = 64 * 1024
HR_LESSONS = frozenset({
    "self-presentation", "behavioral-questions", "motivation-and-conditions",
})

Question = Annotated[str, StringConstraints(min_length=1, max_length=250)]
AnswerText = Annotated[str, StringConstraints(min_length=1, max_length=2400)]
Slot = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9-]{0,59}$")]


class RehearsalAnswer(BaseModel):
    question: Question
    answer: AnswerText


AnswerGroups = dict[Slot, Annotated[list[RehearsalAnswer], Field(max_length=24)]]


class PrivateHRFile(BaseModel):
    owner_email: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    owner_created_at: datetime
    lessons: dict[str, AnswerGroups]


def get_answers(
    user_id: int, email: str, created_at: datetime, lesson_slug: str,
) -> AnswerGroups:
    if lesson_slug not in HR_LESSONS:
        return {}

    # The path comes from the authenticated account, never from a URL parameter.
    path = PRIVATE_HR_DIR / f"{user_id}.json"
    try:
        with path.open("rb") as f:
            data = f.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            return {}
        record = PrivateHRFile.model_validate_json(data)
    except (OSError, ValidationError):
        # A missing or malformed file must not affect the public lesson. Never
        # include private text in validation errors sent to the client or logs.
        return {}

    # Fail closed even if an account is removed and its numeric ID is reused.
    if record.owner_email != email or record.owner_created_at != created_at:
        return {}
    return record.lessons.get(lesson_slug, {})
