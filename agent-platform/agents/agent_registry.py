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
            "规则：直接回复结果，不要追问用户。使用 --yolo 模式运行。"
        ),
        "default_timeout": 1800,
        "capabilities": ["search", "code_gen", "web_fetch", "file_ops"],
        "output_format": "raw_text",
    },
    "basir": {
        "name": "Basir",
        "role_prompt": (
            "你是 Basir，数据分析 Agent。\n"
            "擅长：概念推断、逻辑推理、报告生成、数据分析。\n"
            "规则：基于事实和数据进行推理，标注不确定的信息来源。"
        ),
        "default_timeout": 1800,
        "capabilities": ["analysis", "inference", "report_gen", "reasoning"],
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
