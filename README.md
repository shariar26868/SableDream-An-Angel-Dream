# Sable Dreams API 🌙

Your personal AI companion. One chat — Sable handles everything.

---

## What Was Delivered

- Built a FastAPI backend for an AI companion chatbot named **Sable**, powered by **GPT-4o**
- Sable has a warm, empathetic friend personality — not robotic, listens first, never judges
- Sable matches the user's energy and language style in every response
- Designed a **single chat endpoint** — everything (mood, goals, dreams, routine) is handled through conversation, no separate endpoints needed
- Built a **silent memory extraction system** — every user message is automatically analyzed by GPT-4o-mini in parallel to extract mood, energy level, goals, dreams, daily routine, important people, key events, and activities
- All extracted data is saved to a **persistent memory profile** per session in MongoDB
- Sable reads this memory before every reply and references past things naturally, like a real friend would
- Built **session management** — `session_id` is optional; omit it to start a new conversation, include it to continue an existing one
- Sessions are **auto-titled** from the first message using AI
- Removed authentication entirely to keep the API simple and frictionless
- Connected to **MongoDB Atlas** (cloud database) for persistent storage
- Added a `/memory` endpoint so users can see exactly what Sable has learned about them
- Wrote a **Dockerfile** and **docker-compose.yml** for containerized deployment
- Added `.dockerignore` to keep secrets and cache out of the Docker image
- Added `.gitignore` to prevent `.env` from ever being committed to GitHub
- Fixed a **GitHub secret scanning violation** — removed a leaked OpenAI API key from git history by rewriting commits with a clean orphan branch
- Fixed a **500 crash bug** where passing an invalid `session_id` caused an unhandled MongoDB error — now returns a clean 400 response with a helpful message
- Deployed successfully on a live server via Docker

---

## API Endpoints

```
POST   /api/v1/chat/message              Send a message to Sable
GET    /api/v1/chat/sessions             List all sessions
GET    /api/v1/chat/sessions/{id}        Full conversation history
GET    /api/v1/chat/sessions/{id}/memory What Sable knows about you
DELETE /api/v1/chat/sessions/{id}        Delete a session
```

---

## Tech Stack

- **FastAPI** — Python web framework
- **MongoDB Atlas** — Cloud database
- **Motor** — Async MongoDB driver
- **OpenAI GPT-4o** — Main chat model
- **OpenAI GPT-4o-mini** — Silent memory extraction
- **Docker** — Containerized deployment

---

## MongoDB Collections

| Collection | Purpose |
|---|---|
| `chat_sessions` | All conversation history |
| `session_memory` | Persistent memory profile per session |

---

## Setup

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # fill in your keys
python run.py
```

Docs: **http://localhost:8000/docs**

---

## Docker

```bash
docker-compose up --build -d
docker-compose down
```
