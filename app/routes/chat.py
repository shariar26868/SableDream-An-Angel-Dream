import asyncio
from fastapi import APIRouter, HTTPException, status
from app.models.chat import (
    ChatRequest, ChatResponse,
    SessionSummary, SessionDetail,
    MessageRole,
)
from app.services.sable_ai import (
    get_sable_response,
    extract_memory,
    generate_session_title,
)
from app.database import get_db
from bson import ObjectId
from datetime import datetime
from typing import List

router = APIRouter(prefix="/chat", tags=["Chat"])


def _merge_memory(existing: dict, extracted) -> dict:
    CAP = 50

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
async def send_message(request: ChatRequest):
    db = get_db()
    now = datetime.utcnow()

    # ── Resolve or create session ──────────────────────────────────────────────
    if request.session_id:
        # Validate that session_id is a proper ObjectId before querying
        if not ObjectId.is_valid(request.session_id):
            raise HTTPException(
                status_code=400,
                detail="Invalid session_id format. Leave it empty to start a new session."
            )
        session = await db.chat_sessions.find_one({"_id": ObjectId(request.session_id)})
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        session_id = request.session_id
        raw_history = session.get("messages", [])
        # Use the session's memory_key to load memory
        memory_key = session.get("memory_key", request.session_id)
    else:
        # New session
        title = await generate_session_title(request.message)
        result = await db.chat_sessions.insert_one({
            "title": title,
            "messages": [],
            "created_at": now,
            "updated_at": now,
        })
        session_id = str(result.inserted_id)
        raw_history = []
        memory_key = session_id

        # Store memory_key on session
        await db.chat_sessions.update_one(
            {"_id": result.inserted_id},
            {"$set": {"memory_key": memory_key}}
        )

    # ── Load persistent memory for this session ────────────────────────────────
    memory_doc = await db.session_memory.find_one({"memory_key": memory_key}) or {}

    # ── Run extraction + Sable response in parallel ────────────────────────────
    openai_history = [
        {"role": m["role"], "content": m["content"]}
        for m in raw_history
    ]

    extracted, sable_reply = await asyncio.gather(
        extract_memory(request.message),
        get_sable_response(
            user_message=request.message,
            conversation_history=openai_history,
            user_name="friend",
            user_memory=memory_doc,
        ),
    )

    # ── Persist updated memory ─────────────────────────────────────────────────
    updated_memory = _merge_memory(dict(memory_doc), extracted)
    updated_memory["memory_key"] = memory_key
    updated_memory["updated_at"] = now

    await db.session_memory.update_one(
        {"memory_key": memory_key},
        {"$set": updated_memory},
        upsert=True,
    )

    # ── Save messages to session ───────────────────────────────────────────────
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
async def list_sessions():
    db = get_db()
    sessions = await db.chat_sessions.find().sort("updated_at", -1).to_list(100)

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
async def get_session(session_id: str):
    db = get_db()
    if not ObjectId.is_valid(session_id):
        raise HTTPException(status_code=400, detail="Invalid session_id format")
    session = await db.chat_sessions.find_one({"_id": ObjectId(session_id)})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionDetail(
        id=str(session["_id"]),
        title=session.get("title", "Untitled"),
        messages=session.get("messages", []),
        created_at=session["created_at"],
        updated_at=session["updated_at"],
    )


# ── GET /chat/sessions/{id}/memory ────────────────────────────────────────────
@router.get("/sessions/{session_id}/memory")
async def get_session_memory(session_id: str):
    """See everything Sable has learned from this session's conversations."""
    db = get_db()
    if not ObjectId.is_valid(session_id):
        raise HTTPException(status_code=400, detail="Invalid session_id format")
    memory = await db.session_memory.find_one({"memory_key": session_id})
    if not memory:
        return {"message": "No memory yet. Start chatting with Sable!"}

    memory.pop("_id", None)
    memory.pop("memory_key", None)
    return memory


# ── DELETE /chat/sessions/{id} ────────────────────────────────────────────────
@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: str):
    db = get_db()
    if not ObjectId.is_valid(session_id):
        raise HTTPException(status_code=400, detail="Invalid session_id format")
    result = await db.chat_sessions.delete_one({"_id": ObjectId(session_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Session not found")

    # Clean up memory too
    await db.session_memory.delete_one({"memory_key": session_id})
