import asyncio
from fastapi import APIRouter, HTTPException, Depends, status
from app.models.chat import (
    ChatRequest, ChatResponse,
    SessionSummary, SessionDetail,
    Message, MessageRole,
)
from app.services.sable_ai import (
    get_sable_response,
    extract_memory,
    generate_session_title,
)
from app.dependencies import get_current_user
from app.database import get_db
from bson import ObjectId
from datetime import datetime
from typing import List

router = APIRouter(prefix="/chat", tags=["Chat"])


def _merge_memory(existing: dict, extracted) -> dict:
    """
    Merge newly extracted memory into the user's persistent memory document.
    Lists are deduplicated and capped to avoid unbounded growth.
    """
    CAP = 50  # max items per list

    def merge_list(key: str, new_items: list):
        current = existing.get(key, [])
        combined = current + [i for i in new_items if i not in current]
        existing[key] = combined[-CAP:]

    if extracted.mood:
        existing.setdefault("moods", [])
        existing["moods"].append(extracted.mood)
        existing["moods"] = existing["moods"][-CAP:]

    if extracted.energy_level:
        existing.setdefault("energy_levels", [])
        existing["energy_levels"].append(extracted.energy_level)
        existing["energy_levels"] = existing["energy_levels"][-CAP:]

    merge_list("activities", extracted.activities)
    merge_list("goals", extracted.goals)
    merge_list("dreams", extracted.dreams)
    merge_list("routine_notes", extracted.routine_notes)
    merge_list("important_people", extracted.important_people)
    merge_list("key_events", extracted.key_events)

    return existing


# ── POST /chat/message ─────────────────────────────────────────────────────────
@router.post("/message", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
):
    db = get_db()
    user_id = str(current_user["_id"])
    user_name = current_user.get("name", "friend")
    now = datetime.utcnow()

    # ── 1. Resolve or create session ──────────────────────────────────────────
    if request.session_id:
        session = await db.chat_sessions.find_one({
            "_id": ObjectId(request.session_id),
            "user_id": user_id,
        })
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        session_id = request.session_id
        raw_history = session.get("messages", [])
    else:
        # New session — title generated from first message
        title = await generate_session_title(request.message)
        result = await db.chat_sessions.insert_one({
            "user_id": user_id,
            "title": title,
            "messages": [],
            "created_at": now,
            "updated_at": now,
        })
        session_id = str(result.inserted_id)
        raw_history = []

    # ── 2. Load user's persistent memory ──────────────────────────────────────
    memory_doc = await db.user_memory.find_one({"user_id": user_id}) or {}

    # ── 3. Run memory extraction + Sable response in parallel ─────────────────
    openai_history = [
        {"role": m["role"], "content": m["content"]}
        for m in raw_history
    ]

    extracted, sable_reply = await asyncio.gather(
        extract_memory(request.message),
        get_sable_response(
            user_message=request.message,
            conversation_history=openai_history,
            user_name=user_name,
            user_memory=memory_doc,
        ),
    )

    # ── 4. Persist updated memory ──────────────────────────────────────────────
    updated_memory = _merge_memory(dict(memory_doc), extracted)
    updated_memory["user_id"] = user_id
    updated_memory["updated_at"] = now

    await db.user_memory.update_one(
        {"user_id": user_id},
        {"$set": updated_memory},
        upsert=True,
    )

    # ── 5. Save both messages to session ──────────────────────────────────────
    user_msg = {
        "role": MessageRole.USER,
        "content": request.message,
        "timestamp": now,
        "extracted": extracted.model_dump(),
    }
    assistant_msg = {
        "role": MessageRole.ASSISTANT,
        "content": sable_reply,
        "timestamp": now,
    }

    await db.chat_sessions.update_one(
        {"_id": ObjectId(session_id)},
        {
            "$push": {"messages": {"$each": [user_msg, assistant_msg]}},
            "$set": {"updated_at": now},
        },
    )

    return ChatResponse(
        session_id=session_id,
        reply=sable_reply,
        timestamp=now,
    )


# ── GET /chat/sessions ─────────────────────────────────────────────────────────
@router.get("/sessions", response_model=List[SessionSummary])
async def list_sessions(current_user: dict = Depends(get_current_user)):
    """All sessions for the user, newest first."""
    db = get_db()
    user_id = str(current_user["_id"])

    sessions = await db.chat_sessions.find(
        {"user_id": user_id}
    ).sort("updated_at", -1).to_list(100)

    result = []
    for s in sessions:
        msgs = s.get("messages", [])
        last = msgs[-1]["content"] if msgs else None
        result.append(SessionSummary(
            id=str(s["_id"]),
            title=s.get("title", "Untitled"),
            last_message=last[:120] if last else None,
            message_count=len(msgs),
            created_at=s["created_at"],
            updated_at=s["updated_at"],
        ))

    return result


# ── GET /chat/sessions/{id} ────────────────────────────────────────────────────
@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Full conversation history for a session."""
    db = get_db()
    user_id = str(current_user["_id"])

    session = await db.chat_sessions.find_one({
        "_id": ObjectId(session_id),
        "user_id": user_id,
    })
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionDetail(
        id=str(session["_id"]),
        user_id=session["user_id"],
        title=session.get("title", "Untitled"),
        messages=session.get("messages", []),
        created_at=session["created_at"],
        updated_at=session["updated_at"],
    )


# ── GET /chat/memory ───────────────────────────────────────────────────────────
@router.get("/memory")
async def get_memory(current_user: dict = Depends(get_current_user)):
    """
    See everything Sable has learned about you from your conversations.
    Useful for debugging or showing the user their own profile.
    """
    db = get_db()
    user_id = str(current_user["_id"])

    memory = await db.user_memory.find_one({"user_id": user_id})
    if not memory:
        return {"message": "No memory yet. Start chatting with Sable!"}

    memory.pop("_id", None)
    memory.pop("user_id", None)
    return memory


# ── DELETE /chat/sessions/{id} ────────────────────────────────────────────────
@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    db = get_db()
    user_id = str(current_user["_id"])

    result = await db.chat_sessions.delete_one({
        "_id": ObjectId(session_id),
        "user_id": user_id,
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Session not found")
