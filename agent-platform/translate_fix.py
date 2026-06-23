#!/usr/bin/env python3
"""补翻译遗漏的 29 个技能描述"""
import json, urllib.request, urllib.error, time

API = "http://localhost:8001/api/skills"

MISSING = {
    "creative-ideation": "创意灵感生成",
    "ai-comparison-research": "AI 产品对比研究",
    "research-paper-writing": "机器学习论文写作",
    "python-learning-plan": "Python → AI Agent 学习计划",
    "hermes-vision-setup": "视觉提供商配置",
    "lm-evaluation-harness": "LLM 基准测试",
    "trl-fine-tuning": "Transformer 强化学习",
    "audiocraft": "音频生成",
    "segment-anything": "图像分割模型",
    "vllm": "高性能 LLM 推理",
    "jd-product-scraping": "京东商品采集",
    "pycharm-remote-setup": "PyCharm 远程配置",
    "kanban-orchestrator": "Kanban 任务编排",
    "kanban-worker": "Kanban Worker 指南",
    "feishu-cli": "飞书 CLI 工具",
    "ah-django-developer": "Django 开发助手",
    "node-inspect-debugger": "Node.js Inspect 调试器",
    "agent-collaboration-protocol": "Agent 协作协议",
    "api-design-doc": "API 接口设计文档",
    "gen-code": "代码生成技能",
    "remote-ops": "远程访问配置",
    "polymarket-query": "Polymarket 预测市场查询",
    "jupyter-live": "Jupyter 实时内核",
    "headless-browser": "无头浏览器自动化",
    "llama-cpp": "llama.cpp + GGUF 本地推理",
}

DESCS = {
    "creative-ideation": "当用户说「我想做点什么」「给我一个项目灵感」时，通过各种创意约束条件生成项目创意。",
    "ai-comparison-research": "对 AI 产品、平台、模型和功能进行系统化多维度对比分析，适用于技术选型和竞品研究。",
    "research-paper-writing": "端到端 ML/AI 学术论文写作流水线，覆盖实验到投稿全流程，目标会议 NeurIPS、ICML、ICLR。",
    "python-learning-plan": "为范先生生成结构化 Python 学习课程的下一节内容，循序渐进的 AI Agent 工程师培养计划。",
    "hermes-vision-setup": "配置、诊断和修复 Hermes Agent 的图像分析（视觉）功能，自定义视觉提供商。",
    "lm-evaluation-harness": "在 60+ 学术基准上评估 LLM 性能（MMLU、HumanEval、GSM8K、TruthfulQA 等），用于模型选型和对比。",
    "trl-fine-tuning": "使用 TRL 进行模型对齐训练：SFT、DPO、PPO、GRPO、奖励建模等 RLHF 方法。",
    "audiocraft": "使用 Meta AudioCraft（MusicGen + AudioGen）进行文本到音乐和文本到音效的生成。",
    "segment-anything": "使用 Meta SAM 进行零样本图像分割，支持点、框、Mask 三种输入方式。",
    "vllm": "使用 vLLM 部署高吞吐量 LLM API，支持 PagedAttention、量化、OpenAI 兼容接口。",
    "jd-product-scraping": "爬取京东商品搜索结果：SKU 名称、价格、店铺、标签。京东反爬严格，需注意频率控制。",
    "pycharm-remote-setup": "在 Ubuntu（桌面或无头服务器）上安装 PyCharm 并配置 Python 远程开发环境。",
    "kanban-orchestrator": "Kanban 核心 Worker 生命周期，包括 kanban_create 扇出模式和「分解→分派→聚合」任务编排模式。",
    "kanban-worker": "Kanban Worker 使用指南，包含常见陷阱和示例代码，由 Hermes Kanban 调度器自动加载。",
    "feishu-cli": "飞书操作一站式技能：创建文档、管理任务、搜索消息、检查权限，lark-cli 所有功能。",
    "ah-django-developer": "评估 Django 项目上下文，识别技术栈和架构模式，提供针对性开发指导。",
    "node-inspect-debugger": "当 console.log 不够用时，通过终端程序化驱动 Node.js V8 Inspector 协议进行深度调试。",
    "agent-collaboration-protocol": "三个 Agent 角色通过共享工作区协作，实现多智能体协调工作流。",
    "api-design-doc": "根据需求文档和数据库 DDL 等输入，生成标准化的 API 接口设计文档。",
    "gen-code": "根据需求描述自动生成代码，支持多种编程语言和框架。",
    "remote-ops": "配置远程访问和 VPN 网络，让用户从外部安全连接到 Hermes 主机。",
    "polymarket-query": "通过 Polymarket 公共 REST API 查询预测市场数据：市场列表、价格、订单簿。",
    "jupyter-live": "提供有状态的 Python REPL，变量跨轮次持久化，适合迭代式数据探索。",
    "headless-browser": "在 Ubuntu 上搭建无头浏览器自动化环境，用于网页爬虫和 RPA。",
    "llama-cpp": "使用 llama.cpp 进行 GGUF 格式本地推理，支持量化选择和 HuggingFace 模型发现。",
}

def update(slug, name=None, desc=None):
    data = {}
    if name: data["name"] = name
    if desc: data["description"] = desc
    req = urllib.request.Request(f"{API}/{slug}/", method="PATCH")
    req.add_header("Content-Type", "application/json")
    req.data = json.dumps(data).encode()
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}"}
    except Exception as e:
        return {"error": str(e)[:100]}

ok = 0
fail = 0
for slug in MISSING:
    name = MISSING.get(slug)
    desc = DESCS.get(slug)
    result = update(slug, name=name, desc=desc)
    if "error" in result:
        print(f"  ✗ {slug}: {result['error']}")
        fail += 1
    else:
        ok += 1
    time.sleep(1.5)

print(f"\n完成！成功 {ok}，失败 {fail}")
