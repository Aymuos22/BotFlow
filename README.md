# MindoraxAI — WhatsApp AI Chatbot Platform

MindoraxAI is a **multi-tenant SaaS platform** that lets any business deploy an AI-powered WhatsApp chatbot in minutes. Companies upload their knowledge base (product catalog, FAQs, docs) and immediately get an assistant that answers customer questions on WhatsApp — in English, Hindi, or Hinglish — with seamless escalation to human agents when needed.

---

## Table of Contents

1. [What It Does (Plain English)](#1-what-it-does)
2. [System Architecture](#2-system-architecture)
3. [Technology Stack](#3-technology-stack)
4. [Repository Layout](#4-repository-layout)
5. [Data Model](#5-data-model)
6. [API Reference](#6-api-reference)
7. [Authentication & Security](#7-authentication--security)
8. [Key Flows Explained](#8-key-flows-explained)
9. [Environment Variables](#9-environment-variables)
10. [Local Development Setup](#10-local-development-setup)
11. [Production Deployment (EC2)](#11-production-deployment-ec2)
12. [Running Tests](#12-running-tests)
13. [Ops & Admin Scripts](#13-ops--admin-scripts)

---

## 1. What It Does

```
Customer sends WhatsApp message
         │
         ▼
  MindoraxAI receives it via webhook (Twilio / Meta / AiSensy)
         │
         ├─ Searches your company's knowledge base (RAG)
         ├─ Generates a natural-language reply (Groq / OpenAI)
         ├─ Sends the reply back via WhatsApp
         │
         ├─ If the question is too hard → escalates to a human agent
         ├─ Tracks the conversation, leads, and analytics
         └─ Mirrors everything to Google Sheets (optional)
```

**Who uses this?**

| Role | What they do |
|------|-------------|
| **Super Admin** | Onboards new companies, manages platform users |
| **Company Admin** | Uploads documents, configures AI prompts, runs campaigns |
| **Human Agent** | Takes over conversations when the bot escalates |
| **End Customer** | Chats on WhatsApp — never knows about any of this |

**Current live use case:** SK Range wellness product catalog — customers ask about products, pricing, and availability on WhatsApp.

---

## 2. System Architecture

### High-Level Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                         CUSTOMERS                                    │
│              (WhatsApp on their phones)                              │
└──────────────────────────┬───────────────────────────────────────────┘
                           │  WhatsApp messages
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│              WHATSAPP GATEWAY (choose one per company)               │
│                                                                      │
│   ┌─────────────┐   ┌─────────────────┐   ┌──────────────────────┐  │
│   │   Twilio    │   │  Meta Cloud API │   │      AiSensy         │  │
│   │  (sandbox + │   │  (direct Meta   │   │  (Indian WhatsApp    │  │
│   │ production) │   │   integration)  │   │   BSP)               │  │
│   └──────┬──────┘   └────────┬────────┘   └──────────┬───────────┘  │
└──────────┼───────────────────┼────────────────────────┼─────────────┘
           │ HTTP webhooks     │                        │
           └───────────────────▼────────────────────────┘
                               │
                   ┌───────────▼────────────┐
                   │  FASTAPI BACKEND       │
                   │  (app/)                │
                   │                        │
                   │  ┌──────────────────┐  │
                   │  │  API Routers     │  │
                   │  │  (thin layer)    │  │
                   │  └────────┬─────────┘  │
                   │           │            │
                   │  ┌────────▼─────────┐  │
                   │  │  Services        │  │
                   │  │  (business logic)│  │
                   │  └────────┬─────────┘  │
                   │           │            │
                   │  ┌────────▼─────────┐  │
                   │  │  Repositories    │  │
                   │  │  (DB access)     │  │
                   │  └────────┬─────────┘  │
                   │           │            │
                   │  ┌────────▼─────────┐  │
                   │  │  Integrations    │  │
                   │  │  (external APIs) │  │
                   │  └──────────────────┘  │
                   └──────────┬─────────────┘
                              │
          ┌───────────────────┼──────────────────────┐
          │                   │                      │
          ▼                   ▼                      ▼
  ┌───────────────┐  ┌────────────────┐   ┌──────────────────┐
  │  PostgreSQL   │  │   Weaviate     │   │    AWS S3        │
  │  (Supabase)   │  │  (Vector DB)   │   │  (Document       │
  │               │  │               │   │   Storage)       │
  │  - Companies  │  │  - Document   │   │                  │
  │  - Users      │  │    chunks     │   │  - PDFs          │
  │  - Messages   │  │  - Product    │   │  - Excel files   │
  │  - Campaigns  │  │    catalog    │   │  - Word docs     │
  │  - Analytics  │  │  - Embeddings │   │                  │
  └───────────────┘  └────────────────┘   └──────────────────┘

          ┌───────────────────┐
          │  REACT PORTAL     │
          │  (web/)           │
          │                   │
          │  Admin + Tenant   │
          │  dashboard for:   │
          │  - Chat testing   │
          │  - Inbox          │
          │  - Campaigns      │
          │  - Analytics      │
          └───────────────────┘
```

### Internal Application Layers

The backend follows **Clean Architecture** — each layer has one job, and layers only talk to the layer below:

```
┌─────────────────────────────────────────────────────────────────────┐
│  HTTP REQUEST                                                       │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                 ┌─────────────▼──────────────┐
                 │   1. ROUTERS (app/api/)     │
                 │   Receive HTTP, validate    │
                 │   input, call service,      │
                 │   return response.          │
                 │   NO business logic here.   │
                 └─────────────┬──────────────┘
                               │
                 ┌─────────────▼──────────────┐
                 │   2. SERVICES (app/services)│
                 │   All business rules live   │
                 │   here. Orchestrate repos   │
                 │   and integrations.         │
                 └──────┬──────────────┬───────┘
                        │              │
          ┌─────────────▼───┐    ┌─────▼──────────────────┐
          │  3. REPOSITORIES│    │  4. INTEGRATIONS        │
          │  (app/repos/)   │    │  (app/integrations/)    │
          │  SQL queries,   │    │  Twilio, Meta, AiSensy  │
          │  no logic.      │    │  Weaviate, S3, LLM,     │
          └─────────────────┘    │  Google Sheets          │
                                 └─────────────────────────┘
```

### RAG Pipeline (How the AI Answers Questions)

RAG = Retrieval-Augmented Generation. Instead of the LLM relying only on its training data, it searches your company's actual knowledge base first.

```
Customer message: "What are the benefits of Ashwagandha capsules?"
         │
         ▼
┌────────────────────┐
│  1. Language       │   Detect: English / Hindi / Hinglish
│     Detection      │
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│  2. Query          │   Normalize query for search
│     Processing     │   (remove noise, extract intent)
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│  3. Retrieval      │   Search Weaviate vector DB:
│     (Weaviate)     │   - Semantic (embedding) search
│                    │   - Keyword (BM25) search
│                    │   - Hybrid (both combined)
│                    │   Returns top-K relevant chunks
└────────┬───────────┘
         │  (relevant document chunks)
         ▼
┌────────────────────┐
│  4. Product        │   Also search product catalog
│     Search         │   for matching products
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│  5. LLM Generation │   Send to Groq / OpenAI:
│                    │   - System prompt (company-specific)
│                    │   - Retrieved chunks as context
│                    │   - Conversation history (last N turns)
│                    │   - Customer's question
│                    │   Model generates answer in correct language
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│  6. Confidence     │   If score < threshold → fallback message
│     Check          │   or trigger human handoff
└────────┬───────────┘
         │
         ▼
   WhatsApp reply sent to customer
```

### Human Handoff Flow

```
                Customer chats with bot
                        │
            ┌───────────▼────────────┐
            │  Trigger conditions?   │
            │  - Keywords detected   │
            │    ("talk to human",   │
            │     "agent please")    │
            │  - Low RAG confidence  │
            └───────────┬────────────┘
                        │ YES
                        ▼
            ┌───────────────────────┐
            │  Handoff Created      │
            │  - Bot mode → paused  │
            │  - Staff WhatsApp     │
            │    alert sent         │
            │  - Logged in DB       │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │  Human Agent          │
            │  - Views inbox        │
            │  - Assigns to self    │
            │  - Chats via portal   │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │  Agent resolves       │
            │  handoff              │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │  Operator calls       │   (manual step — agent may
            │  resume-bot API       │    want to send closing msg first)
            └───────────┬───────────┘
                        │
                        ▼
                   Bot resumes
```

---

## 3. Technology Stack

### Backend (Python)

| Category | Technology | Why |
|----------|-----------|-----|
| **Framework** | FastAPI 0.115 | Async, auto-generates OpenAPI docs, fast |
| **Server** | Uvicorn 0.34 | ASGI server for async FastAPI |
| **ORM** | SQLAlchemy 2.0 (async) | Type-safe async DB queries |
| **DB Migrations** | Alembic 1.14 | Version-controlled schema changes |
| **Data validation** | Pydantic v2 | Request/response schemas, settings |
| **HTTP client** | httpx 0.28 | Async HTTP for outgoing API calls |
| **LLM** | Groq (default) / OpenAI | Fast inference; switchable per deployment |
| **Embeddings** | FastEmbed | Local embedding generation, no API cost |
| **Vector DB** | Weaviate | Hybrid search (semantic + keyword) |
| **File storage** | AWS S3 + boto3 | Scalable document storage |
| **WhatsApp** | Twilio / Meta Graph API / AiSensy | Three provider options |
| **Auth / crypto** | PyJWT, bcrypt, Fernet (cryptography) | JWT tokens + encrypted secrets at rest |
| **Audio** | faster-whisper, OpenAI Whisper | Voice note transcription |
| **Google Sheets** | Google Sheets API | Live inbox mirroring |
| **Testing** | pytest, pytest-asyncio, respx, moto | Full async test suite, mocked externals |

### Frontend (TypeScript)

| Category | Technology | Why |
|----------|-----------|-----|
| **Framework** | React 18 + TypeScript | Component-based UI with type safety |
| **Build tool** | Vite 5 | Fast dev server and production builds |
| **Routing** | React Router 7 | Client-side navigation |
| **Auth** | Supabase JS client | JWT-based login with roles |
| **Charts** | Recharts | Analytics dashboards |
| **Markdown** | react-markdown + remark-gfm | Render bot responses with formatting |
| **Deployment** | Nginx (EC2) / Vercel (optional) | Static file serving + API proxy |

### Infrastructure

| Service | Role |
|---------|------|
| **PostgreSQL (Supabase)** | Primary relational database |
| **Weaviate Cloud** | Vector search database |
| **AWS S3** | Document and file storage |
| **AWS EC2** | Application server |
| **Docker** | Container packaging |
| **GitHub Actions** | CI/CD pipeline to EC2 |

---

## 4. Repository Layout

```
Chatbot-engine/
│
├── app/                          # Backend (FastAPI)
│   ├── main.py                   # App factory — CORS, middleware, routers, static files
│   ├── api/
│   │   ├── deps/
│   │   │   └── portal_auth.py    # Auth: Bearer token / Supabase JWT / API keys
│   │   └── v1/
│   │       ├── router.py         # Registers all endpoint routers
│   │       └── endpoints/        # One file per feature area:
│   │           ├── health.py
│   │           ├── onboarding.py
│   │           ├── companies.py
│   │           ├── documents.py
│   │           ├── webhooks/     # twilio.py, meta.py, aisensy.py
│   │           ├── handoffs.py
│   │           ├── agents.py
│   │           ├── analytics.py
│   │           ├── products.py
│   │           ├── portal.py
│   │           ├── portal_inbox.py
│   │           └── whatsapp_campaigns.py
│   │
│   ├── core/
│   │   ├── config.py             # All env vars via pydantic-settings
│   │   ├── database.py           # Async SQLAlchemy engine + session factory
│   │   ├── exceptions.py         # Custom exception classes
│   │   ├── logging_config.py     # Structured logging setup
│   │   ├── passwords.py          # bcrypt hashing
│   │   ├── response.py           # Unified APIResponse[T] / ErrorResponse wrapper
│   │   └── secret_crypto.py      # Fernet encryption for stored WhatsApp secrets
│   │
│   ├── models/                   # SQLAlchemy ORM table definitions (20 tables)
│   ├── schemas/                  # Pydantic request/response schemas (14 modules)
│   ├── repositories/             # Database access layer (~18 repos, one per model)
│   ├── services/                 # Business logic (~22 services)
│   │
│   ├── integrations/
│   │   ├── twilio/               # Send/receive WhatsApp via Twilio
│   │   ├── meta_whatsapp/        # Send/receive via Meta Cloud API
│   │   ├── aisensy/              # Send/receive via AiSensy BSP
│   │   ├── weaviate/             # Vector DB client (index + search)
│   │   ├── llm/                  # LLMClientProtocol + Groq + OpenAI implementations
│   │   ├── embeddings/           # FastEmbed wrapper
│   │   ├── s3/                   # S3StorageClient (upload, download, delete)
│   │   └── google_sheets/        # Sync conversations to Sheets
│   │
│   ├── workers/
│   │   └── whatsapp_outbox_worker.py  # Background poller: campaigns + follow-ups
│   │
│   ├── utils/                    # Text chunking, WhatsApp formatting, correlation IDs
│   ├── static/                   # Served at /static/ — product images per company
│   └── tests/                    # pytest suite (unit + API + e2e)
│
├── web/                          # Frontend (React + Vite)
│   ├── src/
│   │   ├── pages/                # Dashboard, Admin, Inbox, Chat, Campaigns, etc.
│   │   ├── components/           # Reusable UI components
│   │   ├── lib/
│   │   │   ├── api.ts            # Backend API client
│   │   │   ├── supabase.ts       # Supabase auth + role helpers
│   │   │   └── supportApi.ts
│   │   └── context/              # React context providers
│   ├── deploy/                   # Nginx config + install scripts
│   └── api/mindorax/[...slug].ts # Vercel API proxy (optional)
│
├── migrations/
│   └── versions/                 # 19 Alembic migration files (schema history)
│
├── deploy/
│   ├── docker-compose.ec2.yml    # Production: api + migrate + whatsapp-worker
│   └── https/zero-downtime-rollout.sh
│
├── data/
│   └── skrange/                  # Sample tenant: product catalog, FAQs, images
│
├── scripts/                      # One-off ops scripts
│   ├── ec2_setup.py              # Deploy to EC2
│   ├── ingest_local_data.py      # Ingest a directory of docs into Weaviate
│   ├── ingest_file.py            # Ingest a single file into Weaviate
│   ├── onboard_company.py        # Full company onboarding (DB + Weaviate), no HTTP server
│   ├── setup_myresume_twilio.py  # Configure Twilio sandbox for myresume company
│   ├── activate_myresume.py      # Activate myresume after credentials are set
│   ├── import_product_catalog.py # Bulk import products from Excel/CSV
│   ├── copy_company_config.py    # Clone one company's config to another
│   └── set_product_images.py     # Assign images to products
│
├── .github/workflows/
│   └── deploy-ec2.yml            # CI/CD: build → SCP → deploy on `prod` branch push
│
├── docker-compose.yml            # Local dev: api + weaviate
├── Dockerfile                    # Python 3.10-slim + ffmpeg
├── requirements.txt
├── alembic.ini
└── .env.example
```

---

## 5. Data Model

### Entity Relationship Overview

```
companies  ──1:1──  company_configs     (AI prompts, secrets, provider settings)
    │       ──1:1──  onboarding_statuses (setup checklist)
    │       ──1:N──  company_channels   (WhatsApp numbers)
    │       ──1:N──  documents          (uploaded knowledge files)
    │       ──1:N──  products           (product catalog)
    │       ──1:N──  portal_users       (staff accounts)
    │       ──1:N──  conversations      (customer threads)
    │                    │
    │               ──1:N──  messages   (individual chat messages)
    │               ──1:N──  retrieval_logs (RAG audit trail)
    │               ──1:N──  handoffs   (escalation events)
    │
    └───────1:N──  whatsapp_campaigns   (bulk message sends)
    └───────1:N──  whatsapp_followup_rules (automated follow-ups)
    └───────1:N──  whatsapp_outbox_jobs (send queue)
    └───────1:N──  whatsapp_suppressions (do-not-contact list)
    └───────1:N──  google_sheet_sync_jobs (Sheets sync queue)
    └───────1:N──  daily_company_metrics (pre-aggregated analytics)
```

### Key Tables

| Table | Purpose | Notable Columns |
|-------|---------|-----------------|
| `companies` | One row per business tenant | `name`, `display_name`, `status` (active/inactive) |
| `company_configs` | All per-tenant runtime settings | `system_prompt`, `rag_config_json`, `handoff_config_json`, `whatsapp_provider`, encrypted Twilio/Meta/AiSensy credentials, `business_hours_json`, `weaviate_collection` |
| `conversations` | One per customer phone number per company | `current_mode` (bot/agent), `language`, `lead_warmth`, `lead_summary`, `inquiry_complete`, `is_blocked`, `opted_out` |
| `messages` | Every individual message | `role` (customer/bot/agent/system), `content`, `direction`, `provider_message_id` |
| `handoffs` | Escalation events | `status` (open/assigned/resolved), `assigned_agent_id`, `triggered_by` |
| `products` | Company product catalog | `name`, `description`, `price`, `image_url`, `weaviate_object_id` |
| `whatsapp_campaigns` | Bulk template sends | `status`, `template_name`, `scheduled_at`, recipient count |
| `documents` | Knowledge base files | `s3_key`, `status`, `chunk_count` |
| `retrieval_logs` | RAG audit | `query`, `score`, `chunks_returned`, `answer_generated` |

### Conversation Modes

```
bot mode  ←──── resume-bot API ────  agent mode
    │                                     ▲
    └──── handoff triggered ─────────────┘
```

A conversation starts in **bot mode**. When a human handoff is triggered, it switches to **agent mode** (bot stops responding). After the agent resolves the conversation and the operator explicitly resumes the bot, it returns to **bot mode**.

---

## 6. API Reference

All routes are under `/api/v1`. Interactive docs at `/docs` (dev only).

### Health

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness check |
| `GET` | `/api/v1/health` | Versioned liveness check |

### Onboarding

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/onboarding/company/full` | Create a company with config, Weaviate collection, and default settings in one call |

### Companies

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/companies/{id}/readiness` | Check if company is ready (Twilio configured, Weaviate collection exists, etc.) |
| `POST` | `/companies/{id}/activate` | Go live — passes readiness gates |
| `GET` | `/companies/{id}/config` | Read current AI/RAG/handoff config |
| `PUT` | `/companies/{id}/config` | Update prompts, RAG settings, fallback messages (not WhatsApp secrets) |
| `PATCH` | `/companies/{id}/status` | Enable or disable company |
| `POST` | `/companies/{id}/whatsapp/change-number` | Change the WhatsApp number |
| `POST` | `/companies/{id}/weaviate/ensure-collection` | Create Weaviate collection if missing |

### Documents

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/companies/{id}/documents/upload` | Upload PDF/Excel/Word → stores to S3 → indexes into Weaviate |
| `GET` | `/companies/{id}/documents` | List all uploaded documents |
| `GET` | `/companies/{id}/documents/{doc_id}` | Get document metadata and indexing status |
| `POST` | `/companies/{id}/documents/{doc_id}/index` | Re-trigger indexing (e.g. after Weaviate reset) |

### Webhooks (called by WhatsApp providers)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/webhooks/twilio/messages` | Receive inbound WhatsApp from Twilio |
| `GET` | `/webhooks/meta/whatsapp` | Meta webhook verification challenge |
| `POST` | `/webhooks/meta/whatsapp` | Receive inbound WhatsApp from Meta |
| `POST` | `/webhooks/aisensy/messages` | Receive inbound WhatsApp from AiSensy |

### Human Handoff

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/conversations/{id}/handoff` | Manually request handoff for a conversation |
| `GET` | `/companies/{id}/handoffs` | List all handoffs (filter by status) |
| `POST` | `/handoffs/{id}/assign` | Agent claims a handoff |
| `POST` | `/handoffs/{id}/resolve` | Mark handoff resolved |
| `POST` | `/conversations/{id}/resume-bot` | Return conversation to bot mode |
| `GET` | `/agents/{agent_id}/conversations` | View all conversations assigned to an agent |
| `POST` | `/conversations/{id}/messages/agent` | Agent sends a message |

### Analytics

All accept `?period_days=N` (default 30, max 365).

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/companies/{id}/analytics/overview` | Key metrics: messages, conversations, handoffs, fallbacks |
| `GET` | `/companies/{id}/analytics/languages` | English vs Hindi vs Hinglish breakdown |
| `GET` | `/companies/{id}/analytics/leads` | Lead warmth distribution |
| `GET` | `/companies/{id}/analytics/fallbacks` | Low-confidence response analysis |
| `GET` | `/companies/{id}/analytics/handoffs` | Handoff volume and resolution times |
| `GET` | `/companies/{id}/analytics/top-queries` | Most common customer questions |
| `GET` | `/companies/{id}/analytics/products` | Which products are asked about most |

### Products

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/companies/{id}/products` | Add a product to the catalog |
| `GET` | `/companies/{id}/products` | List all products |
| `GET` | `/companies/{id}/products/{product_id}` | Get a product |
| `PUT` | `/companies/{id}/products/{product_id}` | Update a product |
| `DELETE` | `/companies/{id}/products/{product_id}` | Delete a product |
| `POST` | `/companies/{id}/products/{product_id}/reindex` | Re-sync one product to Weaviate |
| `POST` | `/companies/{id}/products/reindex-all` | Re-sync entire catalog to Weaviate |

### Portal — Company Config

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/portal/companies/{id}/config` | Full config |
| `GET` | `/portal/companies/{id}/config/overview` | Dashboard overview + integration status |
| `GET` | `/portal/companies/{id}/config/prompt` | AI prompt settings only |
| `GET` | `/portal/companies/{id}/config/rag` | RAG settings only |
| `GET` | `/portal/companies/{id}/config/escalation` | Handoff settings only |

### Portal — Authentication

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/portal/auth/login` | Login with email + password → Bearer token |
| `POST` | `/portal/auth/bootstrap-first-admin` | One-time: create the very first admin account |

### Portal — Admin

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/portal/admin/companies` | List all tenant companies |
| `GET` | `/portal/admin/users` | List all portal users |
| `POST` | `/portal/admin/users` | Create a portal user (admin or tenant staff) |
| `POST` | `/portal/admin/users/{user_id}/reset-password` | Reset a user's password |
| `POST` | `/portal/admin/companies/{id}/twilio` | Save Twilio credentials for a company |
| `POST` | `/portal/admin/companies/{id}/aisensy` | Save AiSensy credentials |
| `POST` | `/portal/admin/companies/{id}/meta-whatsapp` | Save Meta WhatsApp credentials |
| `POST` | `/portal/admin/google-sheets/provision` | Provision Google Sheet for a company |

### Portal — Chat (Testing)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/portal/chat` | Test RAG Q&A directly — same pipeline as live WhatsApp |

### Portal — Inbox

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/portal/companies/{id}/inbox/conversations` | List conversations with filters |
| `GET` | `/portal/companies/{id}/inbox/conversations/{conv_id}/messages` | Get all messages in a conversation |
| `GET` | `/portal/companies/{id}/inbox/conversations/{conv_id}/poll` | Long-poll for new messages |
| `POST` | `/portal/companies/{id}/inbox/conversations/{conv_id}/messages` | Send a message from the portal |
| `PATCH` | `/portal/companies/{id}/inbox/conversations/{conv_id}` | Update lead info |
| `GET` | `/portal/companies/{id}/sheet-preview` | Preview Google Sheet data |

### Portal — Campaigns

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/portal/companies/{id}/campaigns` | List campaigns |
| `POST` | `/portal/companies/{id}/campaigns` | Create a campaign |
| `GET` | `/portal/companies/{id}/campaigns/{campaign_id}` | Campaign details + recipient status |
| `POST` | `/portal/companies/{id}/campaigns/{campaign_id}/action` | pause / resume / cancel |
| `POST` | `/portal/companies/{id}/campaigns/quick-send` | Send one-time message immediately |
| `POST` | `/portal/companies/{id}/campaigns/preview` | Preview before sending |
| `GET` | `/portal/companies/{id}/meta-templates` | List Meta message templates |
| `POST` | `/portal/companies/{id}/meta-templates` | Create a new template |
| `GET` | `/portal/companies/{id}/outbox-jobs` | View outbox send queue |

### Portal — Follow-up Rules

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/portal/companies/{id}/followup-rules` | List automation rules |
| `POST` | `/portal/companies/{id}/followup-rules` | Create a rule |
| `GET` | `/portal/companies/{id}/followup-rules/{rule_id}` | Get a rule |
| `PATCH` | `/portal/companies/{id}/followup-rules/{rule_id}` | Update a rule |
| `DELETE` | `/portal/companies/{id}/followup-rules/{rule_id}` | Delete a rule |

---

## 7. Authentication & Security

### Auth Methods

The API accepts three different auth mechanisms, depending on the route:

| Header | What it is | Accepted by |
|--------|-----------|-------------|
| `Authorization: Bearer <token>` | Portal login token OR Supabase JWT | Most portal routes |
| `X-Admin-Key: <key>` | Static admin API key from `PORTAL_ADMIN_API_KEY` env var | Admin-only routes |
| `X-Portal-Company-Key: <key>` | Per-company key from `PORTAL_COMPANY_KEYS_JSON` | Company-scoped routes |

### Supabase User Roles (Web App)

The React frontend logs in with Supabase Auth. Set the following in each user's `app_metadata` via the Supabase SQL editor or Admin API:

```sql
-- Admin user
UPDATE auth.users SET raw_app_meta_data = '{"role": "admin"}'
WHERE email = 'admin@yourcompany.com';

-- Tenant staff user
UPDATE auth.users SET raw_app_meta_data = '{"role": "user", "company_id": "<uuid>"}'
WHERE email = 'staff@tenant.com';
```

| Role | Access |
|------|--------|
| `admin` | All companies, all admin endpoints |
| `user` | Only their assigned `company_id` |

### Secrets at Rest

WhatsApp provider credentials (Twilio Account SID, Auth Token, Meta access tokens, AiSensy API keys) are **Fernet-encrypted** before storing in `company_configs`. The encryption key comes from `SECRET_KEY` in env. This means even database access doesn't expose live WhatsApp credentials.

### Bot Protection

Enable with `BOT_PROTECTION_ENABLED=true`. Configurable rate limits and burst limits prevent webhook flooding.

---

## 8. Key Flows Explained

### Onboarding a New Company

```
1. POST /api/v1/onboarding/company/full
   → Creates company record
   → Creates CompanyConfig with defaults
   → Creates Weaviate collection (namespace for this company's docs)
   → Returns company ID and initial config

2. POST /api/v1/portal/admin/companies/{id}/twilio  (or meta / aisensy)
   → Saves WhatsApp credentials (encrypted)
   → Sets whatsapp_provider

3. POST /api/v1/companies/{id}/documents/upload  (repeat for each doc)
   → File stored to S3
   → Background indexing job created
   → Document chunked and embedded into Weaviate

4. POST /api/v1/companies/{id}/activate
   → Checks: Weaviate collection exists? ✓
   → Checks: WhatsApp configured? ✓
   → Checks: At least one document indexed? ✓
   → Sets company status = active
   → WhatsApp webhook is now live
```

### Inbound Message Processing

```
WhatsApp → Webhook → app/api/v1/endpoints/webhooks/
    │
    ├─ Validate provider signature (Twilio HMAC / Meta signature)
    ├─ Find company by WhatsApp number
    ├─ Create or find Conversation record
    ├─ Save inbound Message to DB
    │
    ├─ Is conversation in agent mode? → drop (agent handles it via portal)
    ├─ Is customer blocked / opted out? → skip or reply with opt-out message
    │
    ├─ RAGService.generate_response()
    │   ├─ Detect language
    │   ├─ Search Weaviate (hybrid)
    │   ├─ Search product catalog
    │   ├─ Build LLM prompt with system prompt + chunks + history
    │   ├─ Call Groq / OpenAI
    │   └─ Return answer + confidence score
    │
    ├─ Confidence score < threshold? → HandoffService.trigger()
    │
    ├─ Save bot reply Message to DB
    ├─ Send reply via WhatsApp provider
    ├─ Update conversation metrics
    └─ Log to retrieval_logs (RAG audit)
```

### Campaign Send

```
1. Admin creates campaign with template + recipient list
2. POST /portal/companies/{id}/campaigns
   → Validates Meta template exists
   → Creates WhatsAppCampaign record
   → Creates WhatsAppCampaignRecipient rows (one per phone number)
   → Creates WhatsAppOutboxJob rows (one per recipient)

3. whatsapp_outbox_worker polls outbox_jobs every N seconds
   → For each pending job: call provider API
   → On success: mark job sent, update recipient status
   → On failure: retry with backoff, mark failed after max retries

4. GET /portal/companies/{id}/campaigns/{id}
   → Returns per-recipient delivery status in real time
```

---

## 9. Environment Variables

Copy `.env.example` to `.env` and fill in the values.

### Core App

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `APP_ENV` | `development` | — | `development` or `production` |
| `DATABASE_URL` | — | Yes | PostgreSQL async URL: `postgresql+asyncpg://user:pass@host/db` |
| `SECRET_KEY` | — | Yes (prod) | Random 32+ char string — used for portal tokens and Fernet encryption |
| `DEBUG` | `false` | — | Show detailed error tracebacks in API responses |
| `LOG_LEVEL` | `INFO` | — | Python logging level |
| `PUBLIC_BASE_URL` | — | Yes | Full URL of this server (e.g. `https://api.yourdomain.com`) — used to build product image URLs |
| `CORS_ORIGINS` | — | Yes (prod) | Comma-separated list of allowed frontend origins |

### Weaviate (Vector DB)

| Variable | Description |
|----------|-------------|
| `WEAVIATE_URL` | Weaviate instance URL (e.g. `https://your-cluster.weaviate.network`) |
| `WEAVIATE_API_KEY` | API key for Weaviate Cloud |

### AWS S3 (Document Storage)

| Variable | Description |
|----------|-------------|
| `S3_BUCKET_NAME` | Bucket name (e.g. `mindorax-documents-prod`) |
| `AWS_REGION` | Region (e.g. `ap-south-1`) |
| `AWS_ACCESS_KEY_ID` | Leave unset on EC2 with IAM role attached |
| `AWS_SECRET_ACCESS_KEY` | Leave unset on EC2 with IAM role attached |
| `AWS_ENDPOINT_URL` | Override for LocalStack local dev |

**S3 key naming convention:**
```
companies/{company_id}/documents/{document_id}/{sanitized_filename}
```
Each tenant's files are namespace-isolated.

**Minimum S3 IAM policy:**
```json
{
  "Effect": "Allow",
  "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject", "s3:HeadObject"],
  "Resource": "arn:aws:s3:::mindorax-documents-prod/*"
}
```

### LLM

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `groq` | `groq` or `openai` |
| `GROQ_API_KEY` | — | From [console.groq.com](https://console.groq.com) |
| `OPENAI_API_KEY` | — | Used only when `LLM_PROVIDER=openai` |
| `LLM_MODEL` | — | e.g. `qwen/qwen3.8-27b` (Groq) or `gpt-4o-mini` (OpenAI). Run `groq.models.list()` to see models available on your key. |
| `LLM_TEMPERATURE` | `1` | Response creativity (0–2) |
| `LLM_MAX_COMPLETION_TOKENS` | `8192` | Max tokens per response |
| `LLM_STREAM` | `false` | Use streaming and aggregate chunks |

### RAG & Indexing

| Variable | Default | Description |
|----------|---------|-------------|
| `RAG_SCORE_THRESHOLD` | `0.4` | Below this → fallback / handoff |
| `RAG_TOP_K` | `5` | Max document chunks to retrieve |
| `RAG_HYBRID_ALPHA` | `0.5` | Balance between semantic (1.0) and keyword (0.0) search |
| `RAG_CONVERSATION_TURNS` | `5` | How many past messages to include in LLM context |
| `CHUNK_SIZE` | `1000` | Characters per text chunk when indexing |
| `CHUNK_OVERLAP` | `100` | Characters of overlap between consecutive chunks |
| `INDEXING_MAX_RETRIES` | `3` | Retry failed index jobs this many times |
| `RAG_EMBEDDINGS_ENABLED` | `true` | Enable embedding-based semantic search |

### Portal Auth

| Variable | Description |
|----------|-------------|
| `PORTAL_ADMIN_API_KEY` | Static key for `X-Admin-Key` header |
| `PORTAL_COMPANY_KEYS_JSON` | JSON map of company keys for `X-Portal-Company-Key` |
| `SUPABASE_JWT_SECRET` | Your Supabase project JWT secret (from Project Settings → API) |
| `PORTAL_BOOTSTRAP_SECRET` | One-time secret for creating the first admin user |
| `PORTAL_TOKEN_MAX_AGE_SECONDS` | Portal login token TTL (default: 86400 = 24 hours) |

### WhatsApp Providers (Global)

| Variable | Description |
|----------|-------------|
| `TWILIO_VALIDATE_SIGNATURE` | `true` in production to verify webhook HMAC |
| `META_WEBHOOK_VERIFY_TOKEN` | Token for Meta's webhook verification challenge |
| `META_GRAPH_API_VERSION` | e.g. `v19.0` |
| `AISENSY_API_BASE_URL` | AiSensy API base URL |
| `WHATSAPP_OUTBOX_POLL_INTERVAL` | Outbox worker sleep interval (seconds) |
| `WHATSAPP_FOLLOWUP_SESSION_HOURS` | Hours of inactivity before follow-up fires |

> Per-company credentials (Account SID, Auth Token, phone number) are stored encrypted in the database via the admin API — not in env vars.

### Google Sheets (Optional)

| Variable | Description |
|----------|-------------|
| `GOOGLE_SHEETS_SYNC_ENABLED` | `true` to enable |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Full JSON of service account credentials (inline) |
| `GOOGLE_SERVICE_ACCOUNT_JSON_FILE` | Path to credentials file (alternative to above) |

### Frontend (`web/.env`)

| Variable | Description |
|----------|-------------|
| `VITE_SUPABASE_URL` | Your Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | Supabase anon/public key |
| `VITE_API_BASE_URL` | Backend URL (e.g. `https://api.yourdomain.com`) |
| `VITE_ADMIN_API_KEY` | Optional: pre-fill admin key for dev testing |

---

## 10. Local Development Setup

### Prerequisites

- Python 3.10+
- Node.js 18+
- Docker (for Weaviate local instance)
- A Supabase project (free tier works) — or a local PostgreSQL instance
- Groq or OpenAI API key
- AWS account + S3 bucket (or LocalStack)

### Backend Setup

```bash
# 1. Clone the repo
git clone https://github.com/your-org/mindorax-backend
cd mindorax-backend

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate       # Windows
source .venv/bin/activate    # Linux/macOS

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your values (see Section 9)

# 5. Start local Weaviate (Docker)
docker-compose up -d weaviate

# 6. Run database migrations
alembic upgrade head

# 7. Start the backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs available at: http://localhost:8000/docs

### Frontend Setup

```bash
cd web
cp .env.example .env
# Edit .env: VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY, VITE_API_BASE_URL=http://localhost:8000

npm install
npm run dev
```

Portal available at: http://localhost:5173

### Using Docker Compose (All-in-One)

```bash
# Starts API + Weaviate together
docker-compose up
```

### Ingest Sample Data (SK Range)

```bash
# Index the sample product catalog into your Weaviate instance
python scripts/ingest_local_data.py --company-id <your-company-uuid>

# Import products from Excel into the database + Weaviate
python scripts/import_product_catalog.py --company-id <uuid> --file data/skrange/catalog.xlsx
```

---

## 11. Production Deployment (Render)

### Deploy to Render (Recommended — Free Tier)

1. Push your code to GitHub
2. Go to [render.com](https://render.com) → **New Web Service** → connect your repo
3. Set **Build Command**: `pip install -r requirements.txt`
4. Set **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Add all environment variables from your `.env` in the **Environment** tab
6. Click **Deploy**

Your service URL will be `https://<service-name>.onrender.com`.

Update `PUBLIC_BASE_URL` in Render's environment variables to match.

> **Important:** Set `LLM_MODEL` to a model available on your Groq key.
> Check available models: `python -c "from groq import Groq; [print(m.id) for m in Groq().models.list().data]"`

### First-time DB migration on Render

```bash
# In Render → Shell tab (or via one-off job)
alembic upgrade head
```

---

## 11b. Production Deployment (EC2)

### Prerequisites

- AWS EC2 instance (Ubuntu 22.04, at least t3.small)
- Docker installed on EC2 (or run the bootstrap script)
- Weaviate Cloud account
- Supabase project
- Domain name + SSL (handled by nginx)

### First-Time EC2 Setup

```bash
# Bootstrap Docker on a fresh EC2 instance
bash scripts/ec2-bootstrap.sh

# Or use the Python deploy helper
python scripts/ec2_setup.py --deploy-only
```

### Deploy via GitHub Actions (Recommended)

Push to the `prod` branch and GitHub Actions will automatically:
1. Build a `.env` file from GitHub secrets
2. SCP files to EC2
3. Pull latest Docker image
4. Run `alembic upgrade head`
5. Restart all containers

Configure these secrets in GitHub → Settings → Secrets:
- `EC2_HOST`, `EC2_USER`, `EC2_SSH_KEY`
- All your env var values (see `.env.example`)

### Manual Deploy

```bash
# Sync code to EC2 (PowerShell)
.\scripts\sync-to-ec2.ps1

# On EC2:
cd /opt/mindorax
docker compose -f deploy/docker-compose.ec2.yml up -d
```

### Production Docker Services

```yaml
# deploy/docker-compose.ec2.yml
services:
  migrate:       # Runs once: alembic upgrade head
  api:           # FastAPI on 127.0.0.1:8000 (behind nginx)
  whatsapp-worker: # Background: polls outbox jobs for campaigns/follow-ups
```

### Nginx + HTTPS

```bash
# Install nginx config for frontend
bash web/deploy/install-frontend-nginx.sh

# Zero-downtime API rollout
bash deploy/https/zero-downtime-rollout.sh
```

---

## 12. Running Tests

All external services (Twilio, Weaviate, S3, Groq) are mocked. No real credentials needed.

```bash
# Run all tests
python -m pytest app/tests/ -v

# With coverage report
python -m pytest app/tests/ --cov=app --cov-report=term-missing

# Unit tests only
python -m pytest app/tests/unit/ -v

# API tests only
python -m pytest app/tests/ -m api -v

# End-to-end tests
python -m pytest app/tests/test_e2e.py -v
```

---

## 13. Ops & Admin Scripts

### Ingest a Single File

Ingest any PDF, TXT, MD, CSV, or JSON file directly into a company's Weaviate collection without touching a directory.

```bash
python scripts/ingest_file.py \
  --file "path/to/resume.pdf" \
  --company-id <uuid>
```

Options:
- `--chunk-size` (default from `CHUNK_SIZE` env)
- `--chunk-overlap` (default from `CHUNK_OVERLAP` env)

### Onboard a New Company (CLI)

Full onboarding without the HTTP server:

```bash
# Step 1 – Create company, config, channel, and Weaviate collection
python scripts/onboard_company.py \
  --company-name myresume \
  --display-name "MyResume" \
  --phone +14155238886

# Step 2 – Configure Twilio (Sandbox or production number)
$env:TWILIO_ACCOUNT_SID="ACxxxxxxxxxx"
$env:TWILIO_AUTH_TOKEN="your_token"
$env:TWILIO_WHATSAPP_NUMBER="whatsapp:+14155238886"   # sandbox
python scripts/setup_myresume_twilio.py --enable-twilio-provider

# Step 3 – Activate
python scripts/activate_myresume.py
```

> **PgBouncer note:** All CLI scripts automatically switch the `DATABASE_URL` from
> the Supabase transaction pooler (port 6543) to the session pooler (port 5432) so
> asyncpg prepared statements work correctly. The FastAPI server continues to use the
> transaction pooler with `statement_cache_size=0`.

### Clone a Company Config

Copy prompts, RAG settings, and credentials from one tenant to another — useful when spinning up a new company with similar settings.

```bash
# Preview only (no changes made)
python scripts/copy_company_config.py --from sk-group --to rcs --dry-run

# Copy everything, keep RCS phone/Meta IDs
python scripts/copy_company_config.py --from sk-group --to rcs

# Copy + clear source credentials (ready for new integrations)
python scripts/copy_company_config.py --from sk-group --to rcs \
  --routing from-source --ready-for-new-integrations
```

`--from` / `--to` accept company slug, display name, or UUID.
`weaviate_collection` is never copied — each tenant keeps its own vector namespace.

### Set Product Images

```bash
python scripts/set_product_images.py --company-id <uuid> --images-dir data/skrange/images/
```

### Sync Frontend to EC2

```powershell
.\scripts\sync-frontend-ec2.ps1
```

---

## Architectural Decisions Log

| Decision | Choice | Reason |
|----------|--------|--------|
| No Redis | DB-backed job queues | Reduces infrastructure complexity; outbox jobs are low-frequency |
| Fernet for secrets | Encrypt WhatsApp tokens in DB | Protects credentials even if DB is compromised |
| Correlation ID middleware | UUID on every request | End-to-end request tracing in logs |
| Per-tenant Weaviate collections | One collection per company | Strict data isolation; easy tenant deletion |
| Provider abstraction | `LLMClientProtocol` | Swap Groq/OpenAI without changing business logic |
| Unified API response | `APIResponse[T]` wrapper | Consistent shape for all frontend consumers |
| No async task queue (Celery) | Polling worker + outbox table | Simpler ops; sufficient for current scale |
