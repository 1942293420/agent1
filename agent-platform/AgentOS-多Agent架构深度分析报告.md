# AgentOS 多Agent架构深度技术分析报告

> **分析日期**：2026-06-24
> **代码基础**：基于 `/home/jiangli/projects/agent-platform` 实际源码
> **分析方法**：逐文件阅读 + 交叉引用验证，不臆测

---

## 目录

1. [总体架构概览](#1-总体架构概览)
2. [三权分立架构](#2-三权分立架构)
3. [v4文本协议](#3-v4文本协议)
4. [通信机制](#4-通信机制)
5. [任务调度](#5-任务调度)
6. [Worker层](#6-worker层)
7. [安全架构](#7-安全架构)
8. [容错设计](#8-容错设计)
9. [数据模型](#9-数据模型)
10. [组件关系拓扑图](#10-组件关系拓扑图)

---

## 1. 总体架构概览

AgentOS 是一个基于 Django REST Framework 的多 Agent 协作平台，运行在 `localhost:8001`，采用 **Redis 消息队列 + systemd 服务管理** 的架构模式。

### 1.1 核心服务（4个 systemd --user 服务）

| 服务 | systemd 名称 | 端口 | 文件 | 职责 |
|------|-------------|------|------|------|
| API 后端 | `agent-backend` | 8001 | `gunicorn agent_platform.wsgi` | REST API，消息入库 + Redis 入队 |
| Web 前端 | `agent-frontend` | 5174 | `npx vite preview` | React SPA，12 个管理视图 |
| 消息 Worker | `agent-worker` | — | `agents/redis_worker.py` | 从 Redis 拉取消息，驱动云枢/Agent 执行 |
| 编排守护 | `orch-daemon` | — | `orchestrator_daemon.py` | 每 30s 轮询 pending Task，触发编排执行 |

### 1.2 消息处理全链路

```
用户消息 → Django POST /api/messages/
  → SQLite INSERT (processed=False)
  → Redis LPUSH msg_queue
  → agent-worker BRPOP 拉取
  → 调用 yunshu_io.run_yunshu_session() 启动云枢
  → 云枢解析 PLAN，SPAWN 子Agent (Banni/Basir)
  → WAIT_ALL 等待完成 → REFLECT 自检 → REPLY 最终回复
  → 保存到 DB (processed=True)，标记已处理
  → 飞书 relay（如是飞书来源）
```

---

## 2. 三权分立架构

AgentOS 的核心设计哲学是 **三权分立**，每一层有明确的职责边界：

### 2.1 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                      AgentOS 三权分立                         │
├───────────────┬──────────────────┬───────────────────────────┤
│  Worker (管命) │  云枢 Yunshu (管脑)│  Banni/Basir (管手)       │
│  进程监控/生命周期│  调度决策/任务分解 │  独立执行/工具操作         │
├───────────────┼──────────────────┼───────────────────────────┤
│ redis_worker  │  yunshu_io.py    │  hermes chat -p banni/basir│
│                 orchestrator.py  │                           │
└───────────────┴──────────────────┴───────────────────────────┘
```

### 2.2 Worker 层（管命）—— 进程监控与生命周期管理

**核心文件**：`agents/redis_worker.py`（v7.0）

Worker 的职责是**管理所有 Agent 子进程的生命周期**，确保不失控：

- **消息拉取**：`redis.brpop("msg_queue", timeout=5)` 阻塞式拉取
- **父任务创建**：通过 `POST /api/parent-tasks/` 创建顶层任务
- **启动云枢**：`yunshu_io.run_yunshu_session(parent_id, conv_id, user_msg, agent_profile)`
- **进程池管理**：`ThreadPoolExecutor(max_workers=20)` 最多并发 20 个消息
- **队列积压保护**：`QUEUE_BACKLOG_WARN=100`，超 5 倍直接跳过防止雪崩
- **五维监控 + 僵尸保护**（见 2.4）

### 2.3 云枢 Yunshu（管脑）—— 调度决策与任务分解

**核心文件**：`agents/yunshu_io.py`

YunshuCommandHandler 是调度的"大脑"，负责：

- **协议解析**：拦截 Hermes 输出中的 10 个 v4 命令
- **PLAN 规划**：调用 `PlanGraph.parse()` 解析任务依赖图
- **SPAWN 派发**：调用 `subprocess.Popen(["hermes", "chat", "-q", ...])` 启动子Agent
- **状态追踪**：维护 `self.children` 字典，跟踪所有子进程状态
- **结果聚合**：`wait_all()` 等待所有子任务完成，聚合输出
- **REFLECT 自检**：调用 ReflectState 状态机执行 5 项自检清单
- **REPLY 回复**：将最终结果写回 API
- **护栏控制**：`_guard_spawn()` 限制并发子任务数（默认3，最大8）

**调度流程**（`run_yunshu_session`，最多 15 轮）：

```
第1轮: 云枢启动 → 分析用户消息
第2轮: 输出 PLAN 声明计划 → Worker 解析依赖图
第3轮: SPAWN_BANNI / SPAWN_BASIR → Worker fork 子进程
第4轮: WAIT_ALL → Worker 阻塞等待所有子任务
第5轮: REFLECT → 进入自检模式
第6轮: REFLECT_PASS 或 REFLECT_FAIL → 通过则 REPLY
```

> 关键设计：云枢每轮最多调用一次 `hermes chat -q`，Hermes 的输出被 Worker 逐行拦截解析。非命令行（自然语言）被当作"自言自语"忽略，不加入响应上下文。如果整轮都没有匹配到任何命令，Worker 直接把整段输出当作 REPLY 处理——这是一个巧妙的兜底机制。

### 2.4 五维监控与僵尸保护（`_child_guard`）

**核心文件**：`agents/redis_worker.py` 第 58-122 行

这是 Worker（管命）最精密的部分，每个子进程都被包装在 `_child_guard()` 中：

| 维度 | 实现方式 | 阈值 | 动作 |
|------|---------|------|------|
| **心跳** | `threading.Thread` 每 10s 调用 `POST /api/child-tasks/{id}/heartbeat/` | `CHILD_HEARTBEAT_MAX_GAP=120s` | 标记僵尸 |
| **内存监控** | `psutil.Process(proc.pid).memory_info().rss` | `CHILD_MEMORY_LIMIT_MB=4096` | terminate → kill |
| **超时** | `proc.communicate(timeout=CHILD_TIMEOUT)` | `CHILD_TIMEOUT=300s` | kill + 标记 TIMED_OUT |
| **输出停滞** | `CHILD_STALL_SECONDS=180` | 3分钟无输出 | 标记异常 |
| **进度事件** | `CHILD_MAX_PROGRESS=1000` | 单子任务最大进度事件 | 防止日志爆炸 |

---

## 3. v4 文本协议

v4 文本协议是云枢与 Hermes 之间的**通信契约**。云枢通过 Hermes stdout 输出的命令文本来解析意图，而非 API 调用。

### 3.1 10 命令全量

**核心文件**：`agents/yunshu_io.py` 第 16-29 行的 `CMD_PATTERNS`

| 命令 | 正则模式 | 用途 | v4 新增 |
|------|---------|------|--------|
| `SPAWN_BANNI` | `^SPAWN_BANNI\s*:?\s*(.+)` | 派发任务给 Banni（搜索/工程） | 否 |
| `SPAWN_BASIR` | `^SPAWN_BASIR\s*:?\s*(.+)` | 派发任务给 Basir（分析/推理） | 否 |
| `CHECK` | `^CHECK\s+(\S+)` | 查询子任务状态 | 否 |
| `WAIT_ALL` | `^WAIT_ALL$` | 阻塞等待所有子任务完成 | 否 |
| `KILL` | `^KILL\s+(\S+)` | 强制终止子任务 | 否 |
| `REPLY` | `^REPLY\s*:?\s*(.+)` | 输出最终回复（Markdown） | 否 |
| `PLAN` | `^PLAN\s*:?\s*(.*)` | 声明任务计划（多行收集直到下一个命令） | **是** |
| `REFLECT` | `^REFLECT\s*$` | 进入自检模式 | **是** |
| `REFLECT_PASS` | `^REFLECT_PASS` | 自检通过 | **是** |
| `REFLECT_FAIL` | `^REFLECT_FAIL\s*:?\s*(.+)` | 自检未通过 + 修正行动 | **是** |

### 3.2 PLAN 多行收集机制

```python
# yunshu_io.py 第 322-329 行
if in_plan:
    if line.startswith(("SPAWN_", "REPLY:", "WAIT_ALL", "REFLECT", "CHECK", "KILL")):
        in_plan = False
        response_lines.append(handler.handle_plan("\n".join(plan_lines)))
        plan_lines = []
    else:
        plan_lines.append(line)
        continue
```

PLAN 是一个**多行命令**：遇到 `PLAN:` 开始收集所有后续行，直到遇到下一个命令关键字（SPAWN_、REPLY:、WAIT_ALL 等）或轮次结束。这个设计使得云枢可以在 PLAN 中自由输出 YAML-like 格式的任务依赖图。

### 3.3 完整流程命令序列（来自测试）

```python
# tests/test_v4_core.py TestEndToEndSimulation
commands = [
    "PLAN:\ncomplexity: medium\ntasks:\n  - id: t1, agent: banni, desc: x, deps: []",
    "SPAWN_BANNI: 搜索 X",
    "WAIT_ALL",
    "REFLECT",
    "REFLECT_PASS",
    "REPLY: ## 结果\n\n分析完成",
]
```

修正流程（REFLECT_FAIL 触发重搜）：
```python
commands = [
    "SPAWN_BANNI: 搜索 lerder&works",
    "WAIT_ALL",
    # 发现拼写错误 → REFLECT_FAIL 触发修正
    "SPAWN_BANNI: 搜索 Leader & Workers",
    "WAIT_ALL",
    "REPLY: ## lerder&works 分析\n\n...",
]
```

---

## 4. 通信机制

### 4.1 yunshu_io.py 的协议处理

**核心文件**：`agents/yunshu_io.py`（450 行）

`run_yunshu_session()` 是通信的核心入口，流程：

1. **构建上下文**：`system_prompt` + 用户消息 → 传给 `hermes chat -q`
2. **主循环**（最多 15 轮）：
   - 调用 `_hermes_q(context, agent_profile)` → 调用 `subprocess.run(["hermes", "chat", "-q", ...])`
   - 逐行解析 Hermes stdout 输出
   - 对每一行：遍历 `CMD_PATTERNS` 匹配命令
   - 匹配到命令 → 调用 `YunshuCommandHandler` 的对应方法
   - 未匹配 → 忽略（云枢"自言自语"）
3. **上下文更新**：每轮结束后根据结果构建新 context
   - 如果有 OK 响应 → 自动执行 `wait_all()` 获取子任务结果
   - 否则 → 将错误信息传入下一轮
4. **兜底退出**：
   - `REPLY` 命令 → 直接返回
   - 整轮无命令 → 整段当 REPLY
   - 达到 15 轮 → `_fallback_reply()`

**关键设计决策**：

- **`hermes chat -q` 是短连接**：每轮都是独立的 `subprocess.run`，而非持久进程。这意味着每轮云枢都需要重新加载 context。
- **context 由 Worker 自行构建**：不是 Hermes profile memory 的形式，而是 Worker 拼接 `system_prompt + "\n\n子任务结果：\n" + aggregated`。
- **session_id 前缀剥离**：`_hermes_q()` 和 `check()` 方法都处理了 Hermes 输出中 `session_id:` 前缀（第 406-407 行）。

### 4.2 agent_registry.py 的 Agent 注册机制

**核心文件**：`agents/agent_registry.py`（61 行）

采用 **Python dict 静态注册** 模式（非动态发现/数据库驱动）：

```python
AGENT_REGISTRY = {
    "banni": {
        "name": "Banni",
        "role_prompt": "你是 Banni，工程执行 Agent。\n擅长：搜索查询、信息采集、代码编写、文件操作。...",
        "default_timeout": 1800,           # 30分钟超时
        "capabilities": ["search", "code_gen", "web_fetch", "file_ops"],
        "output_format": "raw_text",
    },
    "basir": {
        "name": "Basir",
        "role_prompt": "你是 Basir，数据分析 Agent。\n擅长：概念推断、逻辑推理、报告生成、数据分析。...",
        "default_timeout": 1800,
        "capabilities": ["analysis", "inference", "report_gen", "reasoning"],
        "output_format": "raw_text",
    },
}
```

**注册接口**：

| 函数 | 用途 |
|------|------|
| `get_agent_config(name)` | 获取 Agent 完整配置 |
| `register_agent(name, config)` | 动态注册新 Agent（运行时） |
| `list_agents()` | 列出所有已注册 Agent |
| `get_role_prompt(name)` | 获取角色提示词（用于 SPAWN 时注入） |
| `get_default_timeout(name)` | 获取超时配置（不存在返回 300s） |

**角色提示词注入流程**：

```
yunshu_io.spawn("banni", prompt)
  → get_role_prompt("banni")   # 从 AGENT_REGISTRY 取 prompt
  → subprocess.Popen(["hermes", "chat", "-q",
       f"<system_instruction>{role_prompt}</system_instruction>\n{prompt}",
       "-p", "banni", "-Q", "--yolo"])
```

> 注意：角色提示词是通过消息前缀 `<system_instruction>` XML 标签注入的，而非通过 Hermes 的 `--system` 参数（该参数不被支持）。子 Agent 的 profile 始终是 `-p banni` 或 `-p basir`。

### 4.3 通信协议对比

项目中有 **两套通信机制** 并行运行：

| 维度 | yunshu_io（文本协议） | orchestrator.py（API 工具调用） |
|------|---------------------|-------------------------------|
| 入口 | `run_yunshu_session()` | `orchestrate()` |
| LLM 调用 | `hermes chat -q`（子进程） | DeepSeek API 直调 |
| 协议 | stdout 文本命令匹配 | OpenAI 兼容 tool_calls |
| 子 Agent | `subprocess.Popen` fork | Python 本地执行 |
| 适用场景 | 多 Agent 协作（父任务→子Agent） | 纯执行/Tool-Use（单 Agent） |
| 守护进程 | redis_worker.py | orchestrator_daemon.py |

---

## 5. 任务调度

### 5.1 orchestrator.py —— 编排引擎 v2

**核心文件**：`agents/orchestrator.py`（768 行）

设计原则（2026-06-22 重写）：
- LLM 只调一次 → 生成完整可执行计划
- Python 本地执行所有步骤（不调 LLM）
- 步骤失败 → 先查 `pitfall_memory` → 没有再调 LLM
- 自动学习：每次 LLM 修复成功 → 写入 `pitfall_memory`

#### 5.1.1 `orchestrate()` — Hermes 风格探索模式

与 `yunshu_io` 不同，这是**纯工具调用模式**，不经过文本协议：

```
orchestrate(user_message, conversation_id, history)
  → 最多 10 轮探索
  → 每轮: DeepSeek API (含 tool_calls) → 本地执行工具
  → 每轮推一条系统消息到对话（实时进度节点）
  → 支持 Redis 停止/暂停信号
  → 10 轮后强制收尾
```

**Redis 信号控制**：
- `orch:stop:{conv_id}` → 用户手动停止
- `orch:pause:{conv_id}` → 用户手动暂停
- `orch:state:{conv_id}` → 当前状态 (running/paused/stopped/idle)

#### 5.1.2 `generate_plan()` + `execute_plan()` — 两阶段执行

```
Phase 1: generate_plan() — LLM 探索生成 [PLAN]...[/PLAN]
  → 最多 5 轮探索
  → 工具调用: terminal | read_file | search | write_file
  → 解析 YAML-like 格式: summary + steps[id, action, command, depends_on]

Phase 2: execute_plan() — Python 纯本地执行
  → 拓扑排序解析依赖
  → ThreadPoolExecutor(max_workers=3) 并行执行无依赖步骤
  → 每步: terminal | read_file | write_file | search | reason
  → 失败修复链路: pitfall_memory → LLM 修复 → 写入记忆
```

#### 5.1.3 五大执行器

| 执行器 | 安全限制 |
|--------|---------|
| `_exec_terminal()` | 拦截 `rm -rf`、`sudo`、`mkfs`、`dd if=`、fork bomb |
| `_exec_read_file()` | 仅绝对路径，最多 200 行 |
| `_exec_write_file()` | 限制写入 `/home/jiangli/` 子目录 |
| `_exec_search()` | find 排除 node_modules/.git/venv/__pycache__ |
| `_exec_reason()` | 仅一次 LLM 调用，200 字以内 |

### 5.2 plan_parser.py — PLAN 依赖图解析器

**核心文件**：`agents/plan_parser.py`（109 行）

```python
@dataclass
class PlanGraph:
    complexity: str = "medium"      # simple|medium|complex
    nodes: list = []                 # PlanNode 列表
    adjacency: dict = {}             # {task_id: [dep_ids]}
    parallel_count: int = 0          # 无依赖节点数
    serial_count: int = 0            # 有依赖节点数
```

**核心方法**：

| 方法 | 功能 |
|------|------|
| `PlanGraph.parse(text)` | 从云枢 PLAN 输出解析（正则宽松匹配，容错） |
| `get_suggested_max_spawn()` | 根据 complexity 返回护栏上限：simple=1, medium=3, complex=5 |
| `validate()` | 验证无环 + 所有 task_id 唯一 + 依赖指向有效 task_id |
| `get_parallel_groups()` | 拓扑排序返回并行执行组 |

**解析格式**（YAML-like）：
```yaml
complexity: medium
tasks:
  - id: t1, agent: banni, desc: 搜索 Leader & Workers, deps: []
  - id: t2, agent: basir, desc: 分析架构模式, deps: [t1]
  - id: t3, agent: banni, desc: 生成报告, deps: [t2]
```

**容错设计**：
- complexity 缺失 → 默认 medium
- tasks 块缺失 → 返回 None
- 依赖 `deps` 可选 → 默认空列表

### 5.3 checkpoint.py — 检查点持久化

**核心文件**：`agents/checkpoint.py`（94 行）

```python
class CheckpointManager:
    def write_checkpoint(stage, children_state, yunshu_line=0, summary_text="")
    def load_latest() -> dict | None
    def build_recovery_context(checkpoint) -> str
```

**双写策略**：
1. **文件系统**：`~/projects/agent-platform/checkpoints/checkpoint_{1,2,3}.json`，循环覆盖（最多 3 个文件）。
2. **数据库**：`POST /api/checkpoints/`，同步写 DB。

**关键设计**：
- `threading.Lock()` 保护并发写安全
- `load_latest()` 从 DB 查询（而非文件），带 `?latest=1` 参数
- `build_recovery_context()` 区分已完成任务（DONE/FAILED/TIMED_OUT）和待执行任务（PENDING/RUNNING）

### 5.4 pitfall_memory.py — 踩坑学习系统

**核心文件**：`agents/pitfall_memory.py`（194 行）

```
异常 → search_pitfall(error_text, context)
  ├─ 命中 → apply_fix(entry) → 自动修复（不调 LLM）
  └─ 未命中 → LLM 生成修复方案 → record_pitfall() → 写入记忆
```

**存储格式**（`~/.hermes/profiles/Banni/pitfall_memory.json`）：
```json
{
  "version": 1,
  "entries": [{
    "id": "pit_001",
    "pattern": ["错误关键词或正则"],
    "context": "什么场景下出现",
    "fix_type": "command_fix|retry|skip|replace|ask_user",
    "fix_detail": "具体修复指令",
    "hit_count": 3,
    "last_hit": "ISO时间"
  }]
}
```

**fix_type 五种策略**：
- `command_fix`：执行修复命令 → 验证 exit code
- `retry`：重试原步骤
- `skip`：跳过此步骤
- `replace`：替换步骤内容
- `ask_user`：抛给用户

---

## 6. Worker 层

### 6.1 三个 Worker 实现对比

| 维度 | redis_worker.py (v7.0) | worker.py (v2) | rq_worker.py |
|------|----------------------|----------------|-------------|
| **行数** | 247 行 | 217 行 | 124 行 |
| **运行状态** | ✅ 生产运行（systemd） | ⚠️ 旧版本 | ⚠️ 旧版本 |
| **消息队列** | Redis BRPOP | 无队列（HTTP pull） | RQ (Redis Queue) |
| **LLM 调用** | `hermes chat -q`（子进程） | DeepSeek API 直调 | Anthropic→DeepSeek Proxy |
| **Agent 路由** | 文本协议 + 云枢调度 | 单 Agent 文本回复 | 单 Agent 文本回复 |
| **并发模型** | ThreadPoolExecutor(max=20) | ThreadPoolExecutor(max=3) | RQ Worker 进程模型 |
| **子进程管理** | `_child_guard` 五维监控 | 无 | 无 |
| **多 Agent 协同** | ✅ 云枢 → SPAWN Banni/Basir | ❌ 单 Agent | ❌ 单 Agent |

### 6.2 redis_worker.py v7.0 主循环

```python
# 第 205-247 行
with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:  # MAX_WORKERS=20
    futures = {}
    while True:
        # 1. 清理已完成的 future
        done = [f for f in futures if f.done()]
        for f in done:
            mid, _ = futures.pop(f)

        # 2. 检查队列积压
        qlen = r.llen(QUEUE_KEY)
        if qlen > QUEUE_BACKLOG_WARN:  # > 100
            print(f"[Worker] 积压: {qlen}")

        # 3. BRPOP 阻塞拉取
        result = r.brpop(QUEUE_KEY, timeout=5)
        if result:
            _, raw = result
            mid = int(raw)
            # 严重积压保护
            if qlen > QUEUE_BACKLOG_WARN * 5:
                print(f"[Worker] 严重积压 跳过")
                continue
            # 提交到线程池
            future = pool.submit(process_message, mid)
            futures[future] = (mid, time.time())
```

### 6.3 worker.py — 事件驱动直调模式

直接调用 DeepSeek API（OpenAI 兼容格式），不经过 Hermes 引擎：

```python
def process_message(msg_id, conversation_id, content, ...):
    messages = [{"role": "system", "content": SYSTEM_PROMPT_DEFAULT}]
    messages.append({"role": "user", "content": content})
    reply = _call_deepseek(messages, sp, used_model)
    _save_reply(conversation_id, reply)
    _mark_processed([msg_id])
```

**关键特性**：
- `_get_system_prompt()` 从消息的 `agent_portrait` 字段构建系统提示
- 支持跨模型选择（`agent_model` 字段）
- 飞书消息通过 `relay_feishu.py` 子进程回传
- 日志写入 `/tmp/worker.log`

### 6.4 rq_worker.py — RQ 队列模式

```python
# 使用 RQ (Redis Queue) 库管理作业
redis_conn = Redis.from_url(REDIS_URL)
queue = Queue("messages", connection=redis_conn)
worker = Worker([queue], connection=redis_conn)
worker.work()
```

通过 Anthropic→DeepSeek 代理（`localhost:4000/v1/messages`）调用 LLM，而非直接调 DeepSeek。

---

## 7. 安全架构

### 7.1 crypto_utils.py — AES-256-GCM 配置加密

**核心文件**：`agents/crypto_utils.py`（52 行）

```python
# 密钥派生
seed = os.environ.get('AGENT_CONFIG_KEY', 'agent-platform-secret-key-v1-32b')
key = hashlib.sha256(seed.encode()).digest()  # 32字节 AES-256

# 加密流程
aesgcm = AESGCM(key)
nonce = os.urandom(12)  # 96-bit 随机 nonce
ciphertext = aesgcm.encrypt(nonce, plaintext, None)
return base64.b64encode(nonce + ciphertext)

# 解密流程
raw = base64.b64decode(encrypted)
nonce, ciphertext = raw[:12], raw[12:]
plaintext = aesgcm.decrypt(nonce, ciphertext, None)
```

**安全特性**：
- AES-256-GCM：认证加密（同时提供机密性和完整性）
- 随机 nonce：每次加密使用不同 nonce，防止重放
- 密钥从环境变量派生：`AGENT_CONFIG_KEY`，有 fallback 但生产环境必须设置
- `mask_value()` / `mask_config()`：脱敏工具，只显示首尾 N 字符

### 7.2 auth.py — HMAC-SHA256 签名认证

**核心文件**：`agents/auth.py`（113 行）

```
Agent 请求流程：
  1. 请求体 + agent.secret_key → HMAC-SHA256 → 签名
  2. Header: X-Agent-Id + X-Signature + X-Timestamp
  3. 平台收到 → 用 agent.secret_key 重新计算签名
  4. hmac.compare_digest() 常数时间比对 → 防时序攻击
  5. 比对一致 → 放行；不一致 → 403
```

**防重放**：`X-Timestamp` 与服务器时间差超过 5 分钟（`MAX_TIME_SKEW=300`）则拒绝。

**三阶段认证**：
```python
def authenticate(self, request):
    # 1. 注册端点跳过（Agent 还没有 secret_key）
    if request.path.endswith('/register/'):
        return None

    # 2. 没有 HMAC 头 → 允许未认证访问（管理 API）
    if not agent_id and not signature:
        return None  # Django Session Auth 接管

    # 3. 有 HMAC 头 → 严格验证
    agent = Agent.objects.get(id=agent_id)
    expected = self._sign(agent.secret_key, body)
    if not hmac.compare_digest(expected, signature):
        raise AuthenticationFailed('HMAC 签名验证失败')
```

**Agent 专用端点保护**（`AgentEndpointPermission`）：
- `heartbeat`、`pull_tasks` → 必须有 request.agent（HMAC 验证通过后设置）
- CRUD 端点 → 允许未认证访问

### 7.3 环境变量密钥管理

`settings.py` 第 9 行：
```python
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-change-me-in-production')
```

环境变量设计：
- `DEEPSEEK_API_KEY` → `~/.hermes/profiles/Banni/.env`（worker.py 加载）
- `DJANGO_SECRET_KEY` → systemd `Environment=` 指令
- `AGENT_CONFIG_KEY` → AES 加密密钥派生种子
- `REDIS_URL` → 默认 `redis://localhost:6379/0`

> 关键设计：所有敏感 key 统一通过 systemd `Environment=` 或 `.env` 文件管理，代码中**不硬编码任何密钥**，不读取明文配置文件。

### 7.4 执行安全网

| 层级 | 文件 | 机制 |
|------|------|------|
| **命令黑名单** | `orchestrator.py` | `DANGEROUS = ["rm -rf", "sudo", "mkfs", "dd if=", ":(){", "> /dev/sd"]` |
| **路径限制** | `orchestrator.py` | `_exec_write_file` 限制只能写 `/home/jiangli/` 子目录 |
| **子进程超时** | `yunshu_io.py` | `_timeout_killer` daemon 线程，超时自动 kill |
| **内存硬限制** | `redis_worker.py` | `CHILD_MEMORY_LIMIT_MB=4096`，超限 terminate → kill |
| **Spawn 护栏** | `yunshu_io.py` | `_max_spawn=3`（动态上限），`_absolute_max=8`（硬上限） |

---

## 8. 容错设计

### 8.1 REFLECT 自检状态机

**核心文件**：`agents/yunshu_io.py` 第 32-83 行 `ReflectState`

```
                 ┌──────────────────┐
    enter() ──▶  │   REFLECT 活跃    │
                 └──────┬───────┬───┘
                        │       │
                 mark_pass()  mark_fail(reason)
                        │       │
                        ▼       ▼
                  passed=True  current_round += 1
                  退出活跃      │
                               ├─ round < 3 → 返回 "FAIL"（继续重试）
                               └─ round >= 3 → 返回 "FORCE_PASS"（熔断）
```

**5 项自检清单**（`get_checklist_prompt` 第 59-84 行）：

1. 事实是否有子Agent输出支撑？
2. 修正是否完成？
3. 是否遗漏用户需求？
4. 结构是否完整？
5. 是否有可操作建议？

**关键设计**：
- `MAX_ROUNDS = 3`：最多 3 轮修正，避免无限循环
- `FORCE_PASS`：3 轮后强制通过，防止系统僵死
- 自检 prompt 动态生成：注入子任务结果摘要 + 用户原始需求

### 8.2 多级熔断

| 层级 | 机制 | 阈值 |
|------|------|------|
| **Spawn 护栏** | `_guard_spawn()` 限制并发子任务 | 动态（PLAN 设定）~ 8 硬上限 |
| **REFLECT 熔断** | 3 轮失败 → FORCE_PASS | 3 轮 |
| **轮次上限** | `run_yunshu_session` 最多 15 轮 | 15 轮 |
| **探索上限** | `orchestrate` 最多 10 轮 | 10 轮 |
| **队列积压熔断** | 超过 `QUEUE_BACKLOG_WARN * 5` 条直接跳过 | 500 条 |
| **LLM 修复次数** | `MAX_RECOVERY_LLM_CALLS` | 2 次 |

### 8.3 超时链路

```
子进程级:
  yunshu_io.spawn() → _timeout_killer daemon 线程
    → time.sleep(timeout) → proc.kill()
    → timeout 来自 agent_registry: banni=1800s, basir=1800s, default=300s

子进程级 (v2):
  redis_worker._child_guard()
    → proc.communicate(timeout=CHILD_TIMEOUT)  # 300s
    → TimeoutExpired → proc.kill() → 标记 TIMED_OUT

LLM 调用级:
  orchestrator._call_llm_api() → requests timeout=60
  worker._call_deepseek() → requests timeout=60

等待级:
  yunshu_io.wait_all() → deadline = time.time() + 600  # 10分钟
  subprocess.run(["hermes", ...]) → timeout=300  # _hermes_q
```

### 8.4 检查点与恢复

**写检查点触发时机**（`yunshu_io.py`）：
- `handle_plan()` → `PLAN_COMPLETED`
- `spawn()` → `EXECUTING`
- `check()` → `EXECUTING`（每次查询状态时更新）
- `handle_reflect_pass()` → `REFLECT_PASSED`

**恢复机制**：
```python
checkpoint = manager.load_latest()
if checkpoint:
    recovery_context = manager.build_recovery_context(checkpoint)
    # → "[恢复上下文]\n父任务 #42 从 EXECUTING 恢复\n已完成: t1(DONE)\n待执行: t2, t3"
```

**循环覆盖策略**（防止磁盘写满）：
```
写 checkpoint_3.json → 重命名 checkpoint_3→checkpoint_2→checkpoint_1
最多保留 3 个文件
```

### 8.5 兜底机制

| 场景 | 兜底行为 | 代码位置 |
|------|---------|---------|
| 整轮无命令 | 整段当 REPLY | `yunshu_io.py:377` |
| 15 轮耗尽 | `_fallback_reply()` → "系统在处理您的请求时遇到问题" | `yunshu_io.py:394` |
| LLM 调用失败 | 返回空字符串（下一轮重试） | `yunshu_io.py:398-412` |
| 子任务创建失败 | 返回 ERROR 字符串 | `yunshu_io.py:162` |
| PLAN 解析失败 | 返回 ERROR 字符串 | `yunshu_io.py:110` |
| API 不可达 | 异常静默（不影响主流程） | 各处 `except: pass` |

---

## 9. 数据模型

**核心文件**：`agents/models.py`（713 行，7 张核心表）

### 9.1 核心 ER 关系

```
Agent 1──N Conversation
Agent 1──N Task
Agent M──N Skill (via agent_skill_assignments)
Agent M──N CapabilityTag (via agents_capabilities)
Conversation 1──N Message
Task 1──N ExecutionLog
Task 1──N SubTask (parent_task_id 自引用)
CronJob 1──N CronExecution
```

### 9.2 关键模型字段

**Agent 表**（agents，3 行）：
```python
name, feishu_app_id, webhook_url, portrait(人设), status(online/offline/busy/error),
last_heartbeat, secret_key(HMAC密钥), version,
config_public(JSON: 公开配置), config_encrypted(AES加密敏感配置)
```

**Task 表**（tasks，77 行）：
```python
title, description, status(pending/in_progress/completed/failed/cancelled),
priority(high/medium/low),
contract(JSON: 任务合同/orchestrator标记/plan_id/step_id/depends_on),
result, agent_id(FK), parent_task_id(FK自引用), deadline
```

**Message 表**（messages，170 行）：
```python
conversation_id(FK), role(user/agent/system), content,
source(web/feishu), processed(Worker标记), metadata(JSON: orch事件)
```

---

## 10. 组件关系拓扑图

```
┌────────────────────────────────────────────────────────────────────┐
│                         入口层                                      │
│  Web Chat (:5174)    飞书消息     REST API                         │
└─────────────────────────┬──────────────────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────────────────┐
│                    Django REST API (:8001)                          │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌──────────────┐     │
│  │ Message  │  │   Task    │  │  Agent   │  │ Conversation │     │
│  │ ViewSet  │  │  ViewSet  │  │ ViewSet  │  │   ViewSet    │     │
│  └────┬─────┘  └─────┬─────┘  └────┬─────┘  └──────┬───────┘     │
│       │              │             │               │              │
│  ┌────▼─────┐        │        ┌────▼─────┐   ┌─────▼──────┐      │
│  │ SQLite   │        │        │  HMAC    │   │  Session   │      │
│  │          │        │        │  Auth    │   │  Auth      │      │
│  └────┬─────┘        │        └──────────┘   └────────────┘      │
│       │              │                                            │
│  ┌────▼─────┐   ┌────▼─────────────────────────────────┐         │
│  │  Redis   │   │           Task Polling                │         │
│  │ LPUSH    │   │    orchestrator_daemon.py (每30s)     │         │
│  └────┬─────┘   └────┬─────────────────────────────────┘         │
└───────┼──────────────┼───────────────────────────────────────────┘
        │              │
        ▼              ▼
┌───────────────────────────────────────────────────────────────────┐
│                     Worker 层 (并行运行)                            │
│                                                                    │
│  ┌───────────────────────┐    ┌─────────────────────────────┐     │
│  │   redis_worker.py v7  │    │    orchestrator.py v2        │     │
│  │   (agent-worker)      │    │    (orch-daemon)             │     │
│  │                       │    │                              │     │
│  │  BRPOP msg_queue      │    │  poll_and_execute()          │     │
│  │    ↓                  │    │    ↓                         │     │
│  │  run_yunshu_session() │    │  orchestrate()               │     │
│  │    ↓                  │    │    ↓                         │     │
│  │  ┌─ yunshu_io.py ───┐│    │  _call_llm_api() + tools     │     │
│  │  │ 文本协议引擎:     ││    │    ↓                         │     │
│  │  │ PLAN → SPAWN     ││    │  本地执行: terminal/read/     │     │
│  │  │ → WAIT → REFLECT ││    │  write/search/reason          │     │
│  │  │ → REPLY          ││    │    ↓                         │     │
│  │  └──────────────────┘│    │  失败修复: pitfall_memory     │     │
│  │    ↓                  │    │                              │     │
│  │  subprocess.Popen     │    │                              │     │
│  │  hermes chat -q       │    │                              │     │
│  │  -p banni / -p basir  │    │                              │     │
│  └───────────────────────┘    └─────────────────────────────┘     │
│                                                                    │
│  ┌───────────────────────┐    ┌─────────────────────────────┐     │
│  │  _child_guard()       │    │  依赖组件:                   │     │
│  │  五维监控:             │    │  ├─ plan_parser.py          │     │
│  │  ├─ 心跳 (10s)        │    │  ├─ checkpoint.py           │     │
│  │  ├─ 内存 (<4GB)       │    │  ├─ agent_registry.py       │     │
│  │  ├─ 超时 (300s)       │    │  ├─ pitfall_memory.py       │     │
│  │  ├─ 停滞检测 (180s)   │    │  ├─ crypto_utils.py         │     │
│  │  └─ 进度事件 (≤1000)  │    │  └─ auth.py                 │     │
│  └───────────────────────┘    └─────────────────────────────┘     │
└───────────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────────┐
│                     Hermes 原生引擎                                 │
│  hermes chat -q -p <profile> -Q --yolo (600s 超时)                │
│  ├─ Profile Memory (USER.md + MEMORY.md)                          │
│  ├─ Skills (hermes_agent_prompt.md)                                │
│  └─ 25+ 内置工具: terminal/read_file/write_file/search_files/     │
│     browser/web_search/delegate_task/skill_view/feishu/...        │
└───────────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────────┐
│                         输出层                                      │
│  POST /api/messages/ (保存回复, processed=True)                    │
│  POST /api/messages/mark-processed/ (批量标记已处理)               │
│  relay_feishu.py (飞书消息回传)                                    │
└───────────────────────────────────────────────────────────────────┘
```

---

## 附录 A：关键文件清单

| 文件 | 行数 | 职责 |
|------|------|------|
| `agents/yunshu_io.py` | 450 | v4 文本协议引擎 + 云枢 I/O 主循环 |
| `agents/orchestrator.py` | 768 | 编排引擎 v2（工具调用模式） |
| `agents/redis_worker.py` | 247 | Worker v7.0（生产运行中） |
| `agents/worker.py` | 217 | Worker v2（直调 DeepSeek） |
| `agents/rq_worker.py` | 124 | Worker v1（RQ 队列） |
| `agents/plan_parser.py` | 109 | PLAN 依赖图解析器 |
| `agents/checkpoint.py` | 94 | 检查点持久化 + 崩溃恢复 |
| `agents/agent_registry.py` | 61 | Agent 角色注册表 |
| `agents/pitfall_memory.py` | 194 | 踩坑学习系统 |
| `agents/crypto_utils.py` | 52 | AES-256-GCM 配置加密 |
| `agents/auth.py` | 113 | HMAC-SHA256 签名认证 |
| `agents/models.py` | 713 | 7 张核心数据表 |
| `orchestrator_daemon.py` | 89 | 编排守护进程 |
| `orchestrator_runner.py` | 188 | Task 依赖链执行器 |
| `monitor_tasks.py` | 40 | 任务监控（每 5s 轮询） |
| `tests/test_v4_core.py` | 442 | v4 核心逻辑测试（6 类 29 用例） |

## 附录 B：设计亮点与局限性

### 亮点

1. **三权分立清晰**：Worker（进程管理）、云枢（调度决策）、Banni/Basir（执行）职责分明，互不越界
2. **文本协议解耦**：云枢与 Hermes 通过 stdout 纯文本通信，无需修改 Hermes 源码
3. **多级熔断**：Spawn 护栏 → REFLECT 3 轮 → 轮次上限 → 队列积压，层层保护
4. **坑位记忆自进化**：不需要再训练的异常学习，纯本地模式匹配
5. **安全纵深**：HMAC 认证 + AES-GCM 加密 + 命令黑名单 + 路径白名单
6. **五维监控**：心跳 + 内存 + 超时 + 停滞 + 进度事件，覆盖子进程全生命周期

### 局限性

1. **两套调度引擎并行**：`yunshu_io` 和 `orchestrator` 有功能重叠，缺乏统一调度器
2. **Agent 注册表静态化**：`AGENT_REGISTRY` 是 Python dict，新增 Agent 需改代码重启
3. **HERMES 短连接开销**：每轮都是独立 `subprocess.run`，15 轮意味着云枢上下文被重建 15 次
4. **角色注入不完美**：通过消息前缀 `<system_instruction>` 注入 role_prompt，而非 profile 级隔离
5. **错误处理粗暴**：多处 `except: pass` 吞掉异常，问题排查困难
6. **无分布式支持**：依赖本地 subprocess、本地 Redis、本地文件系统，无法跨机器扩展
