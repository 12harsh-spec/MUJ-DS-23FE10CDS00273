from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field

Priority = Literal["high", "medium", "low"]
Category = Literal[
    "exam", "fee_payment", "registration", "scholarship", "event",
    "holiday", "placement", "submission", "general",
]


class Action(BaseModel):
    task: str
    description: Optional[str] = None
    deadline: Optional[date] = None
    deadline_text: Optional[str] = None
    event_date: Optional[date] = None
    event_date_text: Optional[str] = None
    time: Optional[str] = None
    priority: Priority = "medium"
    applies_to: str = "all students"
    required_documents: list[str] = Field(default_factory=list)
    fee: Optional[str] = None
    where_or_contact: Optional[str] = None
    confidence: float = Field(0.8, ge=0, le=1)


class NoticeResult(BaseModel):
    title: str
    category: Category = "general"
    issued_by: Optional[str] = None
    summary: str
    actions: list[Action] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
