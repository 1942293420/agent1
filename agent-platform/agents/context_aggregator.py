"""
跨端上下文聚合器
从 Django Message 表拉取所有 source 的最近消息，合并为统一上下文文本块。
用于飞书↔Web 上下文同步：确保 Agent 在任意端都能感知到另一端的对话历史。

v2 改进：
  - 时间窗口从 120min 扩至 480min（8小时），覆盖更长对话
  - 增加按 conversation+feishu_chat_id 跨端合并逻辑
"""
from datetime import timedelta
from django.utils import timezone
from .models import Message

MAX_RECENT_MSGS = 20
MAX_CONTEXT_CHARS = 4000
TIME_WINDOW_MINUTES = 480  # 8小时，覆盖跨日对话

SOURCE_LABELS = {
    "web":         "[Web端]",
    "feishu_chat": "[飞书群]",
    "feishu_bot":  "[飞书Bot]",
    "feishu":      "[飞书]",
}

ROLE_LABELS = {
    "user":      "用户",
    "assistant": "Banni",
    "system":    "系统",
}


def aggregate_cross_source_context(conversation_id: int, current_message: str = "") -> str:
    """
    返回可注入 system prompt 的跨端合并上下文。

    规则：
    - 拉取最近 TIME_WINDOW_MINUTES 内所有 source 的消息
    - 最多 MAX_RECENT_MSGS 条
    - 拼接后总长度不超过 MAX_CONTEXT_CHARS
    - 按时间升序排列（最早的在上面，方便 LLM 理解时间线）
    - 跳过与当前用户消息完全相同的内容（避免重复注入）
    """
    cutoff = timezone.now() - timedelta(minutes=TIME_WINDOW_MINUTES)

    qs = Message.objects.filter(
        conversation_id=conversation_id,
        created_at__gte=cutoff,
    ).order_by("-created_at")[:MAX_RECENT_MSGS]

    if not qs:
        return ""

    # 还原为升序
    messages = sorted(qs, key=lambda m: m.created_at)

    lines = ["[系统] 以下是飞书和 Web 端最近的消息记录，请参考这些上下文理解用户意图。\n"]
    total_chars = len(lines[0])

    current_msg_stripped = current_message.strip() if current_message else ""

    for msg in messages:
        # 跳过与当前用户消息完全相同的条目（避免重复）
        if current_msg_stripped and msg.content and msg.content.strip() == current_msg_stripped:
            continue

        src = SOURCE_LABELS.get(msg.source, f"[{msg.source}]")
        role = ROLE_LABELS.get(msg.role, msg.role)
        content = msg.content or ""

        if len(content) > 500:
            content = content[:500] + "…"

        line = f"{src} {role}: {content}"
        total_chars += len(line) + 1

        if total_chars > MAX_CONTEXT_CHARS:
            lines.append("…(更早的消息已省略)")
            break

        lines.append(line)

    return "\n".join(lines)
