# Patient Navigator — Phase 2: Navigator Agent

A healthcare patient-portal application: registration, authentication, patient
profiles, and a conversational interface backed by a real, LLM-driven
**Navigator Agent** with persisted conversation history. The Navigator
understands what a patient is asking for, classifies intent, decides whether
it needs to ask a clarifying question, and — for anything that could be a
medical emergency — hands off to a deterministic safety layer instead of
trusting the model's own judgment.

## What the project does

A patient can register, log in, view and edit their profile, and start a
conversation from their dashboard. Each message is sent to the Navigator
Agent, which classifies intent and urgency, decides on a next action, and
replies conversationally — all backed by a structured, validated output
contract rather than free-form text. The Navigator does not diagnose,
prescribe, or book anything; it coordinates and, where a capability isn't
built yet (appointments, lab follow-up, etc.), says so plainly.

## Architecture

```
React (Vite)  →  Django REST API  →  Django Services  →  PostgreSQL
                                          ↓
                                   Navigator Agent  →  LLM Provider
```

The frontend never talks to Postgres or the LLM provider directly, and no
database credentials, API keys, or LLM credentials are ever exposed to it.

```
API View (conversations/views.py)
      ↓
Chat Service (conversations/services/chat_service.py)
      ↓
Navigator Service (agents/navigator/service.py)
      ↓
Navigator Agent (agents/navigator/agent.py)  →  LLM Provider (agents/core/llm.py)
      ↓
Structured Output (agents/navigator/schemas.py) — validated, allow-listed
      ↓
Safety Validation (agents/navigator/safety.py) — deterministic, LLM-independent
      ↓
Chat Service persists the reply  →  API Response
```

**Safety is deterministic, not delegated to the LLM.** A regex-based
emergency check runs against the raw patient message independently of
whatever the model classified. If either the model *or* the regex layer
flags a possible emergency, the response is forced onto a fixed,
non-LLM-generated escalation message. The safety layer can only escalate a
result, never downgrade one the model already flagged.

**Agent routing without agents.** The Navigator can recommend routing to a
`triage`, `information`, `appointment`, `follow_up`, or `escalation` agent —
but none of those agents exist yet. For Phase 2, routing to any of them
returns a temporary "this is being prepared" response; the routing decision
itself is real and logged, it just doesn't invoke anything downstream yet.

## Technology stack

- **Frontend:** React 19, Vite, React Router, Axios
- **Backend:** Django 6, Django REST Framework, Simple JWT
- **Database:** PostgreSQL (via `dj-database-url`; falls back to local SQLite
  automatically if `DATABASE_URL` isn't set, so the backend and its tests run
  without a Postgres install)
- **Auth:** JWT access/refresh tokens (`djangorestframework-simplejwt`), with
  refresh-token blacklisting on logout
- **LLM:** Anthropic Messages API, called directly over HTTPS via `requests`
  (no SDK dependency) behind a small provider abstraction

## Project structure

```
patient-navigator/
├── backend/
│   ├── manage.py
│   ├── requirements.txt
│   ├── .env.example
│   ├── config/              # settings, root urls
│   ├── users/                # registration, login, logout, /me
│   ├── patients/             # Patient model + /api/patients/me/
│   ├── conversations/        # Conversation/Message models + chat API
│   │   └── services/          # chat_service.py — API-facing orchestration
│   ├── agents/                # the agent layer — new in Phase 2
│   │   ├── core/               # llm.py (provider abstraction), context.py,
│   │   │                       #   exceptions.py
│   │   ├── navigator/          # agent.py, prompts.py, schemas.py,
│   │   │                       #   safety.py, service.py
│   │   └── tests/
│   └── core/                  # shared DRF exception handling, permissions
│
└── frontend/
    ├── .env.example
    └── src/
        ├── api/               # axios client (JWT + refresh), auth/patients/conversations calls
        ├── context/           # AuthContext
        ├── components/        # ProtectedRoute, GuestRoute, AppShell (nav)
        ├── pages/             # Login, Register, Dashboard, Profile, Chat
        └── styles/            # design tokens
```

## Installation

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then edit .env — LLM_API_KEY is required for real replies
python manage.py migrate
python manage.py createsuperuser   # optional, for /admin/
python manage.py runserver
```

The backend serves the API at `http://localhost:8000/api/` and the admin at
`http://localhost:8000/admin/`. Without `LLM_API_KEY` set, the chat endpoint
still works end-to-end — the Navigator Service catches the resulting
`LLMUnavailableError` and falls back to a safe "temporarily unavailable"
message (or, if the patient's message matches an emergency pattern, the
fixed safety response) rather than erroring out.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env         # points VITE_API_BASE_URL at the backend
npm run dev
```

The frontend serves at `http://localhost:5173`.

## Environment variables

**Backend (`backend/.env`)**

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Django secret key — generate a real one for anything beyond local dev |
| `DEBUG` | `True`/`False` |
| `ALLOWED_HOSTS` | Comma-separated hostnames |
| `DATABASE_URL` | Postgres connection string, e.g. `postgres://user:pass@localhost:5432/patient_navigator` |
| `CORS_ALLOWED_ORIGINS` | Origins allowed to call the API |
| `CSRF_TRUSTED_ORIGINS` | Origins trusted for CSRF-protected requests |
| `SECURE_SSL_REDIRECT` | Only relevant when `DEBUG=False` |
| `LLM_PROVIDER` | Currently only `anthropic` is supported |
| `LLM_API_KEY` | Anthropic API key — leave blank to run in fallback-only mode |
| `LLM_MODEL` | Model name, e.g. `claude-sonnet-4-6` |

**Frontend (`frontend/.env`)**

| Variable | Purpose |
|---|---|
| `VITE_API_BASE_URL` | Base URL of the Django API, e.g. `http://localhost:8000/api` |

Nothing sensitive is ever committed — both `.env` files are git-ignored, and
only `.env.example` templates are checked in.

## Running the backend

```bash
cd backend
python manage.py runserver
python manage.py test          # run the full test suite (52 tests)
```

## Running the frontend

```bash
cd frontend
npm run dev      # local dev server
npm run build    # production build
```

## API overview

```
POST   /api/auth/register/            Create a user + patient profile, returns JWT pair
POST   /api/auth/login/               Returns JWT pair
POST   /api/auth/logout/              Blacklists the given refresh token
POST   /api/auth/token/refresh/       Exchanges a refresh token for a new access token
GET    /api/auth/me/                  Current user's basic account info

GET    /api/patients/me/              Current user's patient profile
PATCH  /api/patients/me/              Update current user's patient profile

GET    /api/conversations/            List the current patient's conversations
POST   /api/conversations/            Create a conversation
GET    /api/conversations/{id}/       Conversation detail + messages
GET    /api/conversations/{id}/messages/    List messages
POST   /api/conversations/{id}/messages/    Send a message → runs the Navigator Agent, returns its reply
```

The chat endpoint's shape hasn't changed since Phase 1 — the frontend has no
idea an LLM is now involved. Internally, `POST .../messages/` now: saves the
patient's message → builds bounded conversation context → runs the Navigator
Agent → validates its structured output → runs safety validation → persists
and returns the final assistant message.

Every conversation/patient endpoint is scoped to the authenticated user —
there is no id-based lookup that lets one patient reach another's data.
Cross-patient access attempts return `404`, matching endpoints resolve `me`
from the JWT rather than a URL parameter.

Errors are returned as `{"error": "<message>"}`, with `{"error": ..., "details": {...}}`
for field-level validation failures. Raw exceptions and stack traces are
never sent to the client; full detail is only ever logged server-side.

## The Navigator Agent

**Intents** (`agents/navigator/schemas.py`): `GENERAL_HEALTH_INFORMATION`,
`SYMPTOM_CONCERN`, `APPOINTMENT_REQUEST`, `APPOINTMENT_CHANGE`,
`LAB_RESULT_FOLLOWUP`, `MEDICATION_INFORMATION`, `GENERAL_NAVIGATION`,
`EMERGENCY_CONCERN`, `HUMAN_ASSISTANCE`, `UNKNOWN`.

**Structured output** — every Navigator turn produces (and every field is
validated against a fixed allow-list before use):

```json
{
  "intent": "GENERAL_NAVIGATION",
  "urgency": "normal",
  "needs_clarification": true,
  "clarifying_question": "What type of healthcare service are you looking for?",
  "recommended_action": "ASK_CLARIFYING_QUESTION",
  "target_agent": null,
  "response": "I can help you figure out which healthcare service you need."
}
```

Malformed or out-of-allow-list output is rejected outright — the turn falls
back to a safe generic message rather than letting an unvalidated value
reach application logic.

**Conversation context** (`agents/core/context.py`) — each turn sends the
conversation's rolling `summary` plus its most recent `MAX_CONTEXT_MESSAGES`
(20) messages, not the full history. The summary itself is regenerated by a
separate, small LLM call every few turns and is explicitly instructed never
to contain diagnoses or medical assumptions — only what the patient is
trying to accomplish and facts they've already stated.

**Safety validation** (`agents/navigator/safety.py`) — deterministic and
independent of the LLM. A fixed keyword/pattern check runs against the raw
patient message; if it matches, or if the agent's own output already flagged
`urgency: emergency`, the final response is forced to a fixed safety message
directing the patient to seek immediate care. This same fallback fires even
if the LLM call fails entirely, so an outage can never suppress an emergency
response.

**LLM provider abstraction** (`agents/core/llm.py`) — the agent layer only
depends on the `LLMProvider` interface, not a specific SDK or vendor. The
current `AnthropicProvider` calls the Messages API directly over HTTPS.

## Development roadmap

```
Phase 1 — Foundation
Phase 2 — Navigator Agent                     (this repo)
Phase 3 — Healthcare Knowledge + RAG
Phase 4 — Appointments + Tools
Phase 5 — Follow-up + Notifications
Phase 6 — Safety + Human Escalation
Phase 7 — Deployment + Monitoring
```

Phase 2 deliberately stops short of implementing the specialized agents
(`triage`, `information`, `appointment`, `follow_up`, `escalation`) —
`target_agent` values are real, validated, and logged, but nothing invokes
them yet. Phase 3+ builds those agents behind the same routing boundary
established here, and replaces today's regex-based safety layer with a
stronger deterministic triage system.
