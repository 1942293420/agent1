"""
RQ Worker — 事件驱动消息处理
启动: cd ~/projects/agent-platform && source venv/bin/activate && python agents/rq_worker.py
"""
import os
import sys
import json
import time
import requests

# ── 配置 ──
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
AGENT_PLATFORM = "http://localhost:8001"
RELAY_SCRIPT = os.path.expanduser("~/.hermes/profiles/feishu-bot2/scripts/relay_feishu.py")

# DeepSeek — 通过本地 proxy（Anthropic 格式 → DeepSeek）
PROXY_URL = "http://localhost:4000/v1/messages"
PROXY_KEY = "sk-anthropic-proxy"

SYSTEM_PROMPT = """你是小温，范先生的飞书助手。友好、高效、直接。中文回答。
你有以下能力：回答问题、提供建议、执行命令、操作文件。
保持简洁。"""


def call_llm(messages: list) -> str:
    """通过 Anthropic→DeepSeek 代理调用 LLM"""
    body = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 2000,
        "temperature": 0.7,
        "system": SYSTEM_PROMPT,
        "messages": messages,
    }
    resp = requests.post(
        PROXY_URL,
        headers={"Authorization": f"Bearer {PROXY_KEY}", "Content-Type": "application/json"},
        json=body,
        timeout=60,
    )
    if resp.status_code != 200:
        raise Exception(f"LLM error {resp.status_code}: {resp.text[:200]}")
    
    data = resp.json()
    parts = data.get("content", [])
    text = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
    return text


def process_message(msg_id: int):
    """
    处理单条消息（RQ job）
    1. 从 agent-platform 拉取消息详情
    2. 调 LLM 生成回复
    3. 写回 agent-platform
    4. 飞书消息额外发送到飞书
    """
    start = time.time()

    # 1. 拉取消息
    resp = requests.get(f"{AGENT_PLATFORM}/api/messages/pending/", timeout=10)
    data = resp.json()
    msgs = data.get("messages", [])
    
    target = None
    for m in msgs:
        if m["id"] == msg_id:
            target = m
            break
    
    if not target:
        print(f"[Worker] 消息 #{msg_id} 未找到（可能已被处理）")
        return

    # 2. 构建对话
    anthropic_msgs = []
    for h in target.get("history", []):
        role = "user" if h["role"] == "user" else "assistant"
        anthropic_msgs.append({"role": role, "content": h["content"]})
    anthropic_msgs.append({"role": "user", "content": target["content"]})

    # 3. 调 LLM
    try:
        reply = call_llm(anthropic_msgs)
    except Exception as e:
        print(f"[Worker] LLM 调用失败: {e}")
        reply = f"抱歉，处理出错了：{e}"

    elapsed = time.time() - start
    print(f"[Worker] #{msg_id} ({elapsed:.1f}s) → {reply[:60]}...")

    # 4. 写回
    requests.post(f"{AGENT_PLATFORM}/api/messages/", json={
        "conversation": target["conversation_id"],
        "role": "agent",
        "content": reply,
        "source": "web",
        "processed": True,
    }, timeout=10)

    # 5. 飞书发送
    if target.get("source") == "feishu" and target.get("feishu_chat_id"):
        import subprocess
        subprocess.run(
            ["python3", RELAY_SCRIPT, target["feishu_chat_id"], reply],
            capture_output=True, timeout=30,
        )

    # 6. 标记已处理
    requests.post(f"{AGENT_PLATFORM}/api/messages/mark-processed/",
                  json={"ids": [msg_id]}, timeout=10)

    print(f"[Worker] #{msg_id} 全部完成")


# ── RQ 启动入口 ──
if __name__ == "__main__":
    from redis import Redis
    from rq import Worker, Queue

    redis_conn = Redis.from_url(REDIS_URL)
    queue = Queue("messages", connection=redis_conn)

    worker = Worker([queue], connection=redis_conn)
    worker.work()
