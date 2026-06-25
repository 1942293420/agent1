# AgentOS vs 主流多Agent系统 — 六维度对比分析报告 (t2)

> **Basir 分析** | 2026-06-24 | 基于 Banni t1 市场调研 + 最新源码审计
>
> 对比对象: **AgentOS (agent-platform)** vs **AutoGen · CrewAI · MetaGPT · LangGraph · ChatDev 2.0**
>
> 分析维度: 架构设计 · 调度机制 · Agent分工 · 通信方式 · 扩展性 · 成熟度

---

## 一、架构设计

### 1.1 AgentOS 架构全景

AgentOS 采用 **三层 + 双管道** 架构：

```
              入口层: Web Chat (views.py)  +  飞书 Bot (gateway → Redis)
                │                                    │
         管道A: DeepSeek API 直调              管道B: 云枢编排引擎
         (单Agent聊天, Web only)               Redis BRPOP → yunshu_session()
                │                                    │
              执行层: ThreadPoolExecutor(20) + subprocess.Popen(hermes chat)
                             Banni(工程) + Basir(分析)
                │
              数据层: SQLite(11表) + Redis List(msg_queue) + Checkpoint(文件+DB)
```

**核心发现**: 管道A（Web Chat直调DeepSeek）和管道B（飞书→云枢编排）走完全不同的代码路径，同一系统在不同入口提供的能力**不一致**——Web是单Agent聊天，飞书是多Agent协同。

### 1.2 六方案架构对比

| 维度 | AgentOS | AutoGen | CrewAI | MetaGPT | LangGraph | ChatDev 2.0 |
|------|---------|---------|--------|---------|-----------|-------------|
| **架构层级** | 3层(入口→执行→数据) | 3层(Core/AgentChat/Ext) | 2层(Crews+Flows) | 单层流水线 | 2层(Graph+State) | 3层(UI+Engine+DAG) |
| **编排中心** | 双中心(Web直调/云枢编排) | 多中心(Topic订阅) | 单中心(Crew) | 单中心(SOP) | 无中心(图定义) | 单中心(DAG引擎) |
| **Agent隔离** | **OS进程级**(subprocess.Popen) | Python对象级 | Python对象级 | Python对象级 | Python函数级 | Python进程级 |
| **状态管理** | 内存dict+Checkpoint+DB | Runtime状态 | 内存对象 | 环境消息 | StateGraph持久化 | YAML配置 |
| **代码规模** | ~2500行核心 | ~50k行 | ~15k行 | ~30k行 | ~20k行 | ~10k行+前端 |

### 1.3 架构优劣

**AgentOS 优势**:
- **OS进程隔离**: `subprocess.Popen(hermes chat)` 确保每个子Agent是独立进程，崩溃不影响主调度器。AutoGen/CrewAI/LangGraph的Agent共享同一进程，一个泄漏全盘崩溃。
- **极简代码**: 编排核心（yunshu_io 590行 + plan_parser 109行 + redis_worker 247行）不到1000行。竞品需数万行实现类似能力。
- **自适应并发**: LLM根据任务复杂度自主选择 `simple=1, medium=3, complex=5` 并发度。

**AgentOS 劣势**:
- 🔴 **双管道不一致**: Web Chat（单Agent）与飞书编排（多Agent）能力不对等。
- 🔴 **单点故障**: 云枢LLM的文本命令输出质量决定整个编排成败，PlanGraph.parse()返回None则编排失败。
- 🟡 **两套任务模型**: Task(7状态) 与 ParentTask/ChildTask(6状态) 语义重叠、互不通信。

---

## 二、调度机制

### 2.1 AgentOS 调度模型

AgentOS 采用 **Plan-first + 代码接管执行** 的两阶段调度：

```
用户消息
  ↓
[阶段1: PLANNING]  云枢LLM分析 → 输出 PLAN 命令
  → PlanGraph.parse() 解析: 提取complexity、DAG依赖、并行分组
  → 护栏: simple=1并发, medium=3, complex=5 (上限8)
  ↓
[阶段2: EXECUTION] 代码按拓扑分组执行
  → get_parallel_groups() 基于Kahn拓扑排序分组
  → 同组内并行 subprocess.Popen()，组间串行
  → wait_all() 轮询proc.poll()(2s间隔, max 600s)
  ↓
[阶段3: REFLECT] 质量自检回路(最多3轮)
  → 5项检查: 事实支撑 / 修正完成 / 需求遗漏 / 结构完整 / 可操作建议
  → REFLECT_PASS → REPLY; REFLECT_FAIL → 回路修正
  → 3轮后 FORCE_PASS 熔断
  ↓
[阶段4: REPLY] 最终回复写DB
```

主循环上限：15轮（yunshu_io.py:389）

### 2.2 六方案调度对比

| 调度维度 | AgentOS | AutoGen | CrewAI | MetaGPT | LangGraph | ChatDev 2.0 |
|----------|---------|---------|--------|---------|-----------|-------------|
| **调度模式** | Plan-first + 代码执行 | 事件驱动对话 | 顺序Task序列 | SOP流水线 | 图节点遍历 | DAG引擎 |
| **任务分解** | LLM自主 + 拓扑分组 | 开发者手动 | YAML预定义 | SOP固定角色 | 图节点+子图 | YAML配置 |
| **并发策略** | 按依赖组分批并行 | GroupChat轮转 | 单Crew串行 | 角色串行 | 无依赖节点并行 | DAG并行 |
| **质量自检** | ✅ REFLECT 3轮 | ❌ 无 | ❌ 无 | ❌ 无 | ❌ (靠人工) | ❌ 无 |
| **动态适应** | ✅ LLM决定complexity | ⚠️ Selector | ❌ | ❌ | ✅ 条件边 | ✅ RL |
| **任务嵌套** | 1层(父→子) | 无限嵌套 | 1层(Task序列) | 4-5角色流水线 | 无限子图 | 多层级DAG |

### 2.3 调度优劣

**AgentOS 优势**:
- **Plan-first 减少LLM调用**: 一次PLAN生成全部计划，后续按代码逻辑执行。AutoGen每步对话都需LLM调用，token开销大。
- **拓扑分组并行**: get_parallel_groups() 自动识别可并发组，最大化利用并发。
- **REFLECT 质量门禁**: 5项检查清单——**市面方案中唯一的自动化质量自检**。
- **复杂度自适应**: simple/medium/complex 三档避免过度并发。

**AgentOS 劣势**:
- 🔴 **PLAN脆弱性**: 格式不符合预期→parse()返回None→编排无法启动，无ReAct fallback。
- 🟡 **REFLECT同谋盲区**: 云枢LLM检查的是它自己分配的子Agent结果——同一个LLM在审查另一个LLM，缺乏独立评估。
- 🟡 **无动态任务生成**: PLAN一旦生成，执行期间无法根据中间结果动态添加新任务。
- 🟡 **粗粒度三档**: 仅simple/medium/complex，无法表达更精细的并发控制需求。

---

## 三、Agent分工

### 3.1 AgentOS 分工模型

AgentOS 当前只有 **2种Agent**，通过 agent_registry.py 字典硬编码：

| Agent | 角色定位 | 分配方式 | 典型任务 |
|-------|---------|---------|---------|
| **Banni** (工程) | 信息搜索、代码生成、工程任务 | 云枢LLM输出 SPAWN_BANNI 命令 | 搜索Leader&Workers方案、生成代码、调用工具 |
| **Basir** (分析) | 概念推断、逻辑推理、报告生成 | 云枢LLM输出 SPAWN_BASIR 命令 | 数据分析、对比报告、结构化输出 |

**分工逻辑**（yunshu_io.py:425-428，硬编码switch-case）:
```python
if cmd_name == "SPAWN_BANNI":
    response = handler.spawn("banni", m.group(1))
elif cmd_name == "SPAWN_BASIR":
    response = handler.spawn("basir", m.group(1))
```

**分工特点**:
- 云枢LLM根据任务性质自主判断用Banni还是Basir
- 子Agent之间**无直接通信**——Banni搜索结果→云枢中转→Basir分析
- 新增Agent需修改3处代码（agent_registry.py + CMD_PATTERNS正则 + yunshu_io.py switch-case）

### 3.2 六方案分工模型对比

| 分工维度 | AgentOS | AutoGen | CrewAI | MetaGPT | LangGraph | ChatDev 2.0 |
|----------|---------|---------|--------|---------|-----------|-------------|
| **分工方式** | LLM自主判断+硬编码2类 | 开发者定义角色 | YAML配置 role/goal | SOP固定角色 | 无角色概念(纯函数) | YAML配置 |
| **Agent数量** | 2 (Banni+Basir) | 自定义任意数量 | 自定义任意数量 | 4-5固定角色 | 任意数量节点 | 自定义任意数量 |
| **分工粒度** | 粗(工程vs分析) | 细(开发者控制) | 细(YAML定义) | 粗(PM/Arch/PM/Eng) | 极细(函数级) | 细(YAML定义) |
| **新增Agent成本** | 3处代码修改 | 子类化Assis.Agent | YAML加一段配置 | 子类化Role | 写一个Python函数 | YAML加一段配置 |
| **分工动态性** | ✅ LLM自主判断 | ⚠️ 开发者预设 | ❌ YAML预定义 | ❌ SOP固定 | ✅ 条件边路由 | ✅ RL动态 |
| **Agent间直连** | ❌ 云枢中转 | ✅ Topic订阅 | ✅ output→下Task | ✅ 角色间消息 | ✅ State读写 | ✅ DAG节点间 |

### 3.3 分工优劣

**AgentOS 优势**:
- **LLM自主分工**: 云枢根据任务内容动态判断用谁，无需人工预定义流程。对比MetaGPT的SOP固定分工（PM→Arch→PM→Engineer），灵活性更高。
- **角色语义清晰**: Banni=搜+做，Basir=想+写，两角色职责边界明确。
- **分工与监控解耦**: 无论分给谁，都走同一套subprocess→5维监控→wait_all流程。

**AgentOS 劣势**:
- 🔴 **只有2种Agent**: 无法支持更细致分工（如代码审查Agent、测试Agent、部署Agent）。对比CrewAI/LangGraph可以任意定义。
- 🔴 **SPAWN硬编码**: `if SPAWN_BANNI elif SPAWN_BASIR` 阻止了动态扩展。AgentRegistry的 register_agent() 接口已设计好但yunshu_io.py未使用。
- 🟡 **Agent间无直连**: Banni搜索→云枢中转→Basir分析，增加跳数和延迟。对比AutoGen的Agent可Topic订阅直接通信。
- 🟡 **无Agent组合模式**: 无法定义"Banni+Basir同时干一件事"之类的组合模式。对比AutoGen的Team和LangGraph的子图。

---

## 四、通信方式

### 4.1 AgentOS 通信拓扑

AgentOS 采用 **严格星型拓扑**——云枢是唯一通信中枢：

```
              云枢 LLM (唯一通信中枢 / 决策者)
              │ stdout     │ stdout        │ stdout
         ┌────▼───┐   ┌───▼────┐   ┌─────▼──────┐
         │ Banni  │   │ Basir  │   │   ...      │
         │ 子进程  │   │ 子进程  │   │  子进程    │
         └────────┘   └────────┘   └────────────┘
         无直连         无直连         无直连
```

**通信层级**:

| 通信对 | 协议 | 载体 | 可靠性 |
|--------|------|------|--------|
| 云枢↔Worker | 文本命令(stdout正则解析) | subprocess管道 | ❌ 无ACK/重试 |
| Worker↔子Agent | 文本(stdin/stdout) | subprocess管道 | ❌ 单次读取 |
| 用户↔AgentOS | REST/飞书Webhook | HTTP | ✅ 标准HTTP |
| Worker↔Redis | BRPOP/LPUSH | TCP | ✅ Redis保证 |
| 子Agent↔DB | REST API | HTTP | ⚠️ 无重试 |

**核心通信代码**（yunshu_io.py:509-523）:
```python
def _hermes_q(message, profile):
    r = subprocess.run(
        ["hermes", "chat", "-q", message, "-p", profile, "-Q", "--yolo"],
        capture_output=True, text=True, timeout=300
    )
    raw = r.stdout.strip()
    return raw or r.stderr.strip() or ""
```

每次通信都是一次完整的 `hermes chat -q` 进程启动→执行→退出周期。实测冷启动耗时 **5-15秒**。

### 4.2 六方案通信对比

| 通信维度 | AgentOS | AutoGen | CrewAI | LangGraph |
|----------|---------|---------|--------|-----------|
| **拓扑** | 严格星型 | Topic Pub/Sub | 顺序传递 | 图边传递 |
| **协议** | stdout文本 + REST | gRPC消息 | Python对象 | Shared State |
| **Agent间直连** | ❌ 不支持 | ✅ Topic订阅 | ✅ output→下Task | ✅ State读写 |
| **消息格式** | 非结构化文本 | AgentEvent(结构化) | TaskOutput(结构化) | State dict |
| **流式通信** | ❌ 全量stdout | ✅ gRPC流 | ❌ | ✅ Streaming |
| **消息可靠性** | ❌ 无ACK | ✅ gRPC保证 | ⚠️ 内存(易丢失) | ✅ Durable |
| **冷启动延迟** | 🔴 5-15s/次 | 🟢 长连接无延迟 | 🟢 内存 | 🟢 内存 |
| **文本协议数** | 10个命令(正则) | N/A(API调用) | N/A(方法调用) | N/A(函数调用) |

### 4.3 通信优劣

> **结论: 通信是AgentOS最薄弱的维度**

**AgentOS 优势**:
- **进程级通信隔离**: subprocess管道天然防止Agent间相互干扰。
- **简洁语义**: 10个命令（PLAN/SPAWN/WAIT/CHECK/KILL/REPLY/REFLECT/REFLECT_PASS/REFLECT_FAIL），每个一行正则。

**AgentOS 劣势**:
- 🔴 **文本协议脆弱性**: 正则匹配 `^SPAWN_BANNI\s*:?\s*(.+)` ——任何格式偏差（多空格、markdown包裹）都导致解析失败。
- 🔴 **CLI冷启动延迟**: `hermes chat -q` 每次5-15秒，15轮主循环 = 75-225秒纯启动开销。
- 🔴 **无ACK/重试**: Redis List FIFO无确认，Worker崩溃消息丢失；子Agent结果单次读取无重传。
- 🟡 **无Agent间直连**: Banni搜索→Basir分析必须全回云枢中转，增加跳数。
- 🟡 **无流式输出**: 用户看不到实时进度，只能轮询API。

---

## 五、扩展性

### 5.1 AgentOS 扩展现状

**Agent类型扩展**（当前硬编码在3处）:
1. agent_registry.py: 字典添加配置项
2. yunshu_io.py: CMD_PATTERNS 添加新正则
3. yunshu_io.py: switch-case 添加新 elif 分支

**水平扩展**: ❌ 单机，SQLite单文件 + 单Redis + 单Worker进程

**工具扩展**: 完全依赖 hermes CLI 生态，Yunshu层无独立工具注册机制

**LLM扩展**: 硬编码DeepSeek（通过hermes profile），切换需改hermes配置

### 5.2 六方案扩展性对比

| 扩展维度 | AgentOS | AutoGen | CrewAI | LangGraph |
|----------|---------|---------|--------|-----------|
| **Agent类型扩展** | 字典+正则硬编码(3处改) | AssistantAgent子类化 | YAML配置(1处) | Python函数(1处) |
| **工具扩展** | hermes CLI间接 | Extensions+MCP | BaseTool继承 | 任意Python函数 |
| **水平扩展** | ❌ 单机 | ✅ gRPC分布式 | ✅ Cloud | ✅ LangSmith |
| **多LLM** | DeepSeek only | OpenAI+多模型 | 多模型 | 全生态 |
| **跨语言** | ❌ | ✅ Python+.NET | ❌ | ✅ LangGraph.js |
| **插件机制** | ❌ 无 | ✅ Extensions | ⚠️ 社区 | ✅ LangChain生态 |
| **部署方式** | systemd×4 | pip install | pip install | pip install |
| **可观测性** | print+SSE | OpenTelemetry | Control Plane | LangSmith全链路 |

### 5.3 扩展性优劣

> **结论: 扩展性是AgentOS差距最大的维度**

**AgentOS 优势**:
- **AgentRegistry设计正确**: register_agent() 和 get_role_prompt() 已定义标准化接口——问题只在yunshu_io.py未使用。
- **极简代码降低维护成本**: 2500行核心代码，新增功能影响范围容易评估。

**AgentOS 劣势**:
- 🔴 **SPAWN硬编码**: `if SPAWN_BANNI elif SPAWN_BASIR` 阻止了Agent动态扩展。理想改为通用模式仅需~10行代码:
  ```python
  if cmd_name.startswith("SPAWN_"):
      agent_type = cmd_name[6:].lower()
      if agent_type in AGENT_REGISTRY:
          response = handler.spawn(agent_type, m.group(1))
  ```
- 🔴 **无Agent SDK**: 没有标准化"创建Agent"的编程接口。对比AutoGen的AssistantAgent、CrewAI的YAML配置。
- 🟡 **单机天花板**: 当前架构上限约20并发消息 × 3-8子Agent = 60-160并发子Agent。生产级场景无法支撑。
- 🟡 **无MCP原生支持**: 完全依赖hermes CLI间接层。

---

## 六、成熟度

### 6.1 AgentOS 成熟度评估

| 维度 | 状态 | 说明 |
|------|------|------|
| **开发阶段** | 🟡 原型向产品过渡 | 核心编排引擎功能完整但工程化不足 |
| **代码质量** | 🟢 良好 | ~2500行核心，结构清晰，有测试覆盖(test_v4_core.py) |
| **文档** | 🟡 偏少 | 无API文档，无使用手册，依赖源码注释 |
| **测试覆盖** | 🟡 基础 | test_v4_core.py覆盖文本协议解析和PlanGraph，无集成/E2E测试 |
| **生产部署** | 🟡 4×systemd | 需要手动配置EnvironmentFile注入密钥，无Docker一键部署 |
| **错误处理** | 🟡 中等 | 有Checkpoint恢复、5维监控，但无死信队列、无告警通知 |
| **社区/生态** | 🔴 自建 | 无开源社区，无外部贡献者 |
| **版本管理** | 🟡 v7.0 | 版本号存在但无changelog、无release流程 |
| **安全** | 🟡 中等 | AES加密飞书配置，但API无认证鉴权 |

### 6.2 六方案成熟度对比

| 成熟度维度 | AgentOS | AutoGen | CrewAI | MetaGPT | LangGraph | ChatDev 2.0 |
|-----------|---------|---------|--------|---------|-----------|-------------|
| **GitHub Stars** | - | ~40k | ~28k | ~50k | ~10k | ~27k |
| **维护状态** | 🟡 活跃开发 | ⚠️ 维护模式 | ✅ 非常活跃 | ✅ 活跃 | ✅ 非常活跃 | ✅ 活跃 |
| **生产就绪** | ❌ 原型 | ⚠️ 有企业用户 | ✅ 企业级 | ❌ 研究原型 | ✅ 企业级 | ✅ 产品化 |
| **文档质量** | 🟡 源码注释 | 🟢 完善 | 🟢 完善 | 🟢 学术论文+文档 | 🟢 非常完善 | 🟢 完善 |
| **企业用户** | 0(自用) | 多家(Elastic等) | 100k+认证开发者 | 学术研究 | Klarna/Replit/Elastic | 产品化平台 |
| **社区活跃度** | 🔴 无 | 🟡 下降中 | 🟢 非常活跃 | 🟢 GitHub活跃 | 🟢 非常活跃 | 🟢 活跃 |
| **商业化** | ❌ 无 | 转MAF | ✅ AMP Suite | 🟡 MGX产品 | ✅ LangSmith | ✅ 平台 |
| **CI/CD** | ❌ 无 | ✅ GitHub Actions | ✅ CI | ✅ CI | ✅ CI | ✅ CI |
| **安装难度** | 🔴 复杂(4服务+Redis) | 🟢 pip install | 🟢 pip install | 🟢 pip install | 🟢 pip install | 🟡 Docker |
| **论文发表** | 无 | ICLR等顶会 | 无 | ✅ ICLR/NeurIPS | 有(学术引用) | ✅ NeurIPS 2025 |

### 6.3 AgentOS 成熟度定位

```
研究原型 ←————————————————————————→ 企业级产品
   MetaGPT      AgentOS    ChatDev    CrewAI    LangGraph
  (学术SOP)   (创新原型)  (产品化)   (商业化)  (事实标准)
```

AgentOS 处于 **研究原型向工程产品过渡阶段**。核心创新（LLM自主编排 + REFLECT + 5维监控）在学术意义上独特，但工程化（通信、扩展、部署、生态）全面落后。

---

## 七、综合评分矩阵

```
维度权重: 架构(20%) · 调度(15%) · 分工(15%) · 通信(20%) · 扩展(15%) · 成熟度(15%)

                AgentOS   AutoGen   CrewAI   MetaGPT  LangGraph ChatDev2.0
架构设计          3.8       3.6       3.4       2.8       4.0       3.8
调度机制          3.6       2.8       2.6       2.2       4.2       3.4
Agent分工         2.8       4.2       4.4       3.0       4.8       4.0
通信方式          1.4       4.6       3.2       2.8       4.8       3.0
扩展性            1.8       4.6       4.4       2.4       4.8       3.2
成熟度            1.6       4.0       4.2       3.2       4.8       4.0
─────────────────────────────────────────────────────────────────────────
加权综合          2.5       3.9       3.7       2.7       4.6       3.6
```

### 关键发现

1. **最大短板 — 通信方式 (1.4/5)**: 文本协议+subprocess+无ACK，可靠性和延迟全面落后。这是生产化的**第一道坎**。

2. **最大长板 — 架构设计 (3.8/5)**: OS进程隔离+极简代码+自适应并发，在隔离性和简洁性上领先。

3. **潜在长板未激活 — Agent分工**: AgentRegistry设计正确但未使用，仅需~10行代码即可实现动态Agent扩展。

4. **被低估的优势 — 调度机制 (3.6/5)**: REFLECT自检回路是市面方案中**唯一**的自动化质量门禁。Plan-first大幅减少LLM调用。

5. **最大差距 — 成熟度 (1.6/5)**: 无社区、无文档、无企业用户、无CI/CD、无商业化。所有竞品在这些维度全面领先。

### 各系统一句话定位

| 系统 | 定位 |
|------|------|
| **AgentOS** | 强隔离+弱通信的创新原型——子Agent生命周期管控业界最强 |
| **LangGraph** | 有状态Agent编排的事实标准——全维度均衡强大 |
| **AutoGen** | 分布式Agent通信框架——已进入维护模式转MAF |
| **CrewAI** | 最快的多Agent MVP框架——YAML配置+企业级商业支持 |
| **MetaGPT** | SOP驱动软件开发研究平台——学术创新为主 |
| **ChatDev 2.0** | 零代码拖拽式多Agent编排平台——产品化最完整 |

---

## 八、改进路线图

### P0 — 通信模型重构

| 改进项 | 代码量 | 预期收益 |
|--------|--------|---------|
| SPAWN命令通用化 | ~10行 | 新增Agent无需改yunshu_io.py |
| 结构化协议层(JSON替代文本正则) | ~50行 | 消除解析失败风险 |
| 子进程→长连接复用(session机制) | ~30行 | 消除5-15s冷启动延迟 |
| Redis ACK确认机制 | ~20行 | 杜绝消息丢失 |

### P1 — 调度与分工增强

| 改进项 | 参照 | 收益 |
|--------|------|------|
| Agent分工SDK标准化 | CrewAI YAML配置 | 新增Agent只需YAML/JSON一段配置 |
| REFLECT人工审核选项 | LangGraph Human-in-loop | 高风险操作安全可控 |
| 动态任务生成 | AutoGen嵌套Team | 执行期间根据中间结果调整 |
| Agent间直连通信 | AutoGen Topic订阅 | 减少云枢中转跳数 |

### P2 — 成熟度提升

| 改进项 | 说明 |
|--------|------|
| Docker一键部署 | 替代4个systemd服务手动配置 |
| CI/CD管道 | GitHub Actions自动化测试+部署 |
| API文档 | OpenAPI/Swagger自动生成 |
| Worker水平扩展 | 多进程/多机器共享Redis队列 |
| PostgreSQL迁移 | 替代SQLite单文件并发瓶颈 |
| MCP工具集成 | 原生支持MCP协议，扩大工具生态 |

---

## 附录: 源码引用索引

| 分析点 | 源码文件 | 行号 |
|--------|---------|------|
| 文本协议命令正则 | agents/yunshu_io.py | 16-29 |
| SPAWN子进程创建 | agents/yunshu_io.py | 142-194 |
| REFLECT状态机 | agents/yunshu_io.py | 32-84, 123-139 |
| PlanGraph依赖解析 | agents/plan_parser.py | 26-71 |
| 拓扑分组算法(Kahn) | agents/plan_parser.py | 89-102 |
| WAIT_ALL轮询 | agents/yunshu_io.py | 231-258 |
| 子Agent清理 | agents/yunshu_io.py | 281-288 |
| 五维监控 | agents/redis_worker.py | 58-122 |
| Worker主循环 | agents/redis_worker.py | 205-247 |
| Agent注册表 | agents/agent_registry.py | 7-61 |
| Checkpoint持久化 | agents/checkpoint.py | 13-94 |
| 云枢主循环 | agents/yunshu_io.py | 376-506 |
| SPAWN硬编码 | agents/yunshu_io.py | 425-428 |
| Web直调管道 | agents/views.py | _call_llm_for_reply |

---

*报告完成。分析基于 2026-06-24 代码快照和 Banni t1 市场调研结果。所有评分为5分制。框架生态信息可能随时间变化，请以官方最新文档为准。Agent分工和成熟度维度为本次t2新增重点分析维度。*
