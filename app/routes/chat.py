import asyncio
from fastapi import APIRouter, HTTPException, status
from app.models.chat import (
    ChatRequest, ChatResponse,
    ConversationDetail,
    MessageRole,
)
from app.services.sable_ai import (
    get_sable_response,
    extract_memory,
)
from app.database import get_db
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

    # ── Load or create conversation for this user ──────────────────────────────
    conversation = await db.conversations.find_one({"user_id": request.user_id})

    if conversation:
        raw_history = conversation.get("messages", [])
    else:
        # First time this user is chatting — create their conversation doc
        await db.conversations.insert_one({
            "user_id": request.user_id,
            "messages": [],
            "created_at": now,
            "updated_at": now,
        })
        raw_history = []

    # ── Load this user's persistent memory ────────────────────────────────────
    memory_doc = await db.user_memory.find_one({"user_id": request.user_id}) or {}

    # ── Run memory extraction + Sable response in parallel ────────────────────
    openai_history = [
        {"role": m["role"], "content": m["content"]}
        for m in raw_history
    ]

    extracted, sable_reply = await asyncio.gather(
        extract_memory(request.message),
        get_sable_response(
            user_message=request.message,
            conversation_history=openai_history,
            user_name=request.user_id,
            user_memory=memory_doc,
        ),
    )

    # ── Persist updated memory ─────────────────────────────────────────────────
    updated_memory = _merge_memory(dict(memory_doc), extracted)
    updated_memory["user_id"] = request.user_id
    updated_memory["updated_at"] = now

    await db.user_memory.update_one(
        {"user_id": request.user_id},
        {"$set": updated_memory},
        upsert=True,
    )

    # ── Save both messages to conversation ────────────────────────────────────
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

    await db.conversations.update_one(
        {"user_id": request.user_id},
        {
            "$push": {"messages": {"$each": [user_msg, assistant_msg]}},
            "$set": {"updated_at": now},
        },
    )

    return ChatResponse(
        user_id=request.user_id,
        reply=sable_reply,
        timestamp=now,
    )


# ── GET /chat/history/{user_id} ───────────────────────────────────────────────
@router.get("/history/{user_id}", response_model=ConversationDetail)
async def get_history(user_id: str):
    """Get full conversation history for a user."""
    db = get_db()
    conversation = await db.conversations.find_one({"user_id": user_id})
    if not conversation:
        raise HTTPException(status_code=404, detail="No conversation found for this user")

    return ConversationDetail(
        user_id=conversation["user_id"],
        messages=conversation.get("messages", []),
        created_at=conversation["created_at"],
        updated_at=conversation["updated_at"],
    )


# ── GET /chat/memory/{user_id} ────────────────────────────────────────────────
@router.get("/memory/{user_id}")
async def get_memory(user_id: str):
    """See everything Sable has learned about this user."""
    db = get_db()
    memory = await db.user_memory.find_one({"user_id": user_id})
    if not memory:
        return {"message": "No memory yet. Start chatting with Sable!"}

    memory.pop("_id", None)
    memory.pop("user_id", None)
    return memory


# ── DELETE /chat/history/{user_id} ───────────────────────────────────────────
@router.delete("/history/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_history(user_id: str):
    """Delete a user's full conversation history and memory."""
    db = get_db()
    conv_result = await db.conversations.delete_one({"user_id": user_id})
    if conv_result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="No conversation found for this user")

    await db.user_memory.delete_one({"user_id": user_id})
