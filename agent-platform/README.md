# AgentOS — 多 Agent 协同平台

> 云枢调度 · 三引擎协同 · 可视化监控 · 跨端上下文

## 架构概览

```
用户层    Web Chat (Vite+React:5174)    飞书 Bot      Cron/Task
              │                           │              │
消息层    ┌───▼───────────────────────────▼──────────────▼───┐
         │              Django REST API (:8001)              │
         │   SQLite(11表) + Redis(Pub/Sub + List Queue)      │
         └───────────────────────┬───────────────────────────┘
                                 │
Worker层  ┌──────────────────────▼───────────────────────────┐
         │              redis_worker.py (20并发)              │
         │   Agent路由 → 直接对话 / 云枢调度                   │
         └──┬────────────────────────────┬───────────────────┘
            │                            │
编排层   直接对话                    云枢调度(yunshu_io)
         hermes chat                 PLAN → execute_plan_graph
            │                            │
执行层    Banni / Basir / 云衡        SPAWN → WAIT → REFLECT → REPLY
         (独立子进程隔离)              (代码按依赖图自动调度)
```

## 核心引擎

| 引擎 | 文件 | 职责 |
|------|------|------|
| **Yunshu (云枢)** | `yunshu_io.py` | LLM 文本协议调度，PLAN→SPAWN→WAIT→REFLECT→REPLY |
| **Orchestrator** | `orchestrator.py` | 结构化任务编排，Plan-first 模式 |
| **Orch Runner** | `runner.py` | DAG 依赖链执行，contract 预定义 |

## Agent 矩阵

| Agent | 角色 | 能力 |
|-------|------|------|
| **Banni (云筑)** | 工程执行 | 搜索、代码编写、文件操作、飞书文档 |
| **Basir (云鉴)** | 数据分析 | 逻辑推理、报告生成、架构分析 |
| **云衡** | 软件测试 | TDD、代码审查、安全扫描、缺陷诊断 |

### 路由规则

| 选择 Agent | 模式 |
|-----------|------|
| 云枢 | 调度模式 → 自动派发 Banni/Basir/云衡 |
| Banni / Basir / 云衡 | 直接对话 → hermes chat 独立执行 |

## 方案 B：代码接管调度

PLAN 解析后由 `execute_plan_graph()` 按依赖图自动执行，LLM 不再参与状态切换。

```
用户消息 → 云枢 PLAN → PlanGraph.parse() → get_parallel_groups()
         → 批次 SPAWN → WAIT_ALL → REFLECT → REPLY
```

**优势：**
- 消除 LLM 对协议理解的依赖（不再"困惑→重 PLAN"）
- 依赖图天然支持并行批次
- 减少 LLM 调用轮数

## 可视化监控

每个父任务自动生成 **TaskNode 节点图**：

- **数据模型**: `TaskNode` (models.py)
- **追踪点**: PLAN→build_from_plan / SPAWN→关联 child_task / CHECK→更新状态
- **API**: `GET /api/parent-tasks/{id}/graph/` — 返回 nodes + edges + 瓶颈
- **前端**: `TaskGraph.jsx` — DAG 层布局 + SVG 连线 + 状态颜色
- **停止**: `POST /api/parent-tasks/{id}/stop/` — 手动终止

```
t1 [banni] 执行中 ──┐
t2 [banni] 完成 ──→ t3 [basir] 执行中 ──┤
                                        ├──→ t4 → t5 → t6 → t7
```

## 跨端上下文

`context_aggregator.py` 聚合飞书 + Web 端最近 2 小时消息，注入云枢 Round 0 context。

- 按时间线合并多 source 消息
- 自动去重（跳过与当前消息相同的条目）
- 上限：20 条 / 4000 字符

## 超时策略

| 级别 | 配置 | 触发 |
|------|------|------|
| 子任务 | 300s | 单 Agent 执行超时 → SIGKILL |
| Hermes 调用 | 300s | 单次 LLM 问答超时 → 返回空 |
| 编排总 | 600s | 整个编排流程 → fallback reply |
| wait_all | 600s | 等待子任务完成 → 收集后继续 |

## 快速开始

```bash
# 启动服务
systemctl --user start agent-backend    # Django :8001
systemctl --user start agent-worker     # redis_worker
systemctl --user start agent-frontend   # Vite Preview :5174

# 检查状态
systemctl --user status agent-backend agent-worker agent-frontend

# 访问
open http://192.168.31.99:5174
```

## 项目结构

```
agent-platform/          # Django 后端
├── agents/
│   ├── yunshu_io.py         # 云枢调度器 v4.1 (方案B)
│   ├── redis_worker.py      # Redis Worker (20并发)
│   ├── orchestrator.py      # 结构化编排器
│   ├── plan_parser.py       # PLAN 解析 + PlanGraph
│   ├── agent_registry.py    # Agent 注册表
│   ├── context_aggregator.py # 跨端上下文聚合
│   ├── pitfall_memory.py    # 踩坑记忆系统
│   ├── task_api.py          # 任务状态机 API
│   ├── models.py            # Django 模型
│   ├── views.py             # API View + 输出面板
│   └── urls.py              # URL 路由
├── agent_platform/          # Django 项目配置
│   └── settings.py          # 数据库/Redis/CORS
└── agent-frontend/          # React 前端
    └── src/
        ├── App.jsx
        ├── components/views/
        │   ├── Tasks.jsx        # 任务管理(表格+节点图)
        │   ├── TaskGraph.jsx    # DAG 节点可视化
        │   ├── Sessions.jsx     # 会话中心
        │   ├── ChatPage.jsx     # 实时对话
        │   └── OutputView.jsx   # 输出面板
        └── index.css
```

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | Vite + React + CSS Variables |
| API | Django REST Framework + gunicorn |
| 数据库 | SQLite (WAL模式) |
| 消息队列 | Redis (Pub/Sub + List) |
| 编排 | Python subprocess + ThreadPool |
| Agent | Hermes CLI + DeepSeek API |

---

*AgentOS v4.1 — 方案 B · 2026-06-24*
