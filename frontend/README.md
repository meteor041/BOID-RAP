# Frontend Skeleton

这是 BOID-RAP 的前端骨架，当前已包含：

- Vite + React + TypeScript 基础结构
- 主路由
- 登录页
- 工作台页
- 会话时间轴页
- 任务状态页
- 报告列表页
- 报告详情页
- 证据附注式报告侧栏
- 搜索洞察页
- 管理端用户/模型/审计日志页
- 金融终端风格的全局 design token
- 基础 `Button` / `Card` / `Table` 样式

## 启动

```bash
cd frontend
npm install
npm run dev
```

默认通过 `VITE_API_BASE_URL` 访问后端，未配置时使用：

```text
http://127.0.0.1:8000
```
