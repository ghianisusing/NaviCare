# NaviCare — Phase 5: Follow-Up, Reminders & Proactive Care Coordination

NaviCare can now act **without a new patient message**. A Follow-Up Agent
creates navigation tasks and reminders on request, a background worker
sends notifications when they come due, and the patient sees a persistent
care-navigation timeline — not just a chat log. This is the shift from a
request/response chatbot to an agentic system with real, scheduled,
proactive behavior.

## What's new in Phase 5

- **A Follow-Up Agent** (`agents/follow_up/`) that creates and manages
  navigation tasks and reminders — never clinical instructions. Same
  bounded, max-2-LLM-calls-per-turn design as the Appointment Agent
  (Phase 4): read-only lookups execute inline and get grounded in a
  second call; completing or cancelling something is only ever
  *proposed*, requiring the same explicit confirm/decline flow used for
  appointments.
- **`FollowUp` and `Reminder` models**, decoupled from each other — one
  follow-up can have multiple reminders (e.g. 24 hours before, then 2
  hours before).
- **A notification abstraction** (`notifications/`) with an in-app
  channel implemented and an email channel stubbed to show the
  extension point, plus a `Notification` model that's the actual
  in-app inbox.
- **An idempotent background worker** (`notifications/tasks.py`, run via
  `manage.py process_reminders`) that sends due reminders and expires
  overdue follow-ups. Running it twice — or having two overlapping runs
  — never produces a duplicate notification: each reminder is
  re-checked under a row lock immediately before being marked sent.
- **Proactive behavior, demonstrated end-to-end**: book an appointment →
  offer a reminder → the reminder fires on its own later, with no
  further patient message, and shows up as a notification.
- **A patient-facing Follow-Ups page and Notifications inbox**, plus
  Navigator routing for follow-up/reminder requests made in plain
  language ("what reminders do I have," "cancel that reminder," "I
  already did that").
- **Per-patient timezone** (`Patient.timezone`) so reminder times are
  never silently assumed to be UTC when shown to the patient, and the
  Follow-Up Agent normalizes natural-language dates ("tomorrow," "next
  Friday") against the patient's actual timezone and the current date —
  the backend still validates the resulting datetime server-side rather
  than trusting the model's arithmetic blindly.

## Architecture

```
                              PATIENT
                                 │
                                 ↓
                         React Frontend
                                 │
                                 ↓
                          Django API
                                 │
                                 ↓
                        Navigator Agent
                                 │
       ┌─────────────────────────┼────────────────────────┐
       ↓                         ↓                        ↓
 Information                  Triage        Appointment / Follow-Up
    Agent                     Agent               Agents
       │                         │                        │
       ↓                         ↓                        ↓
      RAG                   Safety Rules             Tool Registry
                                                        │
                                              Appointment / Follow-Up
                                                    Service
                                                        │
                                                        ↓
                                                   PostgreSQL
                                                        ↑
                                                        │
                                                 Reminder System
                                                        │
                                                        ↓
                                               Background Worker
                                              (manage.py process_reminders)
                                                        │
                                                        ↓
                                                 Notifications
                                                        │
                                                        ↓
                                                    Patient
```

**The confirmation pattern generalizes across domains.** `AgentAction` —
introduced in Phase 4 for appointment proposals — is a domain-agnostic
audit/pending-confirmation record; the Follow-Up Agent's
complete/cancel proposals reuse the exact same table and the exact same
`POST /api/appointments/agent-actions/{id}/confirm|decline/` endpoints as
appointments do. There is one confirmation mechanism in the system, not
one per feature.

**Idempotency is structural, not a flag.** A reminder only gets
processed while its status is `SCHEDULED`, re-checked inside a
row-locked transaction immediately before the notification is created
and the status flips to `SENT`. Two overlapping worker runs (or one run
happening twice) can't both win that race — see
`notifications/tasks.py:_process_one_reminder`.

**Background jobs stay administrative.** The worker can create a
notification, mark a reminder sent, or expire an overdue follow-up. It
never diagnoses, changes a medication, or makes a clinical decision —
per the Phase 5 boundary, follow-ups are navigation/administrative
tasks only.

## No Celery/Redis in this environment

Phase 5 calls for background processing "using Celery + Redis or the
existing background-task infrastructure if already present." Neither is
available in this project's environment, so `notifications/tasks.py`
exposes a plain, idempotent Python function
(`process_due_reminders`/`run_maintenance_cycle`) invoked by the
`process_reminders` management command instead. Run it on a schedule
(cron, a platform's scheduled-job feature, etc.). In a deployment with
Celery available, this function is exactly what a periodic Celery
task's body would call — the idempotency and row-locking already
implemented don't change; only the trigger mechanism would.

## Technology stack

- **Frontend:** React 19, Vite, React Router, Axios
- **Backend:** Django 6, Django REST Framework
- **Database:** PostgreSQL (via `dj-database-url`; SQLite-compatible for
  local dev/tests)
- **Auth:** JWT (`djangorestframework-simplejwt`)
- **LLM:** Anthropic Messages API behind a provider abstraction
- **Background processing:** idempotent management command (see above)

## Project structure

```
patient-navigator/
├── backend/
│   ├── users/, patients/, conversations/       core platform (Phase 1–2)
│   ├── knowledge/, safety/                     RAG + deterministic safety (Phase 3)
│   ├── appointments/                           scheduling domain (Phase 4)
│   ├── follow_ups/                              new in Phase 5
│   │   ├── models.py                              FollowUp, Reminder
│   │   ├── services/follow_up_service.py           single source of truth
│   │   ├── views.py, urls.py                       REST API
│   │   └── management/commands/                   (seed data lives in appointments)
│   ├── notifications/                           new in Phase 5
│   │   ├── models.py                              Notification
│   │   ├── services.py                            channel abstraction (in-app, email stub)
│   │   ├── tasks.py                                idempotent reminder processing
│   │   └── management/commands/process_reminders.py
│   ├── tools/
│   │   ├── appointment_tools.py                   Phase 4
│   │   └── follow_up_tools.py                      new in Phase 5
│   └── agents/
│       ├── core/, navigator/, information/, triage/, appointment/
│       └── follow_up/                              new in Phase 5
│           ├── agent.py, prompts.py, schemas.py, service.py
│
└── frontend/
    └── src/
        ├── api/followUps.js, notifications.js    new in Phase 5
        └── pages/FollowUps.jsx, Notifications.jsx  new in Phase 5
```

## Installation

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_safety_rules
python manage.py seed_knowledge_base
python manage.py seed_appointments
python manage.py createsuperuser
python manage.py runserver
```

To exercise the proactive-reminder flow locally: book an appointment,
create a reminder scheduled a minute or two out, then run

```bash
python manage.py process_reminders
```

and check `GET /api/notifications/` (or the Notifications page) — no
new chat message required.

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
python manage.py test          # 272 tests
```

## API overview (new in Phase 5)

```
GET    /api/follow-ups/                        list own follow-ups
POST   /api/follow-ups/                         create one
GET    /api/follow-ups/{id}/                    retrieve (own only)
PATCH  /api/follow-ups/{id}/                    {"status": "completed"|"cancelled"}
DELETE /api/follow-ups/{id}/                    cancel
POST   /api/follow-ups/appointment-reminder/    one-click "remind me" after booking

GET    /api/reminders/
POST   /api/reminders/
PATCH  /api/reminders/{id}/                     reschedule
DELETE /api/reminders/{id}/                     cancel

GET    /api/notifications/?unread=1
PATCH  /api/notifications/{id}/read/
```

Agent-proposed complete/cancel actions still go through the shared
`POST /api/appointments/agent-actions/{id}/confirm|decline/` endpoints
introduced in Phase 4 — see "Architecture" above.

## Development roadmap

```
Phase 1 — Foundation
Phase 2 — Navigator Agent
Phase 3 — Healthcare Knowledge, Triage & Safety
Phase 4 — Healthcare Actions, Appointments & Tool Calling
Phase 5 — Follow-Up, Reminders & Proactive Care Coordination   (this repo)
Phase 6 — Safety + Human Escalation
Phase 7 — Deployment + Monitoring
```

At this point NaviCare has an orchestrating agent, specialized agents,
RAG, deterministic safety controls, controlled tool execution,
persistent state, scheduled background work, and proactive patient
notifications — the next phase is about human escalation, observability,
and hardening, not new user-facing features.
