from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import datetime
from enum import Enum


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


# ── What Sable silently extracts from each message ────────────────────────────
class ExtractedMemory(BaseModel):
    """
    Sable auto-extracts structured data from the conversation.
    All fields are optional — only populated when detected.
    """
    mood: Optional[str] = None           # e.g. "happy", "anxious", "overwhelmed"
    energy_level: Optional[str] = None   # e.g. "low", "high", "tired"
    activities: List[str] = []           # e.g. ["went to gym", "cooked dinner"]
    goals: List[str] = []                # e.g. ["become a doctor", "learn guitar"]
    dreams: List[str] = []               # e.g. ["travel to Japan", "write a book"]
    routine_notes: List[str] = []        # e.g. ["wakes up at 7am", "skips breakfast"]
    important_people: List[str] = []     # e.g. ["mom", "best friend Sara"]
    key_events: List[str] = []           # e.g. ["got a promotion", "had a fight"]


# ── A single message in the conversation ──────────────────────────────────────
class Message(BaseModel):
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    extracted: Optional[ExtractedMemory] = None  # only on user messages


# ── API request/response ──────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: Optional[str] = None  # None = start new session


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    timestamp: datetime


# ── Session list item (for GET /chat/sessions) ────────────────────────────────
class SessionSummary(BaseModel):
    id: str
    title: str
    last_message: Optional[str] = None
    message_count: int
    created_at: datetime
    updated_at: datetime


# ── Full session with history ─────────────────────────────────────────────────
class SessionDetail(BaseModel):
    id: str
    user_id: str
    title: str
    messages: List[Message] = []
    created_at: datetime
    updated_at: datetime
