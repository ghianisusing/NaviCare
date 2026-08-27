# NaviCare

**A full-stack healthcare patient-navigation platform with a real, safety-first LLM agent system.**

NaviCare is a patient portal where users register, manage a profile, and talk
to an AI Patient Navigator that classifies what they need, answers general
health questions using retrieval-augmented generation over a curated
knowledge base, assesses symptom urgency, and — for anything that could be
a medical emergency — hands off to a deterministic, non-LLM safety system
that has the final say. It's built as a multi-agent architecture on top of
a production-style Django/React stack, not a single prompt wrapped in a
chat UI.

---

## What it does

- **Patient accounts & profiles** — JWT-based registration/login, with
  strict per-patient data isolation (no patient can reach another
  patient's profile or conversations by guessing an ID).
- **Persistent conversations** — every message and AI response is stored,
  with a rolling, non-clinical conversation summary used to keep later
  turns aware of context without re-sending the full history.
- **An AI Navigator Agent** that reads a patient's message and decides
  what should happen next: answer directly, ask a clarifying question, or
  route to a specialist.
- **A Retrieval-Augmented Information Agent** that answers general
  healthcare questions ("What is an MRI?", "What does fasting before a
  blood test mean?") only from a curated, source-attributed knowledge
  base — it cites where an answer came from, and explicitly says "I don't
  have enough information" rather than guessing when nothing relevant is
  found.
- **A Triage Agent** that assesses how urgently a patient's described
  symptoms may need attention (routine / urgent / emergency) through
  targeted follow-up questions, without ever diagnosing.
- **A deterministic Safety layer** — a database-backed, versioned rule
  engine (regex triggers → severity → fixed response) that runs
  independently of the LLM and can only ever escalate urgency, never
  downgrade it. An emergency-pattern match short-circuits the entire
  agent pipeline before the LLM is even called.

## Why it's interesting (the engineering, not just the demo)

Most "AI chatbot" projects are a system prompt and an API call. NaviCare is
built around a principle that matters a lot in a healthcare context:

> **The LLM helps understand and communicate. It never has sole authority
> over patient safety.**

That shows up concretely, not just as a line in a prompt:

- **Emergency detection doesn't depend on the model.** A regex-based
  safety check runs against every raw patient message *before* any LLM
  call happens. If it matches, the pipeline stops immediately and returns
  a fixed, hand-written response — the model is never in the loop for the
  highest-stakes decision in the system, and can't fail, hallucinate, or
  be prompt-injected out of it.
- **Safety rules are escalation-only, by construction.** Every place a
  severity level is computed, the code enforces that a rule can raise
  urgency relative to what an agent already concluded, but nothing can
  ever lower it. This is a structural guarantee, not a prompt instruction.
- **RAG that refuses to hallucinate.** The Information Agent runs
  retrieval first; if nothing in the knowledge base clears a similarity
  threshold, the LLM is never called at all — the patient gets an honest
  "I don't have enough information" instead of a fluent-sounding guess.
  Sources shown to the patient always come from the retrieval layer
  itself, never parsed out of the model's output, so a citation can never
  be fabricated.
- **All LLM output is schema-validated, not trusted.** Every agent (
  Navigator, Information, Triage) returns strict JSON checked against an
  allow-list of fields and values before anything downstream — the API,
  the database, the patient — ever sees it. Malformed or out-of-range
  output is rejected outright and replaced with a safe fallback message.
- **A confidence score that's never shown as a probability.** The Triage
  Agent produces an internal confidence value that is explicitly kept out
  of every patient-facing response — deliberately, to avoid a model's
  self-reported confidence being mistaken for a clinical likelihood.
- **Every agent-layer failure has a safe fallback.** LLM timeouts,
  provider errors, and malformed responses are all caught and mapped to
  a calm, generic message — and the deterministic emergency check still
  runs even when the LLM is completely unavailable, so an outage can
  never suppress a safety response.

## Architecture

```
                         ┌──────────────┐
                         │    Patient   │
                         └──────┬───────┘
                                ↓
                     React (Vite) + JWT auth
                                ↓
                     Django REST API + DRF
                                ↓
                       Conversation Service
                                ↓
                  Deterministic emergency pre-check
                     (independent of the LLM)
                                ↓
                       Navigator Agent (LLM)
                                │
                ┌───────────────┼────────────────┐
                ↓               ↓                 ↓
        Information Agent   Triage Agent    Emergency Concern
                │               │                 │
                ↓               ↓                 ↓
         RAG over a         Structured        Safety Layer
       curated knowledge   urgency + rule-      (fixed,
        base, source-       based escalation    non-LLM
        attributed             (never LLM-      response)
         answers                downgraded)
                │               │                 │
                └───────────────┼─────────────────┘
                                ↓
                     Final safety validation
                                ↓
                    Persisted to PostgreSQL,
                    returned to the patient
```

Every arrow in that diagram is a real, testable service boundary in the
code — not just a conceptual layer. The LLM provider itself sits behind an
interface (`LLMProvider`) so the model/vendor can be swapped without
touching any agent logic.

## Feature checklist

**Core platform**
- [x] JWT authentication (register / login / logout / refresh, with
  refresh-token blacklisting)
- [x] Per-patient data isolation enforced at the query level, not just
  the UI (cross-patient access returns 404, not a data leak)
- [x] Patient profile management
- [x] Persistent, multi-turn conversations with a rolling summary for
  long-context efficiency
- [x] Consistent, sanitized API error handling — no stack traces or raw
  exceptions ever reach the client
- [x] Structured, patient-content-free logging (intents, latencies,
  success/failure — never message text or credentials)

**AI agent system**
- [x] Navigator Agent — LLM-backed intent classification and routing,
  with strict JSON schema validation on every response
- [x] Information Agent — retrieval-augmented generation with a
  similarity-thresholded, hallucination-resistant fallback and real
  source citations
- [x] Triage Agent — structured symptom urgency assessment with
  internal-only confidence scoring
- [x] Deterministic Safety layer — versioned, database-backed rule
  engine with an escalation-only guarantee and a hardcoded fail-safe
  floor that doesn't depend on the database being healthy
- [x] LLM provider abstraction — the agent layer depends on an
  interface, not a specific vendor SDK
- [x] Configurable document chunking + embedding + retrieval pipeline
  for the knowledge base
- [x] Admin-only knowledge base management API (patients never write to
  it directly)

**Frontend**
- [x] React SPA with protected/guest routing and JWT auto-refresh
- [x] A calm, healthcare-appropriate chat UI — typing indicator, retry
  on failed sends, source citations under grounded answers, and a
  clearly (but non-alarmingly) flagged urgency banner for
  urgent/emergency responses

**Quality**
- [x] 122 automated backend tests covering authentication, patient
  privacy, conversation persistence, LLM output schema validation,
  retrieval precision, safety-rule escalation guarantees, and
  end-to-end agent routing — including explicit tests that the LLM is
  never called at all on an emergency pre-check match

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 19, Vite, React Router, Axios |
| Backend | Django 6, Django REST Framework |
| Auth | JSON Web Tokens (`djangorestframework-simplejwt`) |
| Database | PostgreSQL (SQLite-compatible for local dev) |
| LLM | Anthropic Messages API via a custom provider abstraction |
| Retrieval | Custom chunking + embedding + cosine-similarity retrieval pipeline |
| Testing | Django's test framework, 122 tests across 8 Django apps |

## Project structure

```
navicare/
├── backend/            Django REST API
│   ├── users/            authentication
│   ├── patients/         patient profiles
│   ├── conversations/    conversation & message persistence
│   ├── agents/
│   │   ├── core/           LLM provider abstraction, context management
│   │   ├── navigator/      intent classification & routing
│   │   ├── information/    RAG-grounded Q&A
│   │   └── triage/         symptom urgency assessment
│   ├── knowledge/         healthcare knowledge base, ingestion, retrieval
│   └── safety/            deterministic, versioned safety rule engine
└── frontend/           React SPA
    └── src/
        ├── api/            typed API client with JWT auto-refresh
        ├── context/        auth state
        ├── components/     route guards, app shell
        └── pages/          login, register, dashboard, profile, chat
```

## Status

This is a portfolio/demonstration project built in phased milestones
(foundation → agent architecture → knowledge & safety), each with its own
passing test suite before moving to the next. Appointment booking, real
clinical records, and external healthcare system integrations are
explicitly out of scope — the focus of this build is the agent
architecture and the safety guarantees around it, not a production EHR
integration.

**NaviCare does not diagnose patients, prescribe medication, or make
autonomous medical decisions at any point in the system.**
