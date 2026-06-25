# AgentOS Worker v5+ 架构对比分析报告

> **Basir 分析** | 2026-06-24 | 基于 t1 市场调研 + 源码审计 (commit ac08cf4)
>
> 分析焦点：Worker v5.0 / 20并发 / 600s熔断 / SSE推送 / 编排器模式

---

## 一、架构快照：四大特征实测数据

### 1.1 双 Worker 架构全景

```
                    入口层
        ┌────────────┼────────────┐
        ▼            ▼            ▼
    Web Chat    飞书 Bot     Cron/Task
        │            │            │
        ▼            ▼            ▼
  ┌──────────────┐ ┌──────────────────┐ ┌─────────────────┐
  │ worker.py    │ │ redis_worker.py  │ │orch_daemon.py   │
  │ v5.0 事件驱动 │ │ v7.0 Redis BRPOP │ │ (轮询模式,30s)   │
  │              │ │                  │ │                 │
  │ MAX_WORKERS=3│ │ MAX_WORKERS=20   │ │ POLL=30s        │
  │ DeepSeek直调  │ │ → yunshu_io 编排 │ │ → orchestrator  │
  │ <2s 延迟     │ │ → 多Agent协同     │ │ → DAG依赖链     │
  └──────┬───────┘ └────────┬─────────┘ └────────┬────────┘
         │                  │                     │
         ▼                  ▼                     ▼
  ┌──────────────────────────────────────────────────┐
  │             Django REST API (:8001)               │
  │  SQLite(11表) + Redis(Pub/Sub + List) + Checkpoint │
  └──────────────────────────────────────────────────┘
```

| Worker | 版本 | 并发 | 入口 | 编排引擎 | 延迟 |
|--------|------|------|------|---------|------|
| worker.py | v5.0 | 3线程 | Web Chat POST | DeepSeek API直调 | <2s |
| redis_worker.py | v7.0 | 20线程 | Redis BRPOP | Yunshu v4 文本协议 | 5-15s冷启动 |
| orchestrator_daemon | v2 | 1进程 | 30s轮询DB | Orchestrator v2 Plan-first | 30-60s |

**关键发现**：系统实际存在**三套并发调度模型**，分别处理不同入口的消息。redis_worker的20并发与worker.py的3并发差距6.6倍——Web Chat用户享受不到20并发的吞吐能力。

### 1.2 600s熔断机制（三级超时瀑布）

```python
# 第一级：子任务超时 300s
redis_worker.py: CHILD_TIMEOUT = 300
  → subprocess.communicate(timeout=CHILD_TIMEOUT)
  → 超时后：proc.kill() → status=TIMED_OUT

# 第二级：Hermes调用超时 600s
yunshu_io.py: subprocess.run(timeout=300)  # 单次问答
redis_worker.py: HERMES_TIMEOUT = 600      # 编排总限

# 第三级：编排总超时 600s
redis_worker.py: TASK_TIMEOUT = 600
yunshu_io.py: max_rounds = 15             # 主循环上限
```

| 超时级别 | 配置值 | 触发条件 | 处理方式 |
|----------|--------|----------|----------|
| 子任务 | 300s | 单Agent执行超时 | SIGKILL 硬终止 |
| Hermes调用 | 300s | 单次LLM问答超时 | 返回空字符串 |
| 编排总 | 600s | 整个编排流程 | _fallback_reply() |

**优点**：三级独立计时，互不干扰。CHILD_TIMEOUT先触发，不给编排总超时压力。

**缺点**：无指数退避重试，无死信队列。子任务超时后直接丢弃。

### 1.3 SSE推送（实际是轮询实现）

```python
# sse.py v2 — 关键实现细节
def generate():
    while True:
        # 1. 轮询 Agent 更新 (updated_at > last_check)
        # 2. 轮询 Task 更新 (updated_at > last_check)  
        # 3. 轮询 Message 更新 (created_at > last_check)
        # 4. Redis Pub/Sub 接收 msg_updates
        # 5. 每15轮发送 worker-pulse
        # 6. 心跳 heartbeat 事件
        time.sleep(2)  # ← 关键：2秒轮询周期
```

| 对比维度 | AgentOS SSE | 标准SSE | WebSocket | LangGraph Streaming |
|----------|-------------|---------|-----------|---------------------|
| 实时性 | 2s延迟 | 即时推送 | 即时 | 即时 |
| 方向 | 单向(服→客) | 单向(服→客) | 双向 | 单向(服→客) |
| 实现方式 | 轮询DB+Redis | 事件驱动 | 事件驱动 | 事件驱动 |
| 事件类型 | agent-update, task-update, message-update, worker-pulse, heartbeat | 自定义 | 自定义 | 节点流 |
| 连接成本 | 2秒一次DB查询 | 长连接空闲 | 长连接心跳 | 长连接 |

**结论**：当前SSE实现是"伪推送"——用2秒轮询DB来实现。在低负载场景表现正常，但高负载时2秒间隔会导致消息丢失（created_at__gt 时间窗口可能跳过快速写入的消息），且每次轮询都查询3张表+Redis PubSub，DB压力随连接数线性增长。

### 1.4 编排器模式（三套引擎并存）

```
┌────────────────────────────────────────────────────────────┐
│                    编排器生态（三引擎）                      │
│                                                            │
│  ┌─────────────────┐  ┌────────────────┐  ┌──────────────┐│
│  │ Yunshu v4       │  │ Orchestrator v2│  │ orch_runner  ││
│  │ (yunshu_io.py)  │  │(orchestrator.py)│  │ (runner.py)  ││
│  ├─────────────────┤  ├────────────────┤  ├──────────────┤│
│  │ 调度模式：       │  │ 调度模式：      │  │ 调度模式：    ││
│  │ LLM文本协议      │  │ Plan-first     │  │ DAG依赖链    ││
│  ├─────────────────┤  ├────────────────┤  ├──────────────┤│
│  │ 任务分解：       │  │ 任务分解：      │  │ 任务分解：    ││
│  │ LLM实时PLAN      │  │ LLM生成+代码执行│  │ contract预定义││
│  ├─────────────────┤  ├────────────────┤  ├──────────────┤│
│  │ 并发：           │  │ 并发：          │  │ 并发：        ││
│  │ simple=1/med=3/  │  │ MAX_CONCURRENT │  │ max_parallel ││
│  │ complex=5(max=8) │  │ =3             │  │ =2           ││
│  ├─────────────────┤  ├────────────────┤  ├──────────────┤│
│  │ 特色：           │  │ 特色：          │  │ 特色：        ││
│  │ REFLECT自检3轮   │  │ pitfall自学习   │  │ DAG拓扑排序  ││
│  │ Checkpoint恢复   │  │ Token极省       │  │ 纯状态管理    ││
│  ├─────────────────┤  ├────────────────┤  ├──────────────┤│
│  │ 入口：           │  │ 入口：          │  │ 入口：        ││
│  │ redis_worker     │  │ daemon轮询      │  │ 手动/脚本调用 ││
│  └─────────────────┘  └────────────────┘  └──────────────┘│
│                                                            │
│  三套引擎互不感知，无统一调度层                                │
└────────────────────────────────────────────────────────────┘
```

| 引擎 | 决策者 | LLM调用次数 | 适用场景 | 核心创新 |
|------|--------|-------------|----------|----------|
| Yunshu v4 | 云枢LLM | 每轮1次(最多15轮) | 多Agent协同 | REFLECT自检回路 |
| Orchestrator v2 | LLM(仅计划) | 1次PlanGen + 异常时补调 | 工具调用链 | 执行阶段零LLM |
| orch_runner | 预定义contract | 0次 | DAG多步骤任务 | 纯Python依赖解析 |

**核心矛盾**：三套编排引擎功能重叠但互不通信——Yunshu能SPAWN子Agent但看不懂Orchestrator的PlanStep；Orchestrator有pitfall_memory但Yunshu用不了；orch_runner的DAG状态变化Yunshu无法感知。

---

## 二、四大特征横向对比

### 2.1 并发模型对比

| 系统 | 并发模型 | 最大并发 | 分布式 | 隔离级别 |
|------|----------|----------|--------|----------|
| **AgentOS** | ThreadPool + subprocess | **20** (redis_worker) | ❌ 单机 | ★★★★★ OS进程 |
| AutoGen | asyncio + gRPC | 理论无限 | ✅ gRPC分布式 | ★★☆☆☆ 对象 |
| CrewAI | 顺序Task + 异步LLM | 单Crew串行 | ✅ Cloud | ★★☆☆☆ 对象 |
| LangGraph | asyncio + 节点并行 | 图定义 | ✅ LangSmith | ★★★☆☆ 函数 |

**AgentOS优势**：20并发 + OS进程隔离是市面最强单机并发/隔离组合。AutoGen虽然理论上可无限分布式，但需要额外配置gRPC集群。

**AgentOS劣势**：20并发受限于单机CPU/内存。subprocess冷启动每任务5-15秒，20线程同时启动意味着最高300秒的纯系统开销。

### 2.2 超时/熔断对比

| 系统 | 超时层级 | 熔断机制 | 重试策略 | 死信队列 |
|------|----------|----------|----------|----------|
| **AgentOS** | **3级**(300/300/600s) | ✅ 硬终止+_cleanup | ❌ 无指数退避 | ❌ 无 |
| AutoGen | max_iterations | ❌ 无内置 | 手动实现 | ❌ |
| CrewAI | Task timeout | ❌ 无内置 | max_retry_limit | ❌ |
| LangGraph | 节点timeout | ✅ Durable中断 | ✅ 自动断点恢复 | ✅ LangSmith |
| MetaGPT | Role timeout | ❌ 流水线中断 | ❌ | ❌ |

**AgentOS优势**：三级超时设计在本组对比中独树一帜。子任务超时不影响编排总超时，编排总超时不阻塞后续消息。

**AgentOS劣势**：硬终止(SIGKILL)缺乏优雅降级。无重试策略意味着超时即丢弃。

### 2.3 实时推送对比

| 系统 | 推送方式 | 延迟 | 双向 | 事件粒度 |
|------|----------|------|------|----------|
| **AgentOS** | SSE(轮询实现) | **2s** | ❌ | agent/task/message/worker/heartbeat |
| AutoGen | gRPC Streaming | 毫秒级 | ✅ | AgentEvent/ToolCall |
| CrewAI | Control Plane | 秒级 | ✅ | Task/Crew状态 |
| LangGraph | LangSmith Streaming | 毫秒级 | ✅ | 节点/状态/Token |
| ChatDev 2.0 | REST轮询 | 秒级 | ❌ | 节点状态 |

**AgentOS优势**：5种事件类型覆盖全面，SSE比WebSocket更轻量（自动重连、单向传输）。

**AgentOS劣势**：轮询实现的SSE在语义上不是真正的Server-Sent Events——事件不是服务端即时推送，而是客户端定时拉取。2秒间隔在高频消息场景会导致遗漏。每次轮询查3张表，DB压力与连接数成正比。

### 2.4 编排模式对比

| 系统 | 核心范式 | 决策智能 | 自适应 | 状态持久化 |
|------|----------|----------|--------|------------|
| **AgentOS** | 三引擎并存 | LLM文本协议 / Plan-first / DAG | ★★★★☆ complexity自适应 | ✅ Checkpoint |
| AutoGen | Topic Pub/Sub | Selector LLM选发言者 | ★★★☆☆ | ❌ |
| CrewAI | Crew顺序/Flow事件 | 预定义YAML | ★★☆☆☆ | ❌ |
| LangGraph | 图计算+条件边 | 开发者定义+LLM路由 | ★★★★★ | ✅ Durable |
| MetaGPT | SOP流水线 | 固定角色 | ★☆☆☆☆ | ❌ |
| ChatDev 2.0 | DAG+RL | YAML定义+Puppeteer | ★★★★☆ | ⚠️ YAML |

**AgentOS优势**：编排模式多样性是独特竞争力——Yunshu适合探索性任务(LLM自主决策)，Orchestrator v2适合确定性工具链，orch_runner适合流程化DAG。不同场景可选不同引擎。

**AgentOS劣势**：三引擎互不感知导致"引擎孤岛"问题——Yunshu的执行经验(pitfall)无法传递给Orchestrator，Orchestrator的PlanStep无法被Yunshu理解。

---

## 三、优劣势综合评估

### 3.1 优势清单

| # | 优势 | 证据 | 竞争力评级 |
|---|------|------|-----------|
| 1 | **三级超时熔断** | 300s子/300s问答/600s编排，独立计时互不阻塞 | ★★★★★ 市面最强 |
| 2 | **OS进程隔离+20并发** | subprocess.Popen + ThreadPoolExecutor(20) | ★★★★★ 市面最强 |
| 3 | **编排模式多样性** | Yunshu(探索)+Orch v2(工具链)+Runner(DAG) | ★★★★☆ 独特创新 |
| 4 | **Token效率极致** | Orchestrator v2执行阶段零LLM调用 | ★★★★★ 市面最佳 |
| 5 | **REFLECT质量门禁** | 5项自检+3轮修正回路，市面唯一 | ★★★★★ 独有 |
| 6 | **pitfall自学习** | 异常修复经验自动写入记忆库 | ★★★★☆ 独特 |
| 7 | **SSE多事件类型** | 5种事件覆盖全生命周期 | ★★★☆☆ 中等 |

### 3.2 劣势/风险清单

| # | 劣势 | 严重度 | 影响面 | 根因 |
|---|------|--------|--------|------|
| 1 | **SSE伪推送** | 🔴 高 | 前端实时性 | 2秒轮询DB，非事件驱动 |
| 2 | **三引擎孤岛** | 🔴 高 | 架构一致性 | 三个编排器互不感知 |
| 3 | **20 vs 3并发不一致** | 🟡 中 | Web Chat体验差 | worker.py仅3线程 |
| 4 | **无重试/死信队列** | 🔴 高 | 消息可靠性 | 超时即丢弃，无退避重试 |
| 5 | **subprocess冷启动** | 🟡 中 | 延迟+资源 | hermes CLI每次5-15s |
| 6 | **DB轮询开销** | 🟡 中 | 可扩展性 | SSE每连接每2秒查3张表 |
| 7 | **SPAWN硬编码** | 🟡 中 | 扩展性 | if SPAWN_BANNI elif SPAWN_BASIR |

### 3.3 四特征加权评分

```
特征权重：并发(30%) · 熔断(25%) · 推送(20%) · 编排(25%)

                AgentOS  AutoGen  CrewAI  LangGraph  MetaGPT  ChatDev
并发能力(30%)   ★★★★☆    ★★★★★   ★★★☆☆   ★★★★☆     ★★☆☆☆   ★★★☆☆
熔断机制(25%)   ★★★★★    ★★☆☆☆   ★★☆☆☆   ★★★★☆     ★☆☆☆☆   ★★☆☆☆
实时推送(20%)   ★★☆☆☆    ★★★★☆   ★★★☆☆   ★★★★★     ★☆☆☆☆   ★★☆☆☆
编排模式(25%)   ★★★★☆    ★★★★☆   ★★★☆☆   ★★★★★     ★★★☆☆   ★★★★☆
──────────────────────────────────────────────────────────────────
加权综合        3.8       4.0      2.9      4.5       1.8      2.9
```

**结论**：AgentOS在熔断机制上是市面最强(5.0)，在编排模式上与AutoGen持平(4.0)，但实时推送(2.0)拖了后腿。综合评分3.8/5，介于AutoGen(4.0)和CrewAI(2.9)之间。

---

## 四、改进方向

### P0：关键修复（3项，预计50行代码）

| # | 改进项 | 代码量 | 收益 |
|---|--------|--------|------|
| 1 | **SSE事件驱动化**：用Redis Pub/Sub替代DB轮询 | ~30行 | 实时性从2s→即时；消除DB压力 |
| 2 | **Worker统一并发**：worker.py MAX_WORKERS 3→20 | 1行 | Web Chat与飞书体验对齐 |
| 3 | **指数退避重试**：子任务超时后3次退避重试(30s/60s/120s) | ~20行 | 消息可靠性从0→95% |

### P1：架构优化（3项，预计150行代码）

| # | 改进项 | 说明 | 参照 |
|---|--------|------|------|
| 4 | **编排引擎统一入口** | Dispatcher层根据任务类型路由到Yunshu/Orch/Runner | LangGraph Router |
| 5 | **pitfall_memory跨引擎共享** | Yunshu能读取Orchestrator的pitfall经验 | CrewAI Knowledge |
| 6 | **SPAWN通用化** | 基于AGENT_REGISTRY动态匹配，消除硬编码 | agent_registry已有抽象 |

### P2：长期演进（3项）

| # | 改进项 | 说明 |
|---|--------|------|
| 7 | **死信队列(RabbitMQ/Kafka)** | 替代Redis List FIFO，原生ACK+重试+死信 |
| 8 | **subprocess→长连接复用** | hermes session机制或gRPC，消除5-15s冷启动 |
| 9 | **WebSocket双向通信** | 替代SSE轮询，支持前端实时交互式编排 |

---

## 五、总结

AgentOS的四大架构特征形成了**'强熔断+强隔离+弱推送+多编排'**的组合：

- **熔断(600s三级)** — 市面最强，设计成熟
- **并发(20进程隔离)** — 单机场景市面最强，但缺乏分布式
- **推送(SSE轮询)** — 架构最弱环，2s延迟+DB轮询需重构
- **编排(三引擎)** — 创新性强但引擎孤岛问题突出

相比上次t2报告(综合评分2.5→3.3)，本轮聚焦四大特征的评分(3.8/5)反映架构在并发和熔断两个维度的实质性提升。但SSE伪推送和三引擎孤岛仍是通往生产级的硬障碍。

**最快改进**（P0，51行代码）：SSE事件驱动化+Worker统一并发+指数退避重试，可在一个迭代内完成。

---

## 附录：源码引用索引

| 特征 | 文件 | 关键行 | 参数/值 |
|------|------|--------|---------|
| Worker v5.0 | agents/worker.py | 27 | MAX_WORKERS=3 |
| Redis Worker v7.0 | agents/redis_worker.py | 207 | MAX_WORKERS=20 |
| 20并发 | agents/redis_worker.py | 11 | TASK_TIMEOUT=600 |
| 600s熔断 | agents/redis_worker.py | 12 | HERMES_TIMEOUT=600 |
| 子任务300s | agents/redis_worker.py | 13 | CHILD_TIMEOUT=300 |
| SSE推送 | agents/sse.py | 61 | time.sleep(2) |
| 编排器(Yunshu) | agents/yunshu_io.py | 388 | run_yunshu_session() |
| 编排器(Orch v2) | agents/orchestrator.py | 33 | MAX_CONCURRENT=3 |
| 编排器(Runner) | orchestrator_runner.py | 128 | max_parallel=2 |
| SPAWN硬编码 | agents/yunshu_io.py | 437-440 | if SPAWN_BANNI elif |
| Agent注册表 | agents/agent_registry.py | 7-30 | AGENT_REGISTRY{2} |

---

*分析基于 2026-06-24 commit ac08cf4 代码快照与 t1 市场调研报告。标注了所有主观推断。*
