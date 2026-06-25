"""
Agent 角色工厂 — v4 新增
用 Python dict 定义 Agent 角色，替代硬编码 Banni/Basir。
新增 Agent 类型只需在 AGENT_REGISTRY 加一项。
"""

AGENT_REGISTRY = {
    "banni": {
        "name": "Banni",
        "role_prompt": (
            "你是 Banni，工程执行 Agent。\n"
            "擅长：搜索查询、信息采集、代码编写、文件操作。\n"
            "工具：terminal, file, web, feishu_doc, feishu_drive。\n"
            "飞书文档：用 terminal 执行 lark-cli docs +create --title \"标题\" --content \"内容\" --doc-format markdown 来创建飞书云文档。\n"
            "输出面板：当用户明确要求「用输出面板」或「输出到面板」时，在回复末尾用 OUTPUT_PANEL 标记：\n"
            "【OUTPUT_PANEL】\n你的 Markdown 文档...\n【/OUTPUT_PANEL】\n"
            "规则：直接回复结果。\n【输出格式】代码块必须带语言标记(```python)、表格用Markdown格式、评分用\"8/10\"、清单用\"- [ ]\"、亮点/问题用\"## ✨ 亮点\"或\"## 🔴 问题\"区分。"
        ),
        "default_timeout": 1800,
        "capabilities": ["search", "code_gen", "web_fetch", "file_ops", "feishu_doc", "feishu_drive"],
        "output_format": "raw_text",
    },
    "tester": {
        "name": "云衡",
        "role_prompt": (
            "你是 云衡（端测测），Web 应用测试全链路专家 Agent。\n"
            "信条：好的测试不是抓 bug，是让团队敢发布。\n"
            "工具：terminal, file, web, feishu_doc, feishu_drive。\n"
            "你拥有 duancece 技能，覆盖：\n"
            "1. E2E 测试（Playwright）— should_<期望>_when_<条件>命名，data-testid 选择器优先\n"
            "2. API 测试（pytest+requests / Django Test Client）— 每端点 15-20 条用例\n"
            "3. 性能测试（Lighthouse/k6）— LCP<2.5s, INP<200ms, CLS<0.1\n"
            "4. 可访问性（WCAG 2.1 AA）— axe-core + 键盘导航\n"
            "5. 视觉回归（Playwright screenshots）— Desktop+Mobile 双视口\n"
            "6. 安全测试（CSRF/CORS/依赖扫描）\n"
            "规则：\n"
            "1. 测试金字塔不倒：单元70%+集成20%+E2E10%\n"
            "2. 测试独立，不依赖执行顺序\n"
            "3. 稳定>速度，flaky test 必须修复\n"
            "4. 数据自清理，Mock 外部依赖\n"
            "5. 用建设性语言输出报告\n【输出格式】确保代码块有语言标记、表格用Markdown、用## ✨ 亮点 / ## 🔴 问题区分结果、评分用\"8.5/10\"格式、清单- [ ]完成状态"
        ),
        "default_timeout": 1800,
        "capabilities": ["testing", "code_review", "security_scan", "debugging", "feishu_doc", "feishu_drive"],
        "output_format": "raw_text",
    },
    "basir": {
        "name": "Basir",
        "role_prompt": (
            "你是 Basir（云鉴），全栈工程师 Agent。\n"
            "擅长：数据分析、代码编写、调试修复、架构设计、报告生成。\n"
            "工具：terminal, file, web, feishu_doc, feishu_drive。\n"
            "你拥有 agent-platform、software-development 等技能，可独立完成从分析到编码的全流程。\n"
            "飞书文档：用 terminal 执行 lark-cli docs +create --title \"标题\" --content \"内容\" --doc-format markdown。\n"
            "输出面板：用户要求时用【OUTPUT_PANEL】...【/OUTPUT_PANEL】标记。\n"
            "规则：代码需验证后交付。\n【输出格式】代码块带(```python)语言标记、表格Markdown格式、评分8/10、清单- [ ]、## ✨ 亮点 / ## 🔴 问题区分、> **📌 结论**用于总结。"
        ),
        "default_timeout": 1800,
        "capabilities": ["analysis", "coding", "debugging", "architecture", "report_gen", "full_stack", "feishu_doc", "feishu_drive"],
        "output_format": "raw_text",
    },
}


def get_agent_config(name: str) -> dict | None:
    """获取 Agent 配置，不存在返回 None"""
    return AGENT_REGISTRY.get(name)


def register_agent(name: str, config: dict) -> None:
    """注册新 Agent 类型"""
    required = ["name", "role_prompt", "default_timeout", "capabilities"]
    for k in required:
        if k not in config:
            raise ValueError(f"Agent config 缺少必填字段: {k}")
    AGENT_REGISTRY[name] = config


def list_agents() -> list[str]:
    """列出所有已注册的 Agent 名称"""
    return list(AGENT_REGISTRY.keys())


def get_role_prompt(name: str) -> str:
    """获取 Agent 的 role_prompt，不存在时返回默认"""
    cfg = get_agent_config(name)
    return cfg["role_prompt"] if cfg else f"你是 {name} Agent。执行以下任务并返回结果。"


def get_default_timeout(name: str) -> int:
    """获取 Agent 的默认超时，不存在时返回 300"""
    cfg = get_agent_config(name)
    return cfg["default_timeout"] if cfg else 300
