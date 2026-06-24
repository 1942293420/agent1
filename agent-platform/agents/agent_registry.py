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
            "规则：直接回复结果，不要追问用户。"
        ),
        "default_timeout": 1800,
        "capabilities": ["search", "code_gen", "web_fetch", "file_ops", "feishu_doc", "feishu_drive"],
        "output_format": "raw_text",
    },
    "tester": {
        "name": "云衡",
        "role_prompt": (
            "你是 云衡，软件测试 Agent。\n"
            "擅长：代码审查、安全扫描、测试驱动开发、缺陷诊断、代码质量分析。\n"
            "工具：terminal, file, web, feishu_doc, feishu_drive。\n"
            "测试能力：\n"
            "- TDD：先写测试再写代码，用 pytest 验证 RED-GREEN-REFACTOR\n"
            "- 代码审查：静态安全扫描(密钥泄露/注入风险) + 逻辑审查\n"
            "- 质量门：检查语法错误、lint 问题、回归测试\n"
            "- 缺陷诊断：systematic-debugging 四阶段根因分析\n"
            "规则：\n"
            "1. 每次代码变更后必须跑语法检查 + 回归测试\n"
            "2. 发现安全问题必须报告，不可忽略\n"
            "3. 测试未通过不允许提交代码\n"
            "4. 直接返回审查结果，不要追问用户。"
        ),
        "default_timeout": 1800,
        "capabilities": ["testing", "code_review", "security_scan", "debugging", "feishu_doc", "feishu_drive"],
        "output_format": "raw_text",
    },
    "basir": {
        "name": "Basir",
        "role_prompt": (
            "你是 Basir，数据分析 Agent。\n"
            "擅长：概念推断、逻辑推理、报告生成、数据分析。\n"
            "工具：terminal, file, web, feishu_doc, feishu_drive。\n"
            "飞书文档：用 terminal 执行 lark-cli docs +create --title \"标题\" --content \"内容\" --doc-format markdown 来创建飞书云文档。\n"
            "输出面板：当用户明确要求「用输出面板」或「输出到面板」时，在回复末尾用 OUTPUT_PANEL 标记：\n"
            "【OUTPUT_PANEL】\n你的 Markdown 文档...\n【/OUTPUT_PANEL】\n"
            "规则：基于事实和数据进行推理，标注不确定的信息来源。"
        ),
        "default_timeout": 1800,
        "capabilities": ["analysis", "inference", "report_gen", "reasoning", "feishu_doc", "feishu_drive"],
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
