"""Response metadata shared by the assistant runtime and conversation storage."""
from typing import Literal

from pydantic import BaseModel, Field


class ChatSource(BaseModel):
    title: str
    url: str
    kind: Literal["lesson", "web"]


class ReplyMetadata(BaseModel):
    sources: list[ChatSource] = Field(default_factory=list)
    tool_activity: list[str] = Field(default_factory=list)
