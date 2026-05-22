# Sable Dreams API 🌙

Your personal AI companion. One chat — Sable handles everything.

---

## How it works

There is **one chat endpoint**. The user just talks. Sable does the rest:

- Detects and saves **mood** automatically from the conversation
- Picks up on **goals and dreams** as they're mentioned
- Notes **daily routines and habits**
- Remembers **important people** in the user's life
- Tracks **key life events**
- References all of this naturally in future conversations — like a real friend

Everything is stored in a persistent **memory document** per user, built silently from every message they send.

---

## Setup

```bash
# 1. Create virtual environment
python -m venv venv
venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
copy .env.example .env
# Edit .env — add your OPENAI_API_KEY, MONGODB_URL, SECRET_KEY

# 4. Run
python run.py
```

API docs: **http://localhost:8000/docs**

---

## Endpoints

### Auth
```
POST   /api/v1/auth/register     Register
POST   /api/v1/auth/login        Login → get token
GET    /api/v1/auth/me           Current user
```

### Chat (everything lives here)
```
POST   /api/v1/chat/message              Send a message to Sable
GET    /api/v1/chat/sessions             List all sessions
GET    /api/v1/chat/sessions/{id}        Full conversation history
DELETE /api/v1/chat/sessions/{id}        Delete a session
GET    /api/v1/chat/memory               See what Sable knows about you
```

---

## Usage

### Start a new conversation
```json
POST /api/v1/chat/message
Authorization: Bearer <token>

{
  "message": "Hey Sable, I had the worst day today"
}
```

### Continue an existing session
```json
POST /api/v1/chat/message
Authorization: Bearer <token>

{
  "message": "Remember that story I told you yesterday?",
  "session_id": "683abc123def456"
}
```

### Response
```json
{
  "session_id": "683abc123def456",
  "reply": "Oh no, tell me everything. What happened?",
  "timestamp": "2026-05-22T10:30:00Z"
}
```

---

## Memory system

Every user message is silently processed by a fast extraction model (GPT-4o-mini) that pulls out:

| Field | Example |
|---|---|
| `mood` | "anxious", "happy", "overwhelmed" |
| `energy_level` | "tired", "motivated" |
| `goals` | "become a doctor", "learn guitar" |
| `dreams` | "travel to Japan", "write a book" |
| `routine_notes` | "wakes up at 7am", "skips breakfast" |
| `important_people` | "mom", "best friend Sara" |
| `key_events` | "got a promotion", "had a fight with sister" |
| `activities` | "went to gym", "cooked dinner" |

This builds a **persistent memory profile** per user. Sable reads this before every reply and references it naturally — making every conversation feel personal and continuous.

---

## MongoDB Collections

| Collection | Purpose |
|---|---|
| `users` | Auth accounts |
| `chat_sessions` | Conversation history (all messages) |
| `user_memory` | Persistent memory profile per user |
