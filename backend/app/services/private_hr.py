"""Read a user's private rehearsal notes from the persistent server volume."""
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Annotated, TypeVar

from pydantic import BaseModel, Field, StringConstraints, ValidationError, model_validator

PRIVATE_HR_DIR = Path("data/private-hr")
TECHNICAL_INTERVIEW_DIR = Path("data/private-interview")
AGENT_GUIDE_DIR = Path("data/private-agent-guide")
RESUME_DIR = Path("data/private-resume")
MAX_FILE_BYTES = 64 * 1024
MAX_TECHNICAL_FILE_BYTES = 1024 * 1024
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


class AccountBoundNotes(BaseModel):
    owner_email: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    owner_created_at: datetime


class PrivateHRFile(AccountBoundNotes):
    lessons: dict[str, AnswerGroups]


TechnicalAnswers = Annotated[dict[Slot, AnswerText], Field(max_length=100)]


class TechnicalInterviewFile(AccountBoundNotes):
    answers: TechnicalAnswers


class AgentGuideSection(BaseModel):
    heading: Question
    items: Annotated[list[RehearsalAnswer], Field(min_length=1, max_length=24)]


AgentGuideSections = Annotated[list[AgentGuideSection], Field(max_length=8)]


class AgentGuideFile(AccountBoundNotes):
    sections: AgentGuideSections


class ResumePanel(BaseModel):
    title: Question
    text: AnswerText


class ResumeStep(BaseModel):
    from_node: Question
    to_node: Question
    title: Question
    payload: AnswerText
    state: Question
    why: AnswerText


class ResumeScenario(BaseModel):
    title: Question
    steps: Annotated[list[ResumeStep], Field(min_length=1, max_length=32)]


class ResumeNode(BaseModel):
    title: Question
    detail: AnswerText


class ResumeFlow(BaseModel):
    title: Question
    nodes: Annotated[list[ResumeNode], Field(min_length=2, max_length=12)]
    links: Annotated[list[Question], Field(max_length=11)]

    @model_validator(mode="after")
    def validate_links(self):
        if len(self.links) != len(self.nodes) - 1:
            raise ValueError("A flow requires one link between each pair of nodes")
        return self


class ResumeSection(BaseModel):
    id: Slot
    title: Question
    quote: AnswerText
    takeaway: AnswerText | None = None
    flows: Annotated[list[ResumeFlow], Field(max_length=12)] | None = None
    panels: Annotated[list[ResumePanel], Field(min_length=1, max_length=24)]
    scenarios: Annotated[list[ResumeScenario], Field(max_length=12)]
    questions: Annotated[list[RehearsalAnswer], Field(max_length=24)]
    terms: Annotated[list[RehearsalAnswer], Field(max_length=32)]


ResumeSections = Annotated[list[ResumeSection], Field(max_length=96)]


class ResumeFile(AccountBoundNotes):
    sections: ResumeSections
    pdf_sha256: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")] | None = None


Notes = TypeVar("Notes", bound=AccountBoundNotes)


def get_answers(
    user_id: int, email: str, created_at: datetime, lesson_slug: str,
) -> AnswerGroups:
    if lesson_slug not in HR_LESSONS:
        return {}

    record = _load_owned_notes(PRIVATE_HR_DIR, PrivateHRFile, user_id, email, created_at)
    return record.lessons.get(lesson_slug, {}) if record else {}


def get_technical_answers(user_id: int, email: str, created_at: datetime) -> TechnicalAnswers:
    record = _load_owned_notes(
        TECHNICAL_INTERVIEW_DIR, TechnicalInterviewFile, user_id, email, created_at,
        max_bytes=MAX_TECHNICAL_FILE_BYTES,
    )
    return record.answers if record else {}


def get_agent_guide(user_id: int, email: str, created_at: datetime) -> AgentGuideSections:
    record = _load_owned_notes(
        AGENT_GUIDE_DIR, AgentGuideFile, user_id, email, created_at,
        max_bytes=MAX_TECHNICAL_FILE_BYTES,
    )
    return record.sections if record else []


def get_resume(user_id: int, email: str, created_at: datetime) -> ResumeSections:
    record = _load_owned_notes(
        RESUME_DIR, ResumeFile, user_id, email, created_at, max_bytes=MAX_TECHNICAL_FILE_BYTES,
    )
    return record.sections if record else []


def get_resume_pdf(user_id: int, email: str, created_at: datetime) -> bytes | None:
    record = _load_owned_notes(
        RESUME_DIR, ResumeFile, user_id, email, created_at, max_bytes=MAX_TECHNICAL_FILE_BYTES,
    )
    if not record or not record.pdf_sha256:
        return None
    max_pdf_bytes = 4 * 1024 * 1024
    try:
        with (RESUME_DIR / f"{user_id}.pdf").open("rb") as file:
            content = file.read(max_pdf_bytes + 1)
    except OSError:
        return None
    if len(content) > max_pdf_bytes or not content.startswith(b"%PDF-"):
        return None
    return content if sha256(content).hexdigest() == record.pdf_sha256 else None


def _load_owned_notes(
    directory: Path, model: type[Notes], user_id: int, email: str, created_at: datetime,
    *, max_bytes: int = MAX_FILE_BYTES,
) -> Notes | None:
    # The path comes from the authenticated account, never from a URL parameter.
    path = directory / f"{user_id}.json"
    try:
        with path.open("rb") as f:
            data = f.read(max_bytes + 1)
        if len(data) > max_bytes:
            return None
        record = model.model_validate_json(data)
    except (OSError, ValidationError):
        # A missing or malformed file must not affect the public lesson. Never
        # include private text in validation errors sent to the client or logs.
        return None

    # Fail closed even if an account is removed and its numeric ID is reused.
    if record.owner_email != email or record.owner_created_at != created_at:
        return None
    return record
