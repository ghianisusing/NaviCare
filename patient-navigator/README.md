# NaviCare — Phase 3: Healthcare Knowledge, Triage & Safety

A healthcare patient-portal application with a real, LLM-driven **Navigator
Agent** that now routes to two specialized agents: an **Information Agent**
that answers general healthcare questions using retrieval-augmented
generation over a curated knowledge base, and a **Triage Agent** that
assesses how urgently a patient's described symptoms may need attention.
Both sit behind a deterministic, database-backed **Safety** layer that has
final say over anything that could be an emergency — the LLM helps
understand and communicate, but never has sole authority over patient
safety.

## What the project does

A patient can register, log in, view and edit their profile, and start a
conversation from their dashboard. The Navigator Agent classifies each
message and routes it:

- **General health questions** ("What is an MRI?") go to the **Information
  Agent**, which retrieves relevant passages from a curated knowledge base
  and grounds its answer in them — citing sources, and saying plainly when
  it doesn't have enough information rather than guessing.
- **Symptom descriptions** ("I've had a cough for three days") go to the
  **Triage Agent**, which asks targeted clarifying questions and assesses
  urgency (routine / urgent / emergency), without ever diagnosing.
- **Anything that could be an emergency** is caught by a deterministic
  safety check — independent of the LLM, checked before any agent is even
  invoked — and gets a fixed, non-LLM-generated response directing the
  patient to immediate care.

NaviCare does not diagnose, prescribe, or make autonomous medical
decisions at any point in this phase.

## Architecture

```
React (Vite)  →  Django REST API  →  Conversation Service  →  PostgreSQL
                                            ↓
                                     Navigator Agent
                                            │
                          ┌─────────────────┼─────────────────┐
                          ↓                 ↓                 ↓
                  Information Agent    Triage Agent    Emergency Concern
                          │                 │                 │
                          ↓                 ↓                 ↓
                   Knowledge Base      Safety Rules      Safety Layer
                          │                 │                 │
                          └─────────────────┼─────────────────┘
                                            ↓
                                   Final Safety Validation
                                            ↓
                                         Response
```

```
API View (conversations/views.py)
      ↓
Chat Service (conversations/services/chat_service.py)
      ↓
Navigator Service (agents/navigator/service.py)
      │
      ├─ Deterministic emergency pre-check (safety/) — runs BEFORE the
      │  Navigator LLM is even called. A match stops normal navigation
      │  immediately; nothing below this point runs.
      │
      ├─ Navigator Agent (LLM) → intent classification
      │        │
      │        ├─ GENERAL_HEALTH_INFORMATION → Information Agent
      │        │        agents/information/agent.py
      │        │        → knowledge.retrieval.retrieve() (RAG)
      │        │        → grounded LLM answer + real sources
      │        │
      │        ├─ SYMPTOM_CONCERN → Triage Agent
      │        │        agents/triage/agent.py
      │        │        → structured urgency assessment (LLM)
      │        │        → safety/service.py (escalation-only override)
      │        │
      │        └─ everything else → Navigator's own response, or a
      │                 "being prepared" message for appointment/follow_up
      │
      └─ safety.apply_safety_validation() — final backstop before
         anything reaches the patient
```

**Safety is deterministic, layered, and escalation-only.** The `safety/`
app holds a database-backed, versioned `SafetyRule` table (regex triggers →
severity → fixed response) that an admin can edit without a deploy, plus a
hardcoded baseline pattern that's checked regardless of database health —
a DB outage can reduce coverage to the baseline, never to nothing. Every
place a severity is computed (Navigator's pre-check, Triage's rule
integration), a rule can only ever *raise* the severity relative to what
an agent already concluded, never lower it. The final response text for
an emergency/urgent match is always the rule's fixed text, never
LLM-generated.

**RAG, not memorized answers.** The Information Agent never answers from
the LLM's general knowledge. `knowledge/retrieval.py` embeds the question,
finds the most similar chunks in the curated `HealthcareDocument` corpus,
and only calls the LLM with that retrieved context attached — if nothing
clears the similarity threshold, the LLM isn't even called; the patient
gets a fixed "I don't have enough information" response instead of a
guess. Sources shown to the patient always come from the retrieval layer,
never from the LLM's own output, so a citation can never be fabricated.

**Triage confidence stays internal.** The Triage Agent's structured output
includes a `confidence` score, but it is explicitly never surfaced to the
patient — not as a percentage, not as a probability — per Phase 3's
safety principle that a model's confidence must not be mistaken for a
medical probability.

## Technology stack

- **Frontend:** React 19, Vite, React Router, Axios
- **Backend:** Django 6, Django REST Framework, Simple JWT
- **Database:** PostgreSQL (via `dj-database-url`; falls back to local SQLite
  automatically if `DATABASE_URL` isn't set, so the backend and its tests run
  without a Postgres install)
- **Auth:** JWT access/refresh tokens (`djangorestframework-simplejwt`), with
  refresh-token blacklisting on logout
- **LLM:** Anthropic Messages API, called directly over HTTPS via `requests`
  behind a small provider abstraction
- **Retrieval:** a small, dependency-free hashing-trick bag-of-words
  embedding (`knowledge/embeddings.py`) with in-Python cosine similarity —
  see "Knowledge base" below for the trade-off and upgrade path

## Project structure

```
patient-navigator/
├── backend/
│   ├── manage.py
│   ├── requirements.txt
│   ├── .env.example
│   ├── config/                # settings, root urls
│   ├── users/                  # registration, login, logout, /me
│   ├── patients/               # Patient model + /api/patients/me/
│   ├── conversations/          # Conversation/Message models + chat API
│   │   └── services/            # chat_service.py — API-facing orchestration
│   ├── agents/
│   │   ├── core/                 # llm.py, context.py, exceptions.py
│   │   ├── navigator/            # agent.py, prompts.py, schemas.py,
│   │   │                         #   safety.py, service.py (orchestrator + router)
│   │   ├── information/          # RAG-grounded healthcare Q&A — new in Phase 3
│   │   └── triage/               # symptom urgency assessment — new in Phase 3
│   ├── knowledge/                # healthcare knowledge base — new in Phase 3
│   │   ├── models.py              # HealthcareDocument, DocumentChunk
│   │   ├── chunking.py, embeddings.py, ingestion.py, retrieval.py
│   │   ├── seed_data.py           # curated dev dataset
│   │   └── management/commands/  # seed_knowledge_base
│   ├── safety/                   # deterministic safety rules — new in Phase 3
│   │   ├── models.py              # SafetyRule
│   │   ├── rules.py, validator.py, service.py
│   │   └── management/commands/  # seed_safety_rules
│   └── core/                    # shared DRF exception handling, permissions
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
python manage.py seed_safety_rules      # loads the default deterministic safety rules
python manage.py seed_knowledge_base    # loads + embeds the curated knowledge base
python manage.py createsuperuser        # needed to manage knowledge docs via /admin/ or the API
python manage.py runserver
```

The backend serves the API at `http://localhost:8000/api/` and the admin at
`http://localhost:8000/admin/`. Without `LLM_API_KEY` set, the chat endpoint
still works end-to-end — every LLM-dependent path has a safe fallback
message, and the deterministic emergency pre-check still runs regardless.

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
| `KNOWLEDGE_CHUNK_SIZE` / `KNOWLEDGE_CHUNK_OVERLAP` | Document chunking (characters) |
| `EMBEDDING_DIM` | Dimensionality of the local hashing embedding |
| `KNOWLEDGE_RETRIEVAL_TOP_K` | How many chunks to retrieve per question |
| `KNOWLEDGE_MIN_SIMILARITY` | Similarity floor below which retrieval returns nothing (triggers the "insufficient information" fallback) |

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
python manage.py test          # run the full test suite (122 tests)
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
POST   /api/conversations/{id}/messages/    Send a message → Navigator Agent → reply

# Admin-only knowledge management (IsAdminUser / is_staff) — patients
# never access these directly, only indirectly via the Information Agent.
GET    /api/knowledge/documents/            List healthcare documents
POST   /api/knowledge/documents/            Create a document (auto-ingests it)
GET    /api/knowledge/documents/{id}/       Retrieve a document
PATCH  /api/knowledge/documents/{id}/       Update a document (re-ingests it)
DELETE /api/knowledge/documents/{id}/       Delete a document
POST   /api/knowledge/ingest/               Re-chunk and re-embed every document
```

The chat endpoint's shape hasn't changed since Phase 1 — the frontend has no
idea which specialist agent handled a given message. Internally, `POST
.../messages/` now: saves the patient's message → runs the deterministic
emergency pre-check → runs the Navigator Agent → routes to the Information
or Triage agent based on intent → runs final safety validation → persists
and returns the assistant message, now carrying `urgency` and `sources`
fields the frontend uses for an emergency banner and a source list.

Every conversation/patient endpoint is scoped to the authenticated user —
there is no id-based lookup that lets one patient reach another's data.
Cross-patient access attempts return `404`, matching endpoints resolve `me`
from the JWT rather than a URL parameter.

Errors are returned as `{"error": "<message>"}`, with `{"error": ..., "details": {...}}`
for field-level validation failures. Raw exceptions and stack traces are
never sent to the client; full detail is only ever logged server-side.

## Knowledge base

Seeded via `python manage.py seed_knowledge_base` with 10 curated documents
covering general health, diagnostic tests, symptoms, preventive care,
common procedures, and healthcare services — each recording its real
source (e.g. MedlinePlus, RadiologyInfo.org, USPSTF) rather than an
invented citation. Documents are chunked (`knowledge/chunking.py`,
sentence-boundary-aware, configurable size/overlap) and embedded
(`knowledge/embeddings.py`) on ingestion.

**On the embedding implementation:** this phase uses a small,
dependency-free hashing-trick bag-of-words embedding rather than a hosted
embedding API, so ingestion and retrieval work fully offline. It's
deliberately documented as prototype-grade — appropriate for a small
curated knowledge base, not a large corpus. `DocumentChunk.embedding` is
stored as a portable JSON list of floats (not a Postgres-specific vector
column), so a production deployment can swap in a real embedding model
behind the same `embed_text(text) -> list[float]` signature, and move
`knowledge/retrieval.py`'s in-Python cosine similarity scan to an indexed
vector column (e.g. pgvector) without changing anything upstream of it.

## Safety rules

Seeded via `python manage.py seed_safety_rules` with 9 default rules
spanning cardiac/respiratory, neurological, bleeding/trauma, mental health
crisis, and allergic reaction categories, each with a severity
(`emergency`/`urgent`), a regex trigger, and a fixed response. Rules are
manageable from `/admin/` (staff-only) — editing or deactivating a rule
takes effect immediately, no deploy required. See "Architecture" above for
the escalation-only guarantee that makes this safe to let admins edit
without re-reviewing the whole safety system each time.

## Development roadmap

```
Phase 1 — Foundation
Phase 2 — Navigator Agent
Phase 3 — Healthcare Knowledge, Triage & Safety      (this repo)
Phase 4 — Appointments + Tools
Phase 5 — Follow-up + Notifications
Phase 6 — Safety + Human Escalation
Phase 7 — Deployment + Monitoring
```

Phase 3 deliberately stops short of appointment booking, real hospital
integrations, medication prescribing, real clinical records, insurance
processing, or autonomous medical decisions — those are Phase 4+. The
`appointment` and `follow_up` routing targets remain "being prepared"
placeholders, same as Phase 2.
