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
    user_id: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    user_id: str
    reply: str
    timestamp: datetime


class ConversationDetail(BaseModel):
    user_id: str
    messages: List[Message] = []
    created_at: datetime
    updated_at: datetime
