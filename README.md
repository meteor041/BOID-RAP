# Business Object Intelligent Deep Research Analysis Platform (BOID-RAP)

<p align="left">
  <a href="#"><img alt="Python" src="https://img.shields.io/badge/Python-3.x-0A5C5C?style=flat-square"></a>
  <a href="#"><img alt="React" src="https://img.shields.io/badge/Frontend-React%20%2B%20TypeScript-D97706?style=flat-square"></a>
  <a href="#"><img alt="SQLite" src="https://img.shields.io/badge/Database-SQLite-0A5C5C?style=flat-square"></a>
  <a href="#"><img alt="Status" src="https://img.shields.io/badge/Status-Working%20Prototype-D97706?style=flat-square"></a>
  <a href="#"><img alt="Focus" src="https://img.shields.io/badge/Focus-Research%20Workspace-0A5C5C?style=flat-square"></a>
</p>

**中文简介**

BOID-RAP 是一个面向 **公司 / 股票 / 商品** 的智能研究工作台。  
它不是把“大模型回答”简单包成聊天框，而是把 **检索、研究会话、异步任务、结构化报告、证据引用、追问交互、管理后台** 串成一条可持续演进的研究链路。

这个项目适合：

- 想做金融研究 / 行业研究 AI 产品的人
- 想把“搜索 + LLM”做成可落地工作流的人
- 需要一个可以直接改造的研究终端原型的人
- 希望搭建带任务流、历史记录、引用回链、管理端的 AI 应用的人

**English**

BOID-RAP is an open-source research workspace for **companies, stocks, and commodities**.

It is designed for builders who want more than a chat wrapper:

- retrieval-aware research sessions
- async research jobs
- structured reports with citations
- follow-up Q&A on top of reports
- admin and audit surfaces
- a finance-oriented frontend workspace

In short:

> BOID-RAP helps turn messy research inputs into a repeatable, inspectable, product-ready workflow.

---

## Highlights | 项目亮点

### 中文

- **研究会话而不是一次性问答**
  每个对象都有独立会话、消息流、任务状态和报告历史。

- **异步任务流**
  支持创建任务、轮询状态、取消、重试，不会把复杂研究流程塞进一次同步请求。

- **检索增强而不是纯生成**
  内置 Tavily 与通用 HTTP 检索适配层，支持缓存、聚合、关键词过滤和高亮。

- **结构化报告**
  报告不只是大段文字，还包含引用、段落级证据、句子级证据和对象画像。

- **对象级研究框架**
  面向公司、股票、商品三类对象，具备不同的研究路径和结构化画像输出。

- **前后端一体的可演进原型**
  后端 API、管理端、研究工作台、任务页、报告页都已经具备基础骨架。

### English

- **Session-based research, not one-shot prompting**
- **Async job lifecycle with status, retry, and cancel**
- **Retrieval-aware workflow instead of pure generation**
- **Structured reports with citations and evidence alignment**
- **Object-aware research flows for company / stock / commodity**
- **A real product prototype, not just a backend demo**

---

## What Makes It Different | 和常见 AI Demo 的区别

| Typical AI demo | BOID-RAP |
|---|---|
| One prompt in, one answer out | Session-based research workflow |
| Mostly synchronous | Async jobs with lifecycle |
| Text-heavy output | Structured report + citations + evidence |
| Weak auditability | History, logs, admin surfaces |
| Generic UI | Finance-oriented workspace |
| Prompt playground feel | Research terminal feel |

---

## Current Feature Set | 当前已具备能力

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
- Search insights
- Audit logs

### Research Objects

- Company sessions
- Stock sessions
- Commodity sessions
- LLM-generated structured profiles for all three

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

---

## Product Shape | 产品形态

BOID-RAP currently behaves like a real research prototype:

1. Create a research session
2. Select object type and model
3. Launch an async job
4. Inspect retrieval results
5. Read a structured report
6. Follow citations and evidence
7. Ask follow-up questions
8. Review activity from admin and audit views

This makes it useful as:

- an AI research terminal prototype
- a retrieval + reporting reference implementation
- a base project for finance / industry analysis products
- a strong starting point for internal research tooling

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

- OpenAI-compatible Responses path
- OpenRouter-compatible base URL support
- Tavily retrieval support
- pluggable HTTP retrieval provider

---

## Quick Start | 快速开始

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

If needed:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

---

## Default Accounts | 默认账号

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

## Environment Variables | 环境变量

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

If you want to run the LLM path through OpenRouter:

```bash
BOID_RAP_OPENAI_LLM_ENABLED=true
BOID_RAP_OPENAI_API_KEY=your_openrouter_key
BOID_RAP_OPENAI_BASE_URL=https://openrouter.ai/api/v1
BOID_RAP_OPENAI_MODEL=openai/gpt-5-mini
```

---

## Main API Surface | 主要接口

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

## Roadmap | 路线图

### Near Term

- richer dedicated data sources for company / stock / commodity
- stronger evidence alignment
- better report export
- better frontend polish
- improved admin workflows

### Mid Term

- model comparison workflows
- deeper fact verification
- production-oriented deployment support
- stronger observability and monitoring

### Long Term

- a more complete AI-native research operating system
- extensible providers for finance and industry data
- stronger collaboration features for teams

---

## Current Limitations | 当前边界

This repository is already useful, but it is not pretending to be finished.

Not fully production-ready yet:

- dedicated company / stock / commodity data sources are still incomplete
- export is currently Markdown-first
- stronger fact verification is still pending
- deployment / CI / monitoring are still evolving
- some frontend areas are still prototype-grade

The right expectation is:

> BOID-RAP is a serious working prototype and a strong foundation, not a finished SaaS product.

---

## Project Structure | 项目结构

```text
boid_rap/         backend services, repositories, retrieval, llm, domain logic
frontend/         React frontend workspace
data/             local SQLite database
scripts/          migration entrypoints
app.py            backend entry
```

---

## Contributing | 欢迎贡献

Pull requests, issues, and ideas are welcome.

Good contribution directions:

- stronger structured data providers
- better retrieval quality
- richer report export
- better evidence alignment
- admin workflow improvements
- frontend polish
- deployment support

If you want to contribute, a good way to start is:

1. open an issue describing the problem or idea
2. keep the change focused
3. prefer small, reviewable pull requests
4. include verification steps when possible

---

## Who Should Star This Repo | 谁会愿意 Star 这个项目

If you are building:

- AI research tools
- finance / industry analysis software
- knowledge work systems with retrieval + reporting
- internal analyst workflows
- structured AI products beyond plain chat

then this repo is probably worth a star, a fork, or a watch.

If BOID-RAP gives you useful ideas, helps your architecture thinking, or saves you prototype time:

**please consider starring the project.**
