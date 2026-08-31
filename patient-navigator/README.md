# NaviCare — Phase 4: Healthcare Actions, Appointments & Tool Calling

NaviCare's Navigator Agent now takes real, controlled actions. An
**Appointment Agent**, backed by an explicit tool-calling framework, can
search departments and providers, find bookable slots, and propose
booking, cancelling, or rescheduling an appointment — but it can never
touch the database itself. Every mutating action is validated,
authorized, and executed by Django, only after the patient explicitly
confirms it.

## What's new in Phase 4

- **Appointment domain**: `Department`, `Provider`, `Availability`, and
  `Appointment` models, plus fictional development providers to book
  against.
- **A controlled tool registry** (`tools/`): the LLM can only ever
  request a tool that's registered here — `search_departments`,
  `search_providers`, `find_available_slots`, `get_patient_appointments`,
  `book_appointment`, `cancel_appointment`, `reschedule_appointment`.
  Every argument is validated against a typed schema before it goes
  anywhere near the database; an unknown tool name or malformed argument
  is rejected outright.
- **An Appointment Agent** (`agents/appointment/`) that runs a
  deliberately *bounded* tool loop — at most two LLM calls per patient
  turn: one to decide what's needed, and (for read-only lookups only) a
  second to phrase an answer grounded in the real result, so the agent
  is never describing data it never actually saw.
- **Mutating actions are proposals, not actions.** Booking, cancelling,
  and rescheduling are never executed by the agent — they become a
  pending, patient-visible `AgentAction` that only becomes real once the
  patient explicitly confirms it through a dedicated endpoint.
- **A shared appointment service layer**
  (`appointments/services/appointment_service.py`) that both the direct
  REST API and the agent's tools call into — there is exactly one place
  appointment business logic lives.
- **Database-enforced double-booking prevention**: a transaction + row
  lock re-checks availability at booking time, backed by a database
  `UniqueConstraint` as the final guarantee even under a race.
- **An appointment dashboard** showing upcoming appointments with
  cancel/reschedule actions, and a chat UI that renders selectable slot
  cards, appointment lists, and confirm/decline cards inline.

## Architecture

```
                              PATIENT
                                 │
                                 ↓
                          React Frontend
                                 │
                                 ↓
                          Django REST API
                                 │
                                 ↓
                         Conversation Service
                                 │
                                 ↓
                         ┌─────────────────┐
                         │ Navigator Agent │
                         └────────┬────────┘
                                  │
              ┌───────────────────┼────────────────────┐
              ↓                   ↓                    ↓
       Information             Triage            Appointment
          Agent                Agent                 Agent
              │                   │                    │
              ↓                   ↓                    ↓
             RAG             Safety Rules         Tool Registry
                                                       │
                              ┌────────────────────────┼─────────────┐
                              ↓                        ↓             ↓
                       Search Providers          Find Slots       Book /
                                                                Cancel / Reschedule
                              │                        │             │
                              └────────────────────────┼─────────────┘
                                                       ↓
                                             Appointment Service
                                                       │
                                                       ↓
                                                  PostgreSQL
```

**The LLM never has a code path to the database.** It can only ever
produce a structured tool request (`agents/appointment/schemas.py`),
which is validated against the tool registry
(`tools/registry.py` + `tools/schemas.py`) and, for anything that
mutates data, only ever *proposed* — recorded as a pending `AgentAction`
— never executed inline. Execution happens exclusively through
`appointments/services/appointment_service.py`, driven either by a
patient hitting the confirm endpoint (agent path) or a direct REST call
(dashboard path). Both paths share the same service layer, so there is
no appointment business logic duplicated between "the API" and "the
agent."

```
Patient message
      ↓
Navigator Agent — classifies intent
      ↓ APPOINTMENT_REQUEST / APPOINTMENT_CHANGE
Appointment Agent — decides what tool (if any) is needed
      ↓
  read-only tool?                    mutating tool?
      ↓                                    ↓
  execute immediately              record as pending AgentAction
  (search/find/view)               (book/cancel/reschedule) —
      ↓                            never executed here
  ground a 2nd LLM call in               ↓
  the real result                  patient confirms via
      ↓                            POST .../agent-actions/{id}/confirm/
  response + selectable                  ↓
  cards to the patient             appointment_service re-validates
                                    availability/ownership inside a
                                    transaction, then executes
```

**Safety still comes first.** The deterministic emergency pre-check
(Phase 3) runs on every message before the Navigator Agent is even
called — a message that both requests an appointment *and* describes a
possible emergency ("I'm having chest pain, can you book me an
appointment next month?") is caught there and never reaches the
Appointment Agent at all. Safety takes precedence over convenience.

## Technology stack

- **Frontend:** React 19, Vite, React Router, Axios
- **Backend:** Django 6, Django REST Framework
- **Database:** PostgreSQL (via `dj-database-url`; SQLite-compatible for
  local dev/tests)
- **Auth:** JWT (`djangorestframework-simplejwt`)
- **LLM:** Anthropic Messages API behind a provider abstraction
  (`agents/core/llm.py`)
- **Retrieval:** custom chunking + embedding + cosine-similarity pipeline
  (`knowledge/`)

## Project structure

```
patient-navigator/
├── backend/
│   ├── users/, patients/, conversations/    core platform (Phase 1–2)
│   ├── knowledge/, safety/                  RAG + deterministic safety (Phase 3)
│   ├── appointments/                        scheduling domain — new in Phase 4
│   │   ├── models.py                          Department, Provider, Availability,
│   │   │                                       Appointment, AgentAction
│   │   ├── services/appointment_service.py    the single source of truth for
│   │   │                                       appointment business logic
│   │   ├── views.py, urls.py                  direct REST API + agent-action
│   │   │                                       confirm/decline endpoints
│   │   └── management/commands/               seed_appointments
│   ├── tools/                                 controlled tool-calling framework
│   │   ├── registry.py, schemas.py             the only way a tool becomes callable
│   │   └── appointment_tools.py                concrete tool definitions
│   └── agents/
│       ├── core/, navigator/, information/, triage/    Phase 2–3
│       └── appointment/                        new in Phase 4 — bounded tool loop
│           ├── agent.py, prompts.py, schemas.py, service.py
│
└── frontend/
    └── src/
        ├── api/appointments.js               appointments + agent-action client
        ├── pages/Dashboard.jsx                upcoming appointments section
        └── pages/Chat.jsx                     slot cards, confirm/decline cards
```

## Installation

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then edit .env — LLM_API_KEY is required for real replies
python manage.py migrate
python manage.py seed_safety_rules
python manage.py seed_knowledge_base
python manage.py seed_appointments      # fictional departments/providers/availability
python manage.py createsuperuser
python manage.py runserver
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

## Running tests

```bash
cd backend
python manage.py test          # 203 tests
```

## API overview (new in Phase 4)

```
# Read-only, any authenticated patient
GET  /api/departments/
GET  /api/providers/?department=&query=
GET  /api/appointments/available-slots/?department=&provider=&date=

# Direct appointment management — scoped to the requesting patient
GET    /api/appointments/            list own appointments
POST   /api/appointments/            book directly (executes immediately)
GET    /api/appointments/{id}/       retrieve (own only — 404 otherwise)
PATCH  /api/appointments/{id}/       reschedule (executes immediately)
DELETE /api/appointments/{id}/       cancel (executes immediately)

# Agent-proposed action confirmation — the only place a chat-proposed
# booking/cancel/reschedule actually executes
POST /api/appointments/agent-actions/{id}/confirm/
POST /api/appointments/agent-actions/{id}/decline/
```

The chat endpoint (`POST /api/conversations/{id}/messages/`) is
unchanged in shape from earlier phases, but assistant messages can now
carry `appointment_data` (selectable slot/appointment/provider cards)
and `pending_action` (a confirm/decline card) alongside the usual
`content`, `urgency`, and `sources`.

## Development roadmap

```
Phase 1 — Foundation
Phase 2 — Navigator Agent
Phase 3 — Healthcare Knowledge, Triage & Safety
Phase 4 — Healthcare Actions, Appointments & Tool Calling   (this repo)
Phase 5 — Follow-up + Notifications
Phase 6 — Safety + Human Escalation
Phase 7 — Deployment + Monitoring
```

Real hospital/insurance integrations, payment processing, prescription
ordering, real clinical records, and autonomous treatment decisions
remain explicitly out of scope.
