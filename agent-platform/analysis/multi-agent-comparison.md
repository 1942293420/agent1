# 多Agent系统架构对比分析

> 为 Basir 提供决策参考素材 | 2026-06-24 | 云筑 (Banni) 调研

---

## 一、市场主流多Agent系统速览

| 系统 | GitHub Stars | 架构模式 | 核心技术栈 | 活跃度 |
|------|:-----------:|---------|-----------|:-----:|
| **AutoGPT** | ~170k | 单Agent+工具链 | Python, Docker, React | 维护模式 |
| **MetaGPT** | ~52k | 角色扮演多Agent (SOP驱动) | Python, asyncio, pydantic | 活跃 |
| **CrewAI** | ~28k | 角色分工多Agent (Crew+Flow) | Python (独立, 不依赖LangChain) | 非常活跃 |
| **AutoGen (MS)** | ~40k | 对等多Agent (消息传递) | Python/.NET, 分层架构 | 维护→MAF |
| **LangGraph** | ~12k | 图编排 (状态机+DAG) | Python/JS, LangChain生态 | 非常活跃 |
| **OpenAI Agents SDK** | ~25k | Agent手递手 (Handoff) | Python, 模型无关 | 活跃 |
| **TaskWeaver (MS)** | ~5k | Code-First 单Agent | Python, 代码执行容器 | 维护 |
| **SuperAGI** | ~16k | 多Agent marketplace | Python, Docker, React | 低活跃 |
| **BabyAGI** | ~21k | 任务队列+优先级 | Python | 实验性 |

---

## 二、各系统详细分析

### 2.1 AutoGPT — 单Agent自动化平台

**架构模式**: 单Agent + 工具链 + 工作流
- 非多Agent系统，但开创了"自主Agent"概念
- 通过 Block（功能块）构建工作流：每个Block执行单一动作
- Agent Builder: 低代码界面设计Agent行为
- 工作流管理：连接Block形成自动化流水线

**通信机制**: 无Agent间通信（单Agent模式）
- Agent通过工具调用与外部系统交互（Reddit API、YouTube API等）

**核心技术栈**:
- 后端：Python (FastAPI)
- 前端：React (Next.js)
- 部署：Docker Compose
- 数据库：PostgreSQL + Redis
- LLM：OpenAI API

**独特亮点**:
- 低代码Agent Builder（Block拖拽构建）
- 预置Agent市场（Marketplace）
- Agent可被外部事件触发，持续运行
- 监控和分析面板

**适用场景**: 个人自动化、社交媒体自动化、数据管道

**现状**: 经典版（MIT）已进入维护；新版平台使用 Polyform Shield 许可证（非完全开源）

---

### 2.2 MetaGPT — 软件公司SOP多Agent

**架构模式**: 角色扮演 + SOP驱动
- 模拟软件公司组织结构：产品经理 → 架构师 → 项目经理 → 工程师
- 核心哲学：`Code = SOP(Team)` — 将SOP固化为Agent协作流程
- 每个角色是独立的LLM Agent，按预定义SOP执行

**通信机制**: 消息传递 + 共享工作区
- Agent间通过消息（Message）传递信息
- 共享环境（Environment）作为工作区
- 按SOP顺序串行执行（先PRD → 再设计 → 再编码）

**核心技术栈**:
- Python 3.9+，基于 asyncio
- Pydantic 数据模型
- 支持多种LLM（OpenAI/Azure/Ollama/Groq等）
- 产品 MGX：自然语言编程（SaaS）

**独特亮点**:
- SOP驱动协作（最核心创新）— 将人类软件工程流程编码为Agent行为
- 一句需求生成完整项目（用户故事/竞品分析/数据结构/API/文档）
- 学术论文背书（ICLR 2024, ICLR 2025 oral）
- 角色专业化程度高

**适用场景**: 软件项目自动生成、需求→代码全流程

---

### 2.3 CrewAI — 角色分工+事件驱动

**架构模式**: 双层架构 — Crew（角色协作）+ Flow（事件驱动）
- **Crew**: 角色分工式多Agent团队，每个Agent有 role/goal/backstory
- **Flow**: 事件驱动的工作流引擎，精确控制执行路径
- 两者可组合使用：Flow编排Crew的执行

**通信机制**:
- Crew内：Agent间自然语言对话 + 任务委派
- Flow中：状态管理 + 条件分支 + 事件驱动
- 支持：sequential（顺序）、hierarchical（层级委派）两种协作模式

**核心技术栈**:
- 完全独立框架（不依赖LangChain）
- Python ≥3.10, UV包管理
- 支持任意LLM提供商
- 企业版 CrewAI AMP Suite（控制面板 + 追踪 + 安全）

**独特亮点**:
- 极简API设计：定义Agent角色 + 任务 → 自动协作
- Flow提供企业级精确控制（状态管理、条件分支、事件驱动）
- 100,000+ 认证开发者（DeepLearning.AI课程）
- 支持结构化输出（output_pydantic / output_json）
- 人类审核节点（human_input）

**适用场景**: 企业自动化、研究分析、内容生成、客服系统

---

### 2.4 AutoGen (Microsoft) — 对等多Agent消息传递

**架构模式**: 分层对等架构
- **Core API**: 消息传递 + 事件驱动 + 分布式运行时
- **AgentChat API**: 高层抽象（双Agent对话、群聊）
- **Extensions API**: LLM客户端、代码执行等扩展
- Agent间通过消息（Message）平等通信，无主从之分

**通信机制**:
- 消息传递（Message Passing）为核心原语
- 支持 AgentTool：将Agent封装为工具供其他Agent调用
- 群聊模式（GroupChat）：多Agent轮流发言
- 支持分布式部署（跨进程/跨机器）

**核心技术栈**:
- Python 3.10+ / .NET 跨语言支持
- 分层设计（Core → AgentChat → Extensions）
- AutoGen Studio：无代码GUI
- MCP Server集成
- AgentTool 手递手机制

**独特亮点**:
- 微软研究院出品，学术基础扎实
- 分层架构：底层灵活 + 高层简单
- 跨语言支持（Python + .NET）
- Magentic-One：基于AutoGen的通用Agent团队

**现状**: ⚠️ 已进入维护模式，微软推荐迁移至 Microsoft Agent Framework (MAF)

---

### 2.5 LangGraph — 图编排状态机

**架构模式**: 有向图编排（Graph-based State Machine）
- 节点（Node）= Agent/函数/工具调用
- 边（Edge）= 控制流（条件分支、循环）
- 状态（State）= 在图节点间传递的共享数据
- 本质是底层编排框架，不是"Agent框架"

**通信机制**:
- 通过共享State在节点间传递数据
- 图结构定义通信拓扑（谁 → 谁）
- 子图（Subgraph）支持嵌套
- Human-in-the-loop：任意节点可中断等待人类输入

**核心技术栈**:
- Python + TypeScript
- 基于 Pregel (Google) + Apache Beam 概念
- LangChain 生态集成
- LangSmith 可视化调试
- Deep Agents: 高层封装（规划 + 子Agent + 文件系统）

**独特亮点**:
- **持久化执行**（Durable Execution）：Agent崩溃后从断点恢复
- 精确控制流（条件分支、循环、并行）
- 长短期记忆（短期working memory + 长期持久化）
- 生产级部署（LangSmith Deployments）
- 被 Klarna、Replit、Elastic 等企业采用

**适用场景**: 需要精确控制流的复杂Agent工作流、长运行任务、人机协作

---

### 2.6 OpenAI Agents SDK — Agent手递手

**架构模式**: Agent手递手（Handoff）+ Agent即工具
- 每个Agent是独立LLM + 指令 + 工具 + 护栏
- Agent间通过 Handoff 转交控制权
- Agent可封装为 Tool 供其他Agent调用

**通信机制**:
- Handoff：Agent委托另一个Agent处理（转移会话控制权）
- Agent as Tool：Agent被包装为工具，像函数一样调用
- 共享 Sessions（对话历史管理）

**核心技术栈**:
- Python 3.10+，模型无关（支持100+ LLM）
- Pydantic 数据模型
- MCP Server 集成
- 内置 Tracing（运行追踪）
- Sandbox Agents（容器化代码执行）
- Realtime Agents（语音）

**独特亮点**:
- **Guardrails**: 输入/输出安全检查（可配置）
- **Tracing**: 内置运行追踪和调试
- **Sandbox Agents**: Agent在隔离容器中工作（文件系统+长时间任务）
- Handoff 模式简单直观：数学Agent ↔ 化学Agent
- OpenAI官方出品，与GPT模型深度优化

**适用场景**: 客服路由、多领域咨询、需要安全检查的场景

---

### 2.7 TaskWeaver (Microsoft) — Code-First单Agent

**架构模式**: 角色内部分工（单Agent，多角色）
- Planner（规划）→ CodeInterpreter（执行）→ 结果
- 非多Agent系统，但内部采用角色分工
- Code-First：用代码表达任务逻辑（非纯文本）

**核心技术栈**:
- Python ≥3.10
- 代码沙箱（Container模式）
- 插件系统（Plugin）
- 共享内存（Shared Memory）
- 经验系统（Experience）

**适用场景**: 数据分析、复杂数据处理

---

## 三、Agent Platform (AgentOS) 自分析

### 3.1 架构总览

```
用户(Web/飞书) → Django API(:8001) → Redis msg_queue
    → Worker v7.0 (20并发 ThreadPoolExecutor)
        → 云枢(Yunshu) LLM 调度器 ←→ 子Agent(Banni/Basir)
            ↕ 文本协议 (PLAN/SPAWN/CHECK/WAIT_ALL/REFLECT/REPLY)
        → SSE 推送 → 前端 EventSource 实时渲染
```

### 3.2 架构模式：文本协议主从架构

这是 Agent Platform 最核心的创新——**LLM输出结构化文本命令，Python解析执行**：

```
PLAN  → PlanGraph 依赖图解析 → 代码按并行组自动执行
SPAWN → subprocess.Popen 启动独立 Hermes Agent
CHECK → 查询子进程状态 + 读取输出
WAIT_ALL → 阻塞等待全部子任务完成
REFLECT → 自检清单（最多3轮修正）
REFLECT_PASS/FAIL → 质量门禁
REPLY → 输出最终答案
```

**与市场系统的本质区别**：
- 市面系统：Agent间通过消息/API/事件通信，LLM直接控制流程
- AgentOS：LLM输出命令文本 → Python Worker解析执行 → 子Agent作为独立进程运行
- 这创造了一个"LLM决策 + Python执行"的隔离层

### 3.3 云枢调度器（Yunshu）

**角色**: 主调度器（Master Orchestrator）
- 运行在独立 Hermes 会话中
- 接收用户消息 → 分析复杂任务 → 输出 PLAN（任务分解+依赖图）
- PlanGraph 自动解析 → 代码按依赖图并行/串行执行子任务
- 子任务完成后 → REFLECT 自检 → 汇总 → REPLY

**子Agent（Workers）**:

| Agent | 角色 | 能力 | 超时 |
|-------|------|------|------|
| **Banni** (云筑) | 工程执行 | 搜索、信息采集、代码编写、文件操作 | 1800s |
| **Basir** (云鉴) | 数据分析 | 概念推断、逻辑推理、报告生成、数据分析 | 1800s |

**Agent注册表** (`agent_registry.py`)：可扩展的Python dict，新Agent类型只需添加配置项。

### 3.4 通信机制

```
主调度器 (Yunshu LLM)
    │
    ├── 文本协议命令 ──→ Python Worker (yunshu_io.py)
    │                        │
    │                        ├── subprocess.Popen("hermes chat -q -p banni")
    │                        ├── subprocess.Popen("hermes chat -q -p basir")
    │                        │
    │                        └── stdout 捕获 → 解析 → 注入回 LLM context
    │
    └── 子Agent之间：不直接通信，通过Python Worker中转
```

**关键特点**:
- 子Agent是独立的 `hermes chat` 进程（自带25+工具、Memory、Skills）
- 每个子Agent使用独立 Hermes profile（不同的system prompt、工具权限）
- 心跳监控：每10s向DB推送心跳
- 资源监控：内存超限（>4GB）自动kill
- 僵尸保护：子进程超时300s自动清理
- Checkpoint：文件+DB双写，支持崩溃恢复

### 3.5 PlanGraph 依赖图

```python
@dataclass
class PlanGraph:
    complexity: str    # simple/medium/complex → 控制并行度
    nodes: list        # PlanNode(task_id, agent_type, description, dependencies)
    adjacency: dict    # task_id → [依赖的task_id]
    
    def get_parallel_groups():  # 拓扑排序 → 并行组
    def get_suggested_max_spawn():  # simple=1, medium=3, complex=5
```

**示例 PLAN 解析**：
```
复杂任务: "分析BTC近一周走势并写报告"
→ PlanGraph:
    Group 0 (并行): [t1: Banni采集数据]
    Group 1 (串行): [t2: Basir分析报告, depends_on=t1]
```

### 3.6 技术栈

| 层级 | 组件 | 版本 |
|------|------|------|
| 前端 | React + Vite + pure CSS (暗黑科技风) | React 18.2 / Vite 5.1 |
| 后端 | Django + DRF + Gunicorn | 5.2.15 / 3.17.1 |
| 数据库 | SQLite WAL | 6 索引 |
| 队列 | Redis | 8.0.5 (msg_queue + pub/sub SSE) |
| Worker | Python ThreadPoolExecutor | 20并发 / 600s超时 / back-pressure |
| AI引擎 | Hermes Agent → DeepSeek | deepseek-v4-pro |
| 部署 | systemd --user (4服务) | Ubuntu 26.04 |
| 飞书 | lark-cli relay | v1.0.55 |

### 3.7 Worker 演进历史

| 版本 | 并发 | 超时 | 关键架构变化 |
|------|------|------|-------------|
| v2 | 1 | 60s | 单轮 DeepSeek API |
| v3 | 1 | 60s | 手写工具循环（失败） |
| v4 | 1 | 600s | hermes chat -q 原生集成 |
| v4.1 | 1 | 600s | 多Agent角色画像 |
| v4.2 | 3 | 1800s | ThreadPoolExecutor + delegation_guard |
| v5.0 | 20 | 600s | 超时熔断 + back-pressure + SSE推送 |
| **v7.0** | **20** | **600s** | **文本协议 + PlanGraph + REFLECT + Checkpoint** |

---

## 四、架构模式横向对比

| 维度 | AgentOS | CrewAI | MetaGPT | AutoGen | LangGraph | OpenAI SDK |
|------|---------|--------|---------|---------|-----------|------------|
| **编排模式** | 文本协议主从 | 角色+事件驱动 | SOP流程 | 消息对等 | 图状态机 | Handoff手递手 |
| **Agent通信** | stdout解析 | 自然语言+委派 | 消息传递 | Message Passing | 共享State | Handoff+Tool |
| **任务分配** | PLAN→PlanGraph | Task自动委派 | SOP固定流程 | GroupChat轮转 | 图节点路由 | Agent路由 |
| **并行能力** | PlanGraph并行组 | Flow并行分支 | 顺序为主 | 群聊轮转 | 图并行边 | 有限 |
| **质量控制** | REFLECT自检(3轮) | human_input | SOP验证 | 无 | human-in-loop | Guardrails |
| **崩溃恢复** | Checkpoint双写 | 无 | 无 | 无 | Durable Exec | Sessions |
| **子Agent隔离** | 独立进程+Popen | 线程内 | asyncio协程 | 进程/分布式 | 图节点函数 | 线程 |
| **扩展新Agent** | 注册表dict | 定义role | 定义Role类 | 定义Agent类 | 添加Node | 创建Agent |
| **通信协议** | 自定义文本协议 | 无协议(内部) | 无协议(内部) | Message对象 | State dict | Handoff对象 |

---

## 五、AgentOS 的独特优势

### 5.1 文本协议隔离层
- LLM只负责"决策"（输出命令文本），Python负责"执行"
- 避免了LLM直接执行带来的不可控性（幻觉操作、死循环）
- Python Worker可以安全地拦截危险命令

### 5.2 子Agent完全独立
- 每个子Agent是独立 `hermes chat` 进程
- 自带完整的25+工具、Memory、Skills
- 进程级隔离：一个Agent崩溃不影响其他
- 资源监控 + 超时熔断 + 僵尸清理

### 5.3 PlanGraph 依赖图
- 任务自动拓扑排序 → 并行组
- 复杂度自适应并发度（simple=1, medium=3, complex=5）
- 比手动编排更可靠

### 5.4 REFLECT 质量门禁
- 子任务完成后自动触发自检（最多3轮修正）
- 5项检查清单：事实支撑、修正完成度、需求遗漏、结构完整性、可操作性
- 检测到"可能是"等不确定表述 → 自动补搜

### 5.5 极简扩展
```python
AGENT_REGISTRY["new_agent"] = {
    "name": "NewAgent",
    "role_prompt": "你是新Agent...",
    "default_timeout": 600,
    "capabilities": ["search", "code"],
}
```
无需修改任何核心代码，新Agent立即可用。

### 5.6 全链路实时推送
- Redis PUBLISH → Django SSE → EventSource
- 编排过程实时可视化（蓝色"已收到" → 灰色"第N轮" → 绿色"完成"）
- 用户无需刷新页面

---

## 六、AgentOS 的不足与风险

### 6.1 文本协议脆弱性
- 依赖LLM输出正确的命令格式（PLAN/SPAWN/REFLECT）
- LLM输出格式错误 → 解析失败 → 回退逻辑
- 实际测试中，DeepSeek有时不按要求输出格式

### 6.2 通信效率
- 子Agent输出通过stdout文本捕获 → Worker解析 → 注入LLM context
- 大输出（8000字符）在LLM context中占用大量token
- 没有结构化的Agent间通信协议

### 6.3 扩展上限
- 当前仅支持2个Agent类型（Banni + Basir）
- 最大并发子任务数为8（_absolute_max）
- 无分布式支持（所有Worker在同一台机器）

### 6.4 缺少标准化
- 自定义文本协议无文档/规范（与市场标准不兼容）
- 没有Agent通信标准（如A2A、MCP）
- 不能与外部Agent系统互操作

### 6.5 LLM依赖
- 云枢调度器的"大脑"是LLM
- LLM不稳定 → 整个调度链崩溃
- 降级方案（_fallback_reply）只能返回固定错误消息

---

## 七、架构建议

### 短期改进（低成本）
1. **PlanGraph可靠性增强**：PLAN解析失败时自动重试（换prompt）
2. **Agent注册表持久化**：从Python dict迁移到DB表（支持Web管理）
3. **子Agent结果结构化**：JSON输出替代纯文本（减少token消耗）

### 中期演进（中等成本）
4. **标准化通信协议**：兼容A2A（Agent-to-Agent）或MCP
5. **分布式Worker**：支持跨机器部署（当前单机）
6. **对外开放API**：让外部Agent能接入AgentOS调度

### 长期方向（高成本）
7. **多Master容错**：云枢调度器做主备（当前单点）
8. **Agent能力市场**：类似SuperAGI的Agent marketplace
9. **与LangGraph深度集成**：用LangGraph的Durable Execution增强崩溃恢复

---

## 八、结论

**AgentOS（Agent Platform）在架构上最像的市面系统是 CrewAI + LangGraph 的组合**：
- 像 CrewAI 的角色分工（Banni/Basir 类似 CrewAI 的 role 定义）
- 像 LangGraph 的图编排（PlanGraph ≈ LangGraph 的 StateGraph）
- 但通信机制完全不同：AgentOS 的"文本协议"模式是独一无二的

**核心竞争力**：
- 文本协议隔离层（LLM决策 + Python执行）
- 子Agent进程级独立（每个自带完整 Hermes 能力）
- 极简扩展（注册表dict）
- 全链路SSE实时推送

**需要警惕**：
- 文本协议的脆弱性是最大风险点
- 云枢是单点故障（LLM不可用时整个系统停摆）
- 生态孤岛（自定义协议无法与外部系统互操作）

---

*调研人：Banni (云筑) | 2026-06-24 | 为 Basir (云鉴) 提供决策素材*
