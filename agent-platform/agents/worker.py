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
# 读 Hermes .env 中的 DEEPSEEK_API_KEY（和 Hermes 用同一个 key）
import subprocess
def _get_deepseek_key():
    """从 Hermes .env 或环境变量获取 DeepSeek API Key"""
    env_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if env_key and len(env_key) > 10:
        return env_key
    # fallback: 读 .env 文件
    env_file = os.path.expanduser("~/.hermes/profiles/feishu-bot2/.env")
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                if line.startswith("DEEPSEEK_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return "sk-c58625db02854c549dc6e13c0347b7f0"  # 兜底

DEEPSEEK_API_KEY = _get_deepseek_key()
# 直接调 DeepSeek API（不经过本地 proxy，避免格式翻译）
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
MODEL = "deepseek-chat"
AGENT_PLATFORM_URL = "http://localhost:8001"
RELAY_SCRIPT = os.path.expanduser(
    "~/.hermes/profiles/feishu-bot2/scripts/relay_feishu.py"
)
MAX_WORKERS = 3

# 线程池
_executor = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="msg-worker")


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


SYSTEM_PROMPT_DEFAULT = """你是小温，范先生的飞书助手。友好、高效、直接。中文回答。
你有以下能力：
- 回答问题和提供建议
- 查找文件、执行命令（需要通过 Hermes 工具，本 Worker 只能做纯文本回复）
- 如果你需要执行命令或操作文件，请告知用户你正在排队处理，然后消息会转交 Hermes 处理。

保持简洁。"""


def _get_system_prompt(msg: dict) -> str:
    """根据 Agent portrait 构建系统提示，fallback 到默认小温"""
    portrait = msg.get('agent_portrait', '')
    if portrait:
        return portrait
    return SYSTEM_PROMPT_DEFAULT


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
    system_prompt = _get_system_prompt(msg)
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
