#!/usr/bin/env python3
"""
事件驱动消息 Worker — 线程池 + DeepSeek API 直调
在 agent-platform 收到用户消息时即时处理，延迟 < 2 秒
"""
import os
import json
import time
import requests
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Optional

# ── 配置 ──
# Key 统一由 systemd Environment= 或 ~/.hermes/.env 管理，代码不读文件
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
MODEL = "deepseek-chat"

if not DEEPSEEK_API_KEY:
    raise RuntimeError("DEEPSEEK_API_KEY not set in environment")
MODEL = "deepseek-chat"
AGENT_PLATFORM_URL = "http://localhost:8001"
RELAY_SCRIPT = os.path.expanduser(
    "~/.hermes/profiles/Banni/scripts/relay_feishu.py"
)
MAX_WORKERS = 3

# 线程池
_executor = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="msg-worker")

from context_aggregator import aggregate_cross_source_context


def _call_deepseek(messages: list, system_prompt: str = None, model: str = None) -> Optional[str]:
    """调用 DeepSeek API（OpenAI 兼容格式）"""
    msgs = []
    if system_prompt:
        msgs.append({"role": "system", "content": system_prompt})
    msgs.extend(messages)

    try:
        resp = requests.post(
            DEEPSEEK_URL,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": model or MODEL,
                "messages": msgs,
                "temperature": 0.7,
                "max_tokens": 2000,
            },
            timeout=60,
        )
        data = resp.json()
        if "error" in data:
            print(f"[Worker] API error: {data['error']}")
            return None
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[Worker] DeepSeek error: {e}")
        return None


def _save_reply(conversation_id: int, content: str, source: str = "web") -> Optional[int]:
    """保存回复到 agent-platform"""
    try:
        resp = requests.post(
            f"{AGENT_PLATFORM_URL}/api/messages/",
            json={
                "conversation": conversation_id,
                "role": "agent",
                "content": content,
                "source": source,
                "processed": True,
            },
            timeout=10,
        )
        return resp.json().get("id")
    except Exception as e:
        print(f"[Worker] Save reply error: {e}")
        return None


def _mark_processed(message_ids: list):
    """标记消息为已处理"""
    try:
        requests.post(
            f"{AGENT_PLATFORM_URL}/api/messages/mark-processed/",
            json={"ids": message_ids},
            timeout=10,
        )
    except Exception as e:
        print(f"[Worker] Mark processed error: {e}")


def _send_feishu(chat_id: str, content: str) -> bool:
    """通过 relay_feishu.py 发送飞书消息"""
    import subprocess
    try:
        result = subprocess.run(
            ["python3", RELAY_SCRIPT, chat_id, content],
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode == 0
    except Exception as e:
        print(f"[Worker] Feishu send error: {e}")
        return False


SYSTEM_PROMPT_DEFAULT = """你是 云筑(Banni)，工程执行 Agent。友好、高效、直接。中文回答。

【应答机制】你必须主动汇报进度：
1. 收到任务先确认：「已收到，正在处理...」
2. 每完成一步报告进度（如：「✅ 第1步完成，开始第2步...」）
3. 遇到阻塞或需要决策时立即说明
4. 完成后给出总结
不要沉默执行。

你有以下能力：
- 回答问题和提供建议
- 输出文档/报告：在回复末尾用标记推送内容到用户的输出面板：
  【OUTPUT_PANEL】
  内容...
  【/OUTPUT_PANEL】

保持简洁。"""


def _get_system_prompt(msg: dict, conversation_id: Optional[int] = None, current_content: str = "") -> str:
    """根据 Agent portrait + USER.md/MEMORY.md + 跨端上下文构建系统提示"""
    portrait = msg.get('agent_portrait', '')
    
    # 注入 USER.md + MEMORY.md（从 Banni profile 读取）
    profile_dir = os.path.expanduser('~/.hermes/profiles/Banni/memories')
    memory_parts = []
    
    user_file = os.path.join(profile_dir, 'USER.md')
    if os.path.exists(user_file):
        with open(user_file) as f:
            uc = f.read().strip()
        if uc:
            memory_parts.append(f'【用户信息】\n{uc}')
    
    mem_file = os.path.join(profile_dir, 'MEMORY.md')
    if os.path.exists(mem_file):
        with open(mem_file) as f:
            mc = f.read().strip()
        if mc:
            memory_parts.append(f'【你的记忆与知识】\n{mc}')
    
    # 聚合跨端上下文（飞书 + Web 最近消息）
    cross_ctx = ""
    if conversation_id:
        try:
            cross_ctx = aggregate_cross_source_context(conversation_id, current_content)
        except Exception:
            pass
    
    base = portrait if portrait else SYSTEM_PROMPT_DEFAULT
    parts = [base]
    if cross_ctx:
        parts.append(cross_ctx)
    if memory_parts:
        parts.extend(memory_parts)
    
    return '\n\n---\n\n'.join(parts)


def process_message(msg_id: int, conversation_id: int, content: str,
                    source: str, feishu_chat_id: str, history: list,
                    system_prompt: str = None, model: str = None):
    """
    处理单条消息（在线程中运行）
    """
    import traceback
    log_msgs = []
    start = time.time()

    try:
        # 构建消息历史
        messages = []
        for h in history:
            role = "user" if h["role"] == "user" else "assistant"
            messages.append({"role": role, "content": h["content"]})
        messages.append({"role": "user", "content": content})

        sp = system_prompt or SYSTEM_PROMPT_DEFAULT
        used_model = model or MODEL
        log_msgs.append(f"agent={sp[:30]}... model={used_model}")

        # 调 API
        reply = _call_deepseek(messages, sp, used_model)
        if not reply:
            reply = "抱歉，处理出错了，请稍后再试。"

        elapsed = time.time() - start
        log_msgs.append(f"#{msg_id} done ({elapsed:.1f}s) → {reply[:50]}")

        # 保存回复
        _save_reply(conversation_id, reply)

        # 飞书发送
        if source == "feishu" and feishu_chat_id:
            _send_feishu(feishu_chat_id, reply)

        # 标记已处理
        _mark_processed([msg_id])

    except Exception as e:
        log_msgs.append(f"FATAL: {e}\n{traceback.format_exc()}")
        # 确保标记失败的消息不被重复处理
        try:
            _save_reply(conversation_id, "抱歉，处理出错了，请稍后再试。")
            _mark_processed([msg_id])
        except:
            pass

    # 写日志文件
    try:
        with open("/tmp/worker.log", "a") as f:
            f.write(" | ".join(log_msgs) + "\n")
    except:
        pass


def handle_message_async(msg: dict):
    """
    异步处理消息（立即返回，不阻塞 HTTP 响应）
    msg 格式来自 agent-platform pending API
    """
    # 从 Agent portrait 构建系统提示
    system_prompt = _get_system_prompt(
        msg,
        conversation_id=msg.get("conversation_id"),
        current_content=msg.get("content", ""),
    )
    model = msg.get('agent_model', MODEL)
    _executor.submit(
        process_message,
        msg_id=msg["id"],
        conversation_id=msg["conversation_id"],
        content=msg["content"],
        source=msg.get("source", "web"),
        feishu_chat_id=msg.get("feishu_chat_id", ""),
        history=msg.get("history", []),
        system_prompt=system_prompt,
        model=model,
    )


# 测试入口
if __name__ == "__main__":
    # 拉取 pending 并处理
    resp = requests.get(f"{AGENT_PLATFORM_URL}/api/messages/pending/", timeout=10)
    data = resp.json()
    msgs = data.get("messages", [])
    print(f"Pending: {len(msgs)} 条")
    for msg in msgs:
        handle_message_async(msg)
    # 等待线程完成
    _executor.shutdown(wait=True)
    print("全部处理完毕")
