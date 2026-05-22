from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class ExtractedMemory(BaseModel):
    mood: Optional[str] = None
    energy_level: Optional[str] = None
    activities: List[str] = []
    goals: List[str] = []
    dreams: List[str] = []
    routine_notes: List[str] = []
    important_people: List[str] = []
    key_events: List[str] = []


class Message(BaseModel):
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    extracted: Optional[ExtractedMemory] = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: Optional[str] = None  # None = auto-create new session


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    timestamp: datetime


class SessionSummary(BaseModel):
    id: str
    title: str
    last_message: Optional[str] = None
    message_count: int
    created_at: datetime
    updated_at: datetime


class SessionDetail(BaseModel):
    id: str
    title: str
    messages: List[Message] = []
    created_at: datetime
    updated_at: datetime
