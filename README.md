# BOID-RAP

BOID-RAP is an open-source research workspace for **companies, stocks, and commodities**.

It combines:

- retrieval from external information sources
- structured research sessions
- asynchronous research jobs
- citation-aware report generation
- follow-up Q&A on top of generated reports
- a frontend workspace with a restrained, finance-oriented visual style

The goal is simple:

> turn messy research inputs into a repeatable workflow that feels closer to a professional research terminal than a generic AI chat page.

---

## Why This Project Exists

Most AI research demos stop at “ask a question, get an answer”.

BOID-RAP is trying to push further:

- **session-based research**, not one-off prompts
- **retrieval + reasoning + structured output**, not pure text generation
- **object-aware workflows** for company / stock / commodity research
- **reports with citations and evidence alignment**
- **job status, history, and auditability**
- **an actual workspace UI**, not just an API endpoint

If you care about building AI products for investment research, industry analysis, due diligence, or decision support systems, this repo is designed to be a practical starting point.

---

## What You Get Today

### Backend

- User registration / login / RBAC
- Token expiry / refresh / logout
- User enable / disable / soft delete
- SQLite persistence
- Database migrations
- Model configuration management
- Research sessions with multi-turn messages
- Async research jobs with status tracking / retry / cancel
- Retrieval provider registry
- Tavily provider + configurable HTTP retrieval provider
- Retrieval caching, aggregation, keyword filtering, highlighting
- Report generation with citations
- Paragraph-level follow-up Q&A
- Keyword-linked search across reports and retrieval results
- Search insights
- Audit logs

### Research Objects

- Company research sessions
- Stock research sessions
- Commodity research sessions
- LLM-generated structured profiles for all three object types

### Frontend

- Login page
- Workspace page
- Session timeline page
- Job status page
- Report list page
- Report detail page
- Evidence / annotation sidebar
- Search insights page
- Admin pages for users / models / audit logs

The frontend uses a **finance-first design language**:

- deep green as primary
- amber as accent
- off-white background
- left-aligned layouts
- restrained motion
- bordered cards without shadows

---

## Architecture Snapshot

At a high level, BOID-RAP is split into four layers:

1. **Research session layer**
   Creates and manages sessions for different object types.

2. **Retrieval layer**
   Pulls and normalizes external information from configured providers.

3. **Analysis / report layer**
   Builds structured profiles, reports, citations, and follow-up answers.

4. **Delivery layer**
   Exposes HTTP APIs and a frontend workspace for actual usage.

Current implementation keeps the backend intentionally lightweight:

- Python standard library HTTP server
- SQLite
- no heavy web framework dependency yet

That makes the project easy to inspect, fork, and evolve.

---

## Tech Stack

### Backend

- Python 3
- SQLite
- standard-library HTTP server

### Frontend

- React
- TypeScript
- Vite
- React Router

### AI / Retrieval

- OpenAI-compatible Responses API path
- OpenRouter-compatible base URL support
- Tavily retrieval support
- pluggable HTTP retrieval provider

---

## Quick Start

### 1. Clone the repo

```bash
git clone <your-repo-url>
cd BOID-RAP
```

### 2. Start the backend

```bash
python3 app.py
```

Backend default address:

```text
http://127.0.0.1:8000
```

On first start, the project will automatically:

- create `data/boid_rap.db`
- apply migrations
- initialize a usable local database

### 3. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend default address:

```text
http://127.0.0.1:5173
```

If needed, point the frontend to a different backend:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

---

## Default Accounts

You can log in with:

- Admin: `admin / admin123`
- User: `analyst / analyst123`

Admin account is useful for:

- model management
- user management
- audit log inspection

User account is enough to test:

- research sessions
- jobs
- reports
- follow-up Q&A

---

## Environment Variables

The project supports `.env` loading automatically.

Common variables:

```bash
BOID_RAP_OPENAI_LLM_ENABLED=true
BOID_RAP_OPENAI_API_KEY=your_key
BOID_RAP_OPENAI_BASE_URL=https://api.openai.com/v1
BOID_RAP_OPENAI_MODEL=gpt-5-mini

BOID_RAP_TAVILY_ENABLED=true
BOID_RAP_TAVILY_API_KEY=your_tavily_key

BOID_RAP_HTTP_RETRIEVAL_ENABLED=false
BOID_RAP_RETRIEVAL_CACHE_TTL_SECONDS=3600
BOID_RAP_CORS_ALLOW_ORIGIN=*
```

### OpenRouter support

If you want to run the LLM path through OpenRouter, you only need to switch the base URL:

```bash
BOID_RAP_OPENAI_LLM_ENABLED=true
BOID_RAP_OPENAI_API_KEY=your_openrouter_key
BOID_RAP_OPENAI_BASE_URL=https://openrouter.ai/api/v1
BOID_RAP_OPENAI_MODEL=openai/gpt-5-mini
```

---

## Main API Surface

### Auth

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `POST /api/auth/refresh`
- `POST /api/auth/change-password`

### Meta

- `GET /health`
- `GET /api/meta/object-types`
- `GET /api/meta/retrieval-providers`
- `GET /api/meta/search-insights`

### Research

- `GET /api/research/sessions`
- `POST /api/research/sessions`
- `GET /api/research/sessions/{session_id}`
- `POST /api/research/sessions/{session_id}/messages`
- `POST /api/research/sessions/{session_id}/run`
- `GET /api/research/sessions/{session_id}/retrievals`

### Jobs

- `GET /api/research/jobs`
- `GET /api/research/jobs/{job_id}`
- `GET /api/research/jobs/{job_id}/retrieval`
- `POST /api/research/jobs/{job_id}/cancel`
- `POST /api/research/jobs/{job_id}/retry`

### Reports

- `GET /api/reports`
- `GET /api/reports/{report_id}`
- `GET /api/reports/{report_id}/profile`
- `GET /api/reports/{report_id}/markdown`
- `POST /api/reports/{report_id}/follow-up`

### Admin

- `GET /api/admin/users`
- `GET /api/admin/models`
- `POST /api/admin/models`
- `GET /api/admin/audit-logs`

---

## Current Product Experience

Right now, BOID-RAP already feels like a real prototype:

- create a research session
- choose object type and model
- run an async research job
- inspect retrieval output
- read a structured report
- navigate citations and evidence
- ask follow-up questions

This is already useful if you want to:

- prototype an AI research terminal
- test retrieval + report workflows
- build a finance / industry analysis product
- experiment with structured research UX

---

## Current Limitations

This repo is promising, but it is still an evolving system.

Not fully production-ready yet:

- company / stock / commodity dedicated data sources are still incomplete
- report export is currently Markdown-first
- stronger fact verification is still pending
- more advanced model comparison workflows are still pending
- frontend polish is improving but not fully finished
- deployment / CI / monitoring are not yet complete

So the right expectation is:

> this is a serious, working prototype and foundation for a larger product, not a finished SaaS.

---

## Project Structure

```text
boid_rap/         backend services, repositories, retrieval, llm, domain logic
frontend/         React frontend workspace
data/             local SQLite database
scripts/          migration entrypoints
app.py            backend entry
```

If you want to inspect the frontend specifically, start here:

- `frontend/README.md`

---

## Who This Is For

BOID-RAP is especially relevant for:

- AI product builders
- finance / quant / research tooling teams
- industry analysis platforms
- due diligence and knowledge workflow builders
- developers interested in retrieval + report generation systems

If that sounds like you, this repo is meant to be forked, extended, and improved.

---

## Contributing

Issues, ideas, and pull requests are welcome.

Good contribution directions:

- stronger structured data providers
- better retrieval quality
- better evidence alignment
- richer report export
- better admin tools
- frontend polish
- deployment support

---

## Star This Project

If you think this repo is a useful foundation for AI-powered research products:

- star it
- watch it
- fork it
- share it with others building in this space

That kind of support makes it much easier to keep pushing the project forward.
