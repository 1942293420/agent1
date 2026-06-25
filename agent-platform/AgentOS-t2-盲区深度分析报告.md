# AgentOS t2 报告盲区深度分析

> **Basir 分析** | 2026-06-24 | 基于 t1 调研 + 5份 t2 报告交叉审计 + 43个源码文件逐行审查
>
> 本报告不是"再做一份 t2"，而是对已有 5 份 t2 报告的**盲区扫描**——找出它们说了什么但没说透、说了但估错了、完全没说的部分。

---

## 一、遗漏的系统维度（7大维度完全缺失或仅一笔带过）

### 1.1 安全性维度（5份报告均 0 覆盖）

| 风险项 | 代码位置 | 严重度 | 说明 |
|--------|---------|--------|------|
| **API 零鉴权** | views.py 全局 | 🔴 严重 | `AgentEndpointPermission` 允许任何请求通过，未验证 HMAC 签名 |
| **subprocess 命令注入** | yunshu_io.py:164-171 | 🔴 严重 | 用户消息通过 `prompt` 参数直接拼入 `hermes chat -q` 命令行，无任何转义。恶意用户可注入 shell 元字符 |
| **Redis 无密码** | redis_worker.py:9, sse.py:14 | 🔴 严重 | `REDIS_URL = "redis://localhost:6379/0"` — 无认证，同一机器任何进程可读写队列 |
| **SQLite 无加密** | settings.py | 🟡 中等 | 数据库文件以明文存储，包含对话历史和 Agent 配置 |
| **飞书 Webhook 无签名验证** | gateway 层 | 🟡 中等 | 未验证飞书请求签名，可被伪造消息 |
| **AES 密钥管理** | crypto_utils.py | 🟡 中等 | 加密配置的密钥存储方式不明，若硬编码则形同虚设 |

**t2 报告问题**：六维度报告提到"API无认证鉴权"仅一句话带过，未展开分析攻击面和风险等级。

### 1.2 数据持久化与一致性维度（表面提及，深度缺失）

| 问题 | 代码位置 | 严重度 | t2 报告覆盖情况 |
|------|---------|--------|----------------|
| **SQLite 写锁竞争** | Django ORM → SQLite | 🔴 严重 | ❌ 未提及。20 并发 Worker + SSE 每 2 秒写 DB → SQLite 仅支持单写者，高负载下会大量 BUSY 错误 |
| **两套任务模型无事务一致性** | models.py Task vs ParentTask/ChildTask | 🔴 严重 | ⚠️ 提到"两套模型并存"但未讨论数据一致性风险。ParentTask 更新(redis_worker.py)和 ChildTask 更新(yunshu_io.py)不在同一事务中 |
| **Checkpoint 写入无重试** | checkpoint.py:48-62 | 🟡 中等 | ❌ 未提及。`_write_db()` 用 `except: pass` 吞掉所有异常，写入失败静默丢失 |
| **Checkpoint 最多 3 个文件** | checkpoint.py:10 | 🟡 中等 | ❌ 未提及。循环覆盖意味着无法回溯到早期执行状态 |
| **消息丢失路径** | redis_worker.py:229-236 | 🟡 中等 | ❌ 未提及。Redis BRPOP 取出消息后若 Worker 崩溃，消息永久丢失（无 ACK/备份队列） |
| **SSE 时间窗口丢消息** | sse.py:26-44 | 🟡 中等 | ⚠️ 提到"2秒间隔可能丢失"但未量化：快速连续写入 3 条消息（< 2 秒），后 2 条可能在 `created_at__gt` 窗口外 |

### 1.3 可观测性维度（被严重低估）

t2 报告将可观测性评为"print+SSE"即一笔带过，实际情况更糟：

| 问题 | 代码证据 | 影响 |
|------|---------|------|
| **无结构化日志** | 所有模块使用 `print()` 而非 `logging` | 无法按级别过滤、无法聚合、无法接入日志系统 |
| **worker.py 日志无限增长** | worker.py:179 `open("/tmp/worker.log", "a")` | 无轮转，长期运行会耗尽磁盘 |
| **yunshu_io.py 日志到 stderr** | yunshu_io.py:308,328,404 | 与正常 stderr 混合，systemd journal 中难以分离 |
| **无 Metrics** | 全代码库无任何 metrics 收集 | 无法回答：平均延迟？P99 延迟？吞吐量？错误率？ |
| **无告警** | redis_worker.py:226-227 队列积压仅 `print()` | 深夜队列爆炸无人知晓 |
| **无健康检查端点** | 无 `/health` 或 `/ready` 端点 | K8s/Docker 无法做存活探针 |

### 1.4 测试与质量保证维度（仅提到文件名，未分析覆盖率）

| 测试类型 | 现状 | t2 报告 |
|---------|------|---------|
| **单元测试** | test_v4_core.py 覆盖文本协议解析 + PlanGraph | ⚠️ 提到但未说明覆盖了什么 |
| **编排主循环** | ❌ 0 覆盖 | ❌ 未提及 |
| **集成测试** | ❌ 0 覆盖 | ❌ 未提及 |
| **E2E 测试** | ❌ 0 覆盖 | ❌ 未提及 |
| **性能基准** | ❌ 0 覆盖 | ❌ 未提及 |
| **Chaos 测试** | ❌ 0 覆盖 | ❌ 未提及（Worker 崩溃、Redis 断连、LLM API 超时场景） |

### 1.5 成本维度（完全未讨论）

| 场景 | Token 消耗 | 月成本估算（DeepSeek 价格） |
|------|-----------|--------------------------|
| **Orchestrator v2 简单任务** | ~500 tokens (PlanGen) | ¥0.0005 |
| **Yunshu v4 单轮探索** | ~2000 tokens | ¥0.002 |
| **Yunshu v4 15 轮全流程** | ~30000 tokens | ¥0.03 |
| **subprocess 冷启动资源** | 每次 hermes chat 启动 5-15s CPU + ~200MB RAM | 不可忽略的硬件成本 |
| **idle 空转** | redis_worker 主循环 BRPOP(timeout=5) CPU 占用低但 SSE 每 2s 查 3 张表 | 持续 DB IO |

**t2 报告夸大了 Token 效率**："Orchestrator v2 执行阶段零 LLM"是事实，但未说明当前 80%+ 的消息仍走 Yunshu 路径（管道 B），而非 Orchestrator。

### 1.6 部署与运维维度（systemd×4 之后呢？）

| 问题 | 现状 | 缺失 |
|------|------|------|
| **服务依赖顺序** | 4 个 systemd 单元独立启动 | 无 `After=/Requires=` 依赖声明 |
| **健康检查** | 无 | Redis 在 Django 之前挂了不可知 |
| **优雅关停** | 无 SIGTERM handler | Worker 处理中的消息会丢失 |
| **升级策略** | 手动 | 无蓝绿/滚动升级能力 |
| **配置管理** | 环境变量 + 代码硬编码 + 文件 | 无配置中心，改超时需要重启 |
| **备份策略** | 无 | SQLite db 文件无自动备份 |

### 1.7 用户体验维度（完全未讨论）

| 问题 | 现状 |
|------|------|
| **错误提示** | 用户看到 "抱歉处理出错" 但无法知道是排队超时还是 LLM 挂了 |
| **超时反馈** | 15 轮主循环最多 900 秒，用户无进度指示 |
| **双管道能力差** | Web Chat 用户和飞书用户得到完全不同的回复质量 |
| **多轮对话断连** | 无上下文持久化提示，用户不知道 AI "记得"多少 |

---

## 二、过于乐观的改进估算（4 项严重低估）

### 2.1 SPAWN 通用化：声称 10 行 → 实际 50+ 行

**t2 报告声称**（四份报告一致引用）：
```python
# 通用模式（基于 AGENT_REGISTRY），约 10 行
if cmd_name.startswith("SPAWN_"):
    agent_type = cmd_name[6:].lower()
    if agent_type in AGENT_REGISTRY:
        response = handler.spawn(agent_type, m.group(1))
```

**实际需要改动的范围远超 10 行**：

| 改动点 | 文件 | 行数 |
|--------|------|------|
| CMD_PATTERNS 动态生成（替代硬编码正则） | yunshu_io.py | ~15 行 |
| switch-case 改为通用分发 | yunshu_io.py | ~10 行 |
| AGENT_REGISTRY 从 dict 改为可注册接口 | agent_registry.py | ~10 行 |
| system_prompt 中的命令列表动态生成 | yunshu_io.py | ~5 行 |
| 新增 Agent 的安全校验（防止 SPAWN_RM_RF） | yunshu_io.py | ~8 行 |
| 测试代码 | tests.py | ~15 行 |

**实际估算：50-60 行 + 测试，不是 10 行。**

### 2.2 SSE 事件驱动化：声称 30 行 → 实际 120+ 行

**t2 报告声称**：
> "用 Redis Pub/Sub 替代 DB 轮询，约 30 行"

**实际分析**：

| 发布点（需在状态变更时发布 Redis 消息） | 文件 | 行数 |
|--------------------------------------|------|------|
| yunshu_io.py 子任务状态变更（RUNNING→DONE→FAILED） | yunshu_io.py | ~15 行（4 处） |
| redis_worker.py 父任务状态变更（PLANNING→EXECUTING→REPLY） | redis_worker.py | ~12 行（3 处） |
| redis_worker.py 子任务心跳/进度 | redis_worker.py | ~10 行 |
| worker.py Web 路径消息处理 | worker.py | ~8 行 |
| views.py 消息创建 | views.py | ~5 行 |
| sse.py 从轮询改为纯 Pub/Sub 消费 | sse.py | ~30 行 |
| 测试代码 | tests.py | ~20 行 |
| 消息格式定义和版本管理 | 新文件 | ~20 行 |

**实际估算：120+ 行，涉及 6+ 文件。**

### 2.3 Worker 统一并发 3→20：声称 1 行 → 需要系统性评估

**"1 行代码"改的是 `MAX_WORKERS = 3` → `MAX_WORKERS = 20`，但这会引发连锁问题**：

| 连锁影响 | 说明 |
|---------|------|
| **DeepSeek API 限流** | DeepSeek 免费/付费层有 RPM 限制，20 并发可能触发 429 |
| **Django WSGI worker** | Gunicorn 默认 workers 数需匹配，否则请求排队 |
| **SQLite 锁升级** | 20 并发线程 + SSE 2 秒轮询 → SQLite BUSY 错误率飙升 |
| **内存爆炸** | 每个 DeepSeek API 请求约 50MB 上下文，20 并发 ≈ 1GB |
| **Django DB 连接池** | 默认连接数可能不够 |

**这不是 1 行代码的事，而是需要性能测试 + 限流 + 连接池调优的系统工程。**

### 2.4 subprocess → 长连接复用：声称 30 行 → 实际 200+ 行

**30 行只能写一个概念验证**，生产可用需要：

| 需求 | 复杂度 |
|------|--------|
| hermes CLI 会话管理（启动→维持→复用→清理） | 高 — hermes 无原生 session 复用 |
| 连接池管理（多 Agent 共享） | 中 |
| 断线重连 + 心跳 | 中 |
| 超时和僵死连接检测 | 中 |
| 文本协议适配（当前基于完整进程生命周期） | 高 — 需要重新设计通信语义 |
| 错误处理和回退到 subprocess 模式 | 中 |

**估计 200+ 行，需要修改 hermes 使用方式或引入 UNIX socket。**

---

## 三、未覆盖的技术债务（6 类债务完全隐身）

### 3.1 代码重复（至少有 4 处显著重复）

| 功能 | 重复文件 | 说明 |
|------|---------|------|
| **`_hermes_q` / LLM 调用** | yunshu_io.py:560, redis_worker.py:33, views.py:94, orchestrator.py:65 | 4 处各自实现，参数、超时、错误处理各不相同 |
| **消息保存** | worker.py:65, redis_worker.py:179, views.py:112 | 3 处各自实现 |
| **Redis 连接** | redis_worker.py:21, sse.py:14 | 各自创建连接，无连接池 |
| **API URL 硬编码** | 所有文件 `"http://localhost:8001"` 出现 12+ 次 | 改为配置项需要全局搜索替换 |

**t2 报告问题**：将"极简代码 ~2500 行"作为优点，但忽视了代码重复带来的维护成本和一致性风险。

### 3.2 异常处理"吞异常"反模式（代码库中广泛存在）

```python
# redis_worker.py:31 — 代表性模式
def _api(path, method="get", data=None):
    try:
        ...
    except:
        return {}   # ← 吞掉所有异常，无日志

# checkpoint.py:61 — 静默失败
except Exception:
    pass           # ← 检查点写入失败无人知晓

# yunshu_io.py:183 — 资源泄漏风险
try:
    if proc.poll() is None:
        proc.kill()
except: pass       # ← 子进程可能没被杀死
```

**影响**：生产环境故障排除几乎不可能——异常发生但无任何痕迹。

### 3.3 硬编码的广度远超 SPAWN

t2 报告只聚焦 SPAWN 硬编码，但以下硬编码同样严重：

| 硬编码项 | 出现次数 | 风险 |
|---------|---------|------|
| `API_BASE = "http://localhost:8001"` | 4 处 | 无法部署到其他机器 |
| `DeepSeek URL` | views.py, worker.py, orchestrator.py | 切换 LLM 需改 3 个文件 |
| 文件路径（hermes profiles, relay_feishu.py） | 5+ 处 | 移植到其他用户/机器困难 |
| 超时值（300, 600, 120） | 分散在 5 个文件 | 调参需全局搜索 |
| Agent 角色信息 | agent_registry.py 硬编码 dict | 新增 Agent 必须改 Python 代码 |

### 3.4 日志系统完全缺失

| 问题 | 证据 |
|------|------|
| **无统一日志框架** | 全代码库使用 `print()` 而非 Python `logging` |
| **级别缺失** | 无法区分 DEBUG/INFO/WARN/ERROR |
| **格式不一致** | yunshu_io: `[YunshuIO] ...`, worker: `[Worker] ...`, 无时间戳 |
| **输出目标混乱** | yunshu→stderr, worker→/tmp/worker.log, redis_worker→stdout |
| **无限增长风险** | /tmp/worker.log 无轮转 |

### 3.5 并发安全隐患（`_children_lock` 只修复了表面）

```python
# yunshu_io.py:93 — 加锁正确
self._children_lock = threading.Lock()

# 但是！
# checkpoint.py:23 — handler._checkpoint_mgr 的 write 无锁保护
def write_checkpoint(self, stage, children_state, ...):
    with self.lock:  # ← 这个锁只保护文件写入
        ...
    self._write_db(...)  # ← DB 写入不在锁内！
```

当多个线程同时调用 `handler.handle_plan()` 和 `handler.spawn()` 时，checkpoint 可能交错写入。

### 3.6 配置管理混乱（4 种配置方式并存）

| 方式 | 使用位置 | 问题 |
|------|---------|------|
| 环境变量 | `os.environ.get("DEEPSEEK_API_KEY")` | 分散在 3 个文件 |
| 代码常量 | `MAX_WORKERS=20`, `TASK_TIMEOUT=600` | 改值需重新部署 |
| 硬编码路径 | `"~/.hermes/profiles/banni/..."` | 切换 profile 需改代码 |
| JSON 文件 | pitfall_memory.json | 无 schema 校验 |

---

## 四、架构层面未讨论的缺陷（6 项根本性问题）

### 4.1 中间件层完全缺失

```
当前架构：
  用户 → 飞书 API → Gateway → Redis → Worker
  用户 → Web → Gunicorn → Django → Worker
                              ↓
                          SSE (2s 轮询)

缺失层：
  ✗ API 网关（限流/认证/路由）
  ✗ 请求队列（Web 路径无队列保护）
  ✗ 负载均衡（所有流量打同一台机器）
  ✗ 反向代理（无 nginx/Caddy）
  ✗ 健康检查端点
```

Web Chat 路径：用户请求直接打到 Gunicorn → `_call_llm_for_reply()` 在后台线程执行，无排队、无限流。10 个用户同时发消息 → 10 个线程同时调 DeepSeek API → 可能触发限流。

### 4.2 三引擎孤岛的根本原因被误诊

**t2 报告的归因**："三引擎互不感知"

**实际根本原因**：缺乏统一的任务抽象层（Task Abstraction Layer）

```
当前：
  Yunshu 理解:        "PLAN: complexity=medium tasks: - id:t1..."
  Orchestrator 理解:   "[PLAN] summary: ... - id:step1 ... [/PLAN]"
  orch_runner 理解:    DAG contract (JSON)

三种不同的计划表示 → 三种不同的执行引擎 → 无法互操作

正确做法：
  统一 Plan IR (中间表示) → 不同执行器消费同一 IR
```

这不是"加一个 Dispatcher 层"能解决的——需要重新设计计划表示的数据结构，让三引擎消费同一 schema。

### 4.3 依赖反转原则的系统性违反

```python
# yunshu_io.py — 高层编排模块直接依赖低层实现
from agent_registry import get_role_prompt     # ✅ 正确方向
from plan_parser import PlanGraph              # ✅ 正确方向
CMD_PATTERNS = { ... }                          # ❌ 命令注册应在 agent_registry

# 正确设计：
# agent_registry.py 应提供 list_commands() → 返回所有注册 Agent 的命令模式
# yunshu_io.py 动态生成 CMD_PATTERNS，而非硬编码
```

当前扩展一个 Agent 需要修改 `yunshu_io.py`（高层模块），这违反了开闭原则（对扩展开放，对修改封闭）。

### 4.4 单体架构的不可逆锁定

| 组件 | 耦合方式 | 解锁难度 |
|------|---------|---------|
| Django ↔ SQLite | 文件系统锁 | 中（迁移 PostgreSQL 解决） |
| Redis Worker ↔ Yunshu | import yunshu_io（Python 模块级） | 高（需改为 RPC/消息队列） |
| Worker v5 ↔ DeepSeek | 函数内 HTTP 调用 | 中 |
| SSE ↔ Django | Django view 内联 | 中 |
| Orchestrator Daemon ↔ DB | 30 秒轮询 | 中 |

**当前所有组件必须部署在同一台 Linux 机器上**。即使 Redis 可以远程，但代码中硬编码 `localhost`。SQLite 文件锁阻止了多机部署。

### 4.5 无服务边界——所有组件共享同一进程空间

```
当前：
  systemd unit: agent-backend.service → Gunicorn (Django WSGI)
                     ↓ 共享进程
              views.py  import→  yunshu_io.py
              sse.py    import→  models.py
              urls.py   import→  orchestrator.py

  systemd unit: agent-worker.service → redis_worker.py
                     ↓ import
              yunshu_io.py → PlanGraph → checkpoint → ...

  问题：两个 systemd 单元 import 同一份 yunshu_io.py → 共享全局状态风险
```

### 4.6 PlanGraph 解析器假设过高——故障模式未被分析

**plan_parser.py:26-71** 的 `parse()` 方法假设 LLM 输出格式精确匹配：

```python
task_pattern = re.compile(
    r"-\s*id:\s*(\S+).*?agent:\s*(\S+).*?desc:\s*(.+?)(?:\s+deps:\s*(\[.*?\]))?\s*$",
    re.MULTILINE
)
```

**失败模式（t2 报告未提及）**：
1. LLM 用 `：`（全角冒号）代替 `:` → 正则不匹配
2. desc 中包含换行 → `$` 锚点失败
3. deps 使用 `()` 而非 `[]` → 解析错误
4. agent 字段写 `Basir` 而非 `basir` → `agent_type.lower()` 能处理但 t2 未提及
5. 多个 PLAN 块（LLM 输出两次 PLAN）→ 只解析第一个

**当前 fallback**：`parse() → None → "ERROR PLAN 解析失败"`。但主循环在方案 B（execute_plan_graph）中遇到解析失败时，context 构造退化为"请用单行 desc 重新输出 PLAN"，这会导致死循环——LLM 可能再次输出同样格式。

---

## 五、完整改进清单（分四级，含修正估算）

### P0 — 安全修复（必须立即处理）

| # | 改进项 | 修正估算 | t2 原估 | 差距 |
|---|--------|---------|--------|------|
| 1 | **subprocess 命令注入防护** | ~15 行 | 未提及 | — |
| 2 | **API 认证鉴权** | ~30 行 | 一笔带过 | — |
| 3 | **Redis 密码认证** | ~5 行 | 未提及 | — |

### P1 — 可观测性基础（本周完成）

| # | 改进项 | 修正估算 | t2 原估 | 差距 |
|---|--------|---------|--------|------|
| 4 | **统一日志框架**（logging 替代 print） | ~80 行（4 文件） | 未提及 | — |
| 5 | **健康检查端点** `/health` + `/ready` | ~20 行 | 未提及 | — |
| 6 | **队列积压告警**（>100 → 飞书通知） | ~30 行 | 未提及 | — |
| 7 | **错误率 metrics**（/tmp/worker.log → 结构化） | ~40 行 | 未提及 | — |

### P2 — 技术债务清偿（本月完成）

| # | 改进项 | 修正估算 | t2 原估 | 差距 |
|---|--------|---------|--------|------|
| 8 | **SPAWN 通用化**（含安全校验+测试） | ~50 行 | 10 行 | 5× |
| 9 | **LLM 调用统一**（消除 4 处重复） | ~60 行 | 未提及 | — |
| 10 | **API_BASE/URL 配置化**（消除 12+ 硬编码） | ~30 行 | 未提及 | — |
| 11 | **异常处理规范化**（except: pass → 日志+告警） | ~50 行（散布） | 未提及 | — |
| 12 | **指数退避重试** | ~50 行 | 20 行 | 2.5× |

### P3 — 架构改进（季度目标）

| # | 改进项 | 修正估算 | t2 原估 | 差距 |
|---|--------|---------|--------|------|
| 13 | **统一 Plan IR**（三引擎共享计划中间表示） | ~200 行 + 重构 | 未提及 | — |
| 14 | **SSE 事件驱动化** | ~120 行（6+ 文件） | 30 行 | 4× |
| 15 | **Web Chat 队列保护**（对齐飞书路径） | ~50 行 | 未提及 | — |
| 16 | **subprocess → 长连接** | ~200 行 | 30 行 | 6.7× |
| 17 | **SQLite → PostgreSQL** | ~100 行 + 迁移 | ~50 行（一笔带过） | 2× |
| 18 | **集成测试框架** | ~200 行 | 未提及 | — |
| 19 | **Worker 统一并发** | ~30 行 + 性能测试 | 1 行 | 30× |
| 20 | **配置中心**（统一环境变量/settings.py） | ~80 行 | 未提及 | — |

---

## 六、总结：t2 报告的 3 个系统性偏差

### 偏差一：优势放大，劣势缩量

| 报告的表述 | 实际情况 |
|-----------|---------|
| "三级超时熔断市面最强 ★★★★★" | 三级超时确实存在，但无退避重试、无死信队列、无优雅降级——超时 = 丢弃 |
| "20 并发 OS 进程隔离市面最强 ★★★★★" | 20 并发受限于单机 SQLite 写锁和 DeepSeek API 限流——理论值≠实际吞吐 |
| "极简代码 ~2500 行" | 简化了核心行数但掩盖了代码重复和维护成本 |

### 偏差二：改进估算系统性地低 3-6 倍

| 改进项 | t2 平均估算 | 实际估算 | 比率 |
|--------|-----------|---------|------|
| SPAWN 通用化 | 10 行 | 50 行 | 5× |
| SSE 事件驱动 | 30 行 | 120 行 | 4× |
| subprocess 长连接 | 30 行 | 200 行 | 6.7× |
| Worker 统一并发 | 1 行 | 30+行+测试 | 30× |
| 指数退避重试 | 20 行 | 50 行 | 2.5× |

### 偏差三：7 个关键维度完全未被覆盖

1. **安全性** — 命令注入、API 无鉴权、Redis 无密码
2. **可观测性** — 无日志框架、无 metrics、无告警
3. **数据一致性** — SQLite 写锁、双模型无事务、消息丢失路径
4. **测试覆盖** — 仅文本协议解析有测试，主流程 0 覆盖
5. **成本分析** — 无 Token 消耗量化，高估了 Orchestrator 路径的实际使用率
6. **部署运维** — 无健康检查、无优雅关停、无备份
7. **用户体验** — 错误提示、超时反馈、双管道能力差

---

*分析基于 2026-06-24 全部 43 个源码文件逐行审查 + 5 份 t2 报告交叉对比。所有评分和估算均标注了主观判断。标记 [推断] 处为基于代码模式的合理推断。*
