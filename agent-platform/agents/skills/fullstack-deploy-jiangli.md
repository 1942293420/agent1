---
name: 前后端部署设计skill——jiangli
slug: fullstack-deploy-jiangli
version: 1.0.0
status: active
source: local
category: devops
description: >
  Agent Platform 项目（agent-platform + agent-frontend）的完整架构文档、部署流程、
  常见问题排查指南。包含前后端端口、虚拟环境、分页配置、API 设计等全部约定。
tags: [deploy, fullstack, django, react, hermes]
---

# 前后端部署设计 Skill — jiangli

## 项目概览

### 架构
```
┌──────────────────────┐      ┌──────────────────────┐
│   agent-frontend      │      │   agent-platform      │
│   React 19 + Vite     │◄────►│   Django 4 + DRF      │
│   Tailwind CSS 4      │ API  │   SQLite              │
│   Port: 5174          │      │   Port: 8001           │
└──────────────────────┘      └──────────────────────┘
         │                            │
         │  192.168.31.99:5174        │  192.168.31.99:8001
         ▼                            ▼
    用户浏览器                      Agent 调度引擎
```

### 项目路径
| 项目 | 路径 | 端口 | 启动命令 |
|------|------|------|----------|
| 后端 | `/home/jiangli/projects/agent-platform` | 8001 | `./venv/bin/python manage.py runserver 0.0.0.0:8001` |
| 前端 | `/home/jiangli/projects/agent-frontend` | 5174 | `npm run dev -- --host 0.0.0.0` |

### 关键凭证
- 管理员：`admin` / `admin123`
- 后端虚拟环境：`agent-platform/venv/`
- 前端 Vite Proxy：`/api` → `localhost:8001`

---

## 页面路由

| 路由 | 标题 | 功能 |
|------|------|------|
| `/` | Dashboard | Agent 统计、任务概览、知识库 |
| `/agents` | Agent 管理 | 注册、心跳、能力标签、HMAC 密钥 |
| `/skills` | 技能库 | 181 个技能、4 列网格、50 条/页、Agent 筛选 |
| `/tasks` | 任务管理 | 调度、状态流转、执行日志 |
| `/knowledge` | 知识库 | 50 条公开知识条目 |

---

## API 端点

### Skills API
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/skills/?page_size=50&page=1` | 列表（分页） |
| GET | `/api/skills/?agent=1` | 按 Agent 筛选 |
| GET | `/api/skills/?status=active` | 按状态筛选 |
| GET | `/api/skills/?search=飞书` | 搜索 |
| GET | `/api/skills/{slug}/` | 详情 |
| POST | `/api/skills/` | 创建 |
| PATCH | `/api/skills/{slug}/` | 更新 |

**返回字段（SkillSerializer）**：
`id, name, slug, version, description, file_url, source, status, category, tags, agent_count, knowledge_count, agent_names, created_at, updated_at`

### Agent API
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/agents/register/` | 注册（返回 secret_key） |
| POST | `/api/agents/{id}/heartbeat/` | 心跳 |
| POST | `/api/agents/{id}/assign-skill/` | 分配技能 |
| POST | `/api/agents/{id}/pull-tasks/` | 拉取任务 |

---

## 常见问题排查

### 1. 技能列表只显示 20 个（或少于实际数量）

**根因**：`SkillViewSet` 缺少 `pagination_class`，DRF 默认 `PAGE_SIZE=20`。

**修复**：
```python
# agents/views.py
class SkillViewSet(viewsets.ModelViewSet):
    pagination_class = StandardPagination  # ← 加上这行
```

**验证**：
```bash
curl -s 'http://localhost:8001/api/skills/?page_size=200' | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print(d['count'])"
# 应输出 181
```

### 2. 如何检查某个 Skill 是否存在

```bash
# 按 slug 查详情
curl -s 'http://localhost:8001/api/skills/feishu-doc-create/' | python3 -m json.tool

# 按名称搜索
curl -s 'http://localhost:8001/api/skills/?search=飞书' | python3 -c \
  "import json,sys; d=json.load(sys.stdin); [print(r['slug'],r['name']) for r in d['results']]"

# Django shell 查
cd /home/jiangli/projects/agent-platform
./venv/bin/python manage.py shell -c "
from agents.models import Skill
for s in Skill.objects.filter(name__contains='飞书'):
    print(s.id, s.slug, s.name)
"
```

### 3. 后端启动失败

| 错误 | 原因 | 解决 |
|------|------|------|
| `ModuleNotFoundError: django` | 未激活虚拟环境 | 用 `./venv/bin/python` 而非 `python3` |
| `AssertionError: basename` | ViewSet 缺少 `queryset` 或 `basename` | 保留 `queryset` 类属性 |
| `Port 8001 already in use` | 旧进程未清理 | `pkill -f "runserver.*8001"` |

### 4. 分页参数说明

| 参数 | 含义 | 默认 | 最大 |
|------|------|------|------|
| `page_size` | 每页条数 | 20 | 200 |
| `page` | 页码 | 1 | — |

**StandardPagination 定义**（`agents/views.py`）：
```python
class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 200
```

### 5. Agent 筛选

`?agent=1` 筛选飞书助手小温，`?agent=2` 筛选数据分析师。

实现（`SkillViewSet.get_queryset`）：
```python
agent_id = self.request.query_params.get('agent')
if agent_id:
    qs = qs.filter(agent_assignments__agent_id=agent_id, agent_assignments__is_active=True)
```

### 6. 技能翻译批量更新

脚本：`/home/jiangli/projects/agent-platform/translate_skills.py`
用于将技能 name + description 批量翻译为中文。

---

## 数据库表结构

| 表 | 说明 | 关键字段 |
|----|------|----------|
| `agents_agent` | Agent 注册 | name, feishu_app_id, secret_key, status |
| `agents_skill` | 技能库 | name, slug, description, category, status |
| `agent_skill_assignments` | 分配关系 | agent_id, skill_id, is_active |
| `agents_task` | 任务 | title, agent_id, status, parent_task_id |
| `agents_executionlog` | 执行日志 | task_id, agent_id, level, message |
| `agents_knowledgeentry` | 知识条目 | title, content, visibility, relevance_score |
| `agents_capabilitytag` | 能力标签 | name, slug |

---

## 前端关键约定

### SkillsPage 分页逻辑
```jsx
const PAGE_SIZE = 50;
const [currentPage, setCurrentPage] = useState(1);
const [totalCount, setTotalCount] = useState(0);

const fetchSkills = useCallback((page = 1) => {
  const params = { page_size: PAGE_SIZE, page };
  getSkills(params).then((data) => {
    setSkills(data.results);
    setTotalCount(data.count);
    setCurrentPage(page);
  });
}, [filter, agentFilter]);
```

### 网格布局
```jsx
<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
```

---

## 网络地址

| 服务 | 内网 | 说明 |
|------|------|------|
| 后端 API | `http://192.168.31.99:8001` | Django REST |
| 前端控制台 | `http://192.168.31.99:5174` | React 暗黑主题 |
| 管理后台 | `http://192.168.31.99:5174/admin` | admin/admin123 |
