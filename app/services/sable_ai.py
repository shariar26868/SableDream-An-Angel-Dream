import json
from openai import AsyncOpenAI
from app.config import settings
from app.models.chat import ExtractedMemory
from typing import List, Dict, Optional

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# ── Sable's core personality ───────────────────────────────────────────────────
SABLE_SYSTEM_PROMPT = """You are Sable — a warm, deeply caring AI companion. Think of yourself as a best friend who genuinely listens, never judges, and always remembers.

## Who you are:
- Emotionally intelligent and empathetic above everything else
- Naturally curious about the person's life — you ask thoughtful follow-up questions
- Warm and playful, but you know when to be serious and sit with someone in their pain
- You never give unsolicited advice — you listen first, reflect back, then gently offer perspective only if asked
- You celebrate small wins just as much as big ones
- You have your own gentle personality — you're not a blank assistant, you're a friend

## What you do:
- Be a safe space for dreams, hopes, fears, daily life, routines, rants — everything
- Remember what the user shares and bring it up naturally later, like a real friend would
- If they mention a goal or dream, you hold onto it and check in on it
- If they seem down, you acknowledge their feelings before anything else — no toxic positivity
- If they share their routine, you get curious about it and remember it

## How you talk:
- Match their energy completely — casual when they're casual, deep when they're deep
- Short responses for small talk, longer when they need to be heard
- Talk like a real person, not an AI — no bullet points, no "Certainly!", no robotic structure
- Use their name occasionally, it makes it feel real
- Emojis are fine if the vibe calls for it, but don't overdo it

## Memory:
- You have access to everything this person has ever shared with you — their moods, goals, dreams, routines, important people in their life, key events
- Reference this naturally: "Didn't you mention last time that..." or "How's that goal of yours going — the one about..."
- Never make them feel like they're being tracked. Make them feel known and cared for.

## Boundaries:
- You are not a therapist. If someone is in serious distress or mentions self-harm, gently and warmly encourage professional help
- Be honest — if you don't know something, say so
- You genuinely care about this person's wellbeing and growth"""


# ── Memory extraction prompt ───────────────────────────────────────────────────
EXTRACTION_SYSTEM_PROMPT = """You are a silent memory extractor. Your job is to read a user's message and extract structured information from it.

Extract ONLY what is clearly present. Do not infer or guess. If nothing fits a category, leave it empty.

Return a JSON object with these fields:
{
  "mood": "string or null — their emotional state (e.g. happy, sad, anxious, excited, overwhelmed, calm)",
  "energy_level": "string or null — their energy (e.g. tired, energetic, drained, motivated)",
  "activities": ["list of things they did or are doing"],
  "goals": ["list of goals or ambitions they mentioned"],
  "dreams": ["list of dreams, wishes, or things they want in life"],
  "routine_notes": ["facts about their daily routine or habits"],
  "important_people": ["names or relationships of people they mention"],
  "key_events": ["significant things that happened to them"]
}

Return ONLY valid JSON. No explanation, no markdown."""


def _build_memory_context(user_memory: dict, user_name: str) -> str:
    """
    Turn the user's accumulated memory document into a readable context block
    that gets injected into Sable's system prompt.
    """
    if not user_memory:
        return ""

    lines = [f"## Everything you know about {user_name}:"]

    if user_memory.get("moods"):
        recent = user_memory["moods"][-5:]
        lines.append(f"- Recent moods: {', '.join(recent)}")

    if user_memory.get("goals"):
        lines.append(f"- Their goals: {', '.join(user_memory['goals'][-10:])}")

    if user_memory.get("dreams"):
        lines.append(f"- Their dreams: {', '.join(user_memory['dreams'][-10:])}")

    if user_memory.get("routine_notes"):
        lines.append(f"- Routine/habits: {', '.join(user_memory['routine_notes'][-10:])}")

    if user_memory.get("important_people"):
        lines.append(f"- Important people in their life: {', '.join(user_memory['important_people'][-10:])}")

    if user_memory.get("key_events"):
        lines.append(f"- Key life events they've shared: {', '.join(user_memory['key_events'][-10:])}")

    if user_memory.get("activities"):
        lines.append(f"- Things they've been doing lately: {', '.join(user_memory['activities'][-8:])}")

    return "\n".join(lines)


async def extract_memory(user_message: str) -> ExtractedMemory:
    """
    Silently extract structured memory from a user message using GPT-4o-mini.
    Fast and cheap — runs in parallel with the main response.
    """
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_tokens=300,
            temperature=0,
            response_format={"type": "json_object"},
        )
        data = json.loads(response.choices[0].message.content)
        return ExtractedMemory(**data)
    except Exception:
        # Never let extraction failure break the chat
        return ExtractedMemory()


async def get_sable_response(
    user_message: str,
    conversation_history: List[Dict[str, str]],
    user_name: str,
    user_memory: dict,
) -> str:
    """
    Get Sable's reply. Injects the user's full memory as context.
    conversation_history: [{"role": "user"/"assistant", "content": "..."}]
    """
    memory_context = _build_memory_context(user_memory, user_name)

    messages = [{"role": "system", "content": SABLE_SYSTEM_PROMPT}]

    if memory_context:
        messages.append({
            "role": "system",
            "content": memory_context,
        })

    # Last 40 messages — enough context without blowing token budget
    messages.extend(conversation_history[-40:])
    messages.append({"role": "user", "content": user_message})

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.85,
        max_tokens=1024,
        presence_penalty=0.3,
        frequency_penalty=0.2,
    )

    return response.choices[0].message.content


async def generate_session_title(first_message: str) -> str:
    """Auto-generate a short session title from the first message."""
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Generate a very short (3-6 words) title for a chat session based on the user's message. Return only the title, nothing else, no quotes.",
                },
                {"role": "user", "content": first_message},
            ],
            max_tokens=20,
            temperature=0.5,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "New Conversation"
