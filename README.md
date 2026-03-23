# BOID-RAP

商业对象智能深度调研分析平台的后端原型，当前已经具备可运行的数据库、权限、任务流和检索适配层。

当前版本聚焦于把 `docs/TASK.md` 中最核心的能力抽象成可运行的服务骨架：

- SQLite 数据落库
- 用户注册、登录与 RBAC
- 管理端模型配置
- 用户研究会话
- 调研任务编排状态
- 检索 provider 注册与 HTTP 适配
- LLM provider 适配与报告生成
- 检索结果缓存、聚合与历史记录
- 报告生成与历史记录

## 技术选择

为了在空仓库里先落一版零依赖、可直接运行的原型，当前实现使用 Python 标准库和 SQLite 构建 HTTP API。后续可以平滑迁移到 FastAPI、Django 或拆分成微服务。

## 启动方式

```bash
python3 app.py
```

默认监听 `http://127.0.0.1:8000`。

首次启动会自动创建 `data/boid_rap.db`。

如需配置真实检索 provider，可参考 [.env.example](/home/meteor/Documents/BOID-RAP/.env.example) 和 [docs/HTTP_RETRIEVAL_PROVIDER.md](/home/meteor/Documents/BOID-RAP/docs/HTTP_RETRIEVAL_PROVIDER.md)。当前已内置 `tavily_search` 和通用 `http_deepsearch` 两种 HTTP provider。

如需配置真实大模型调用，可在 `.env` 中设置 `BOID_RAP_OPENAI_LLM_ENABLED=true` 并提供 `BOID_RAP_OPENAI_API_KEY`。如果要切到 OpenRouter，只需要把 `BOID_RAP_OPENAI_BASE_URL` 改成 `https://openrouter.ai/api/v1`，并把模型名改成 OpenRouter 的模型标识即可。

## 默认账号

- 管理员：`admin / admin123`
- 普通用户：`analyst / analyst123`

## 主要接口

- `GET /health`
- `GET /api/meta/object-types`
- `GET /api/meta/search-insights`
- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/admin/users`
- `GET /api/admin/models`
- `POST /api/admin/models`
- `GET /api/meta/retrieval-providers`
- `GET /api/research/sessions`
- `POST /api/research/sessions`
- `GET /api/research/sessions/{session_id}`
- `GET /api/research/sessions/{session_id}/retrievals`
- `POST /api/research/sessions/{session_id}/messages`
- `POST /api/research/sessions/{session_id}/run`
- `GET /api/research/jobs`
- `GET /api/research/jobs/{job_id}`
- `GET /api/research/jobs/{job_id}/retrieval`
- `GET /api/reports`
- `GET /api/reports/{report_id}`
- `GET /api/reports/{report_id}/profile`
- `GET /api/reports/{report_id}/markdown`
- `POST /api/reports/{report_id}/follow-up`

其中检索结果接口、报告列表、报告详情与 Markdown 导出接口已支持 `keyword` 查询参数，可用于关键词过滤、命中高亮和返回 `search_meta` 推荐词。
报告追问接口也支持在请求体中传 `keyword`，用于优先锁定命中段落后再继续追问。

## 认证方式

登录后通过 `Authorization: Bearer <token>` 或 `X-Auth-Token: <token>` 访问受保护接口。

## 当前边界

这一版已经具备持久化、基础权限、异步任务、检索缓存、检索适配和基础报告追问能力，但仍是“可演进原型”，不是完整生产实现：

- 真实大模型编排仍未接入
- 默认报告内容仍以结构化模板输出为主
- 报告追问已支持段落级定位、句子级证据和引用回链，但还没有做到更强的语义级证据对齐
- 权限模型仍是简化 RBAC
- 还没有前端页面、导出能力、监控告警和生产级部署

更完整的架构说明见 [docs/ARCHITECTURE.md](/home/meteor/Documents/BOID-RAP/docs/ARCHITECTURE.md)。
前端联调可直接参考 [docs/API.md](/home/meteor/Documents/BOID-RAP/docs/API.md)。
前端页面拆分和对接顺序可参考 [docs/FRONTEND_HANDOFF.md](/home/meteor/Documents/BOID-RAP/docs/FRONTEND_HANDOFF.md)。
前端技术实现建议可参考 [docs/FRONTEND_TECH_PLAN.md](/home/meteor/Documents/BOID-RAP/docs/FRONTEND_TECH_PLAN.md)。
前端视觉规范可参考 [docs/FRONTEND_STYLE_GUIDE.md](/home/meteor/Documents/BOID-RAP/docs/FRONTEND_STYLE_GUIDE.md)。
前端代码骨架位于 [frontend/README.md](/home/meteor/Documents/BOID-RAP/frontend/README.md)。
前端视觉风格可参考 [docs/FRONTEND_STYLE_GUIDE.md](/home/meteor/Documents/BOID-RAP/docs/FRONTEND_STYLE_GUIDE.md)。
