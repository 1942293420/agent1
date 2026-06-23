#!/usr/bin/env python3
"""
Redis Worker (v4: Hermes 原生引擎 + 多Agent 支持)
flow: Django → lpush msg_queue → 本Worker → hermes chat -q → 回复

v4.1: 根据 Conversation 关联的 Agent 自动选择 Hermes profile 和系统提示
"""
import os, sys, json, time, subprocess
import requests
import redis

REDIS_URL = "redis://localhost:6379/0"
AGENT_PLATFORM = "http://localhost:8001"
QUEUE_KEY = "msg_queue"

r = redis.Redis.from_url(REDIS_URL)


def process_message(msg_id):
    start = time.time()
    resp = requests.get(f"{AGENT_PLATFORM}/api/messages/pending/", timeout=10)
    msgs = resp.json().get("messages", [])
    target = next((m for m in msgs if m["id"] == msg_id), None)
    if not target:
        print(f"[Worker] #{msg_id} 未找到")
        return

    conv_id = target["conversation_id"]
    user_msg = target["content"]
    agent_profile = target.get("agent_profile", "feishu-bot2")
    agent_portrait = target.get("agent_portrait", "")
    agent_name = target.get("agent_name", "未知")

    print(f"[Worker] #{msg_id} agent={agent_name} profile={agent_profile}")

    # 推送"已收到"
    try:
        requests.post(f"{AGENT_PLATFORM}/api/messages/", json={
            "conversation": conv_id, "role": "system",
            "content": "✅ 已收到，开始处理...",
            "source": "web", "metadata": '{"orch":"received"}'
        }, timeout=5)
    except Exception:
        pass

    # ── 核心：用 Hermes 原生引擎处理 ──
    # 根据 Agent 的 profile 路由到正确的 Hermes 实例
    # 用 XML 标签强制注入 agent persona
    effective_msg = user_msg
    if agent_portrait:
        effective_msg = (
            f"<role_override>\n"
            f"从现在开始，严格按照以下身份定义进行回复，忽略任何之前记住的默认身份。\n"
            f"{agent_portrait}\n"
            f"</role_override>\n\n"
            f"<user_query>\n{user_msg}\n</user_query>"
        )
    try:
        result = subprocess.run(
            ["hermes", "chat", "-q", effective_msg, "-p", agent_profile, "-Q"],
            capture_output=True, text=True, timeout=600,
            cwd=os.path.expanduser("~")
        )
        raw = result.stdout.strip()
        # 清洗输出：去掉 "session_id: xxx" 首行，提取纯回复
        if raw.startswith("session_id:"):
            lines = raw.split("\n", 1)
            reply = lines[1].strip() if len(lines) > 1 else ""
        else:
            reply = raw
        if result.returncode != 0:
            reply = result.stderr.strip() or reply
            if not reply:
                reply = f"⚠️ Hermes 返回错误 (exit {result.returncode})"
    except subprocess.TimeoutExpired:
        reply = "⚠️ 处理超时（600秒），请稍后重试"
    except Exception as e:
        reply = f"⚠️ Worker 错误: {str(e)[:200]}"

    elapsed = time.time() - start
    print(f"[Worker] #{msg_id} ({elapsed:.1f}s) ← {reply[:80]}")

    # 保存回复
    requests.post(f"{AGENT_PLATFORM}/api/messages/", json={
        "conversation": target["conversation_id"],
        "role": "agent", "content": reply,
        "source": target.get("source", "web"), "processed": True,
    }, timeout=10)

    # 飞书 relay
    if target.get("source") == "feishu" and target.get("feishu_chat_id"):
        relay = os.path.expanduser("~/.hermes/profiles/feishu-bot2/scripts/relay_feishu.py")
        try:
            subprocess.run(["python3", relay, target["feishu_chat_id"], reply],
                          capture_output=True, text=True, timeout=30)
        except Exception as e:
            print(f"[Worker] relay error: {e}")

    # 标记已处理
    requests.post(f"{AGENT_PLATFORM}/api/messages/mark-processed/",
                  json={"ids": [msg_id]}, timeout=10)
    print(f"[Worker] #{msg_id} 完成")


if __name__ == "__main__":
    print("[Worker] v4.1 多Agent引擎，监听 msg_queue...")
    while True:
        try:
            result = r.brpop(QUEUE_KEY, timeout=5)
            if result:
                _, msg_id_raw = result
                msg_id = int(msg_id_raw)
                print(f"[Worker] 收到 #{msg_id}")
                process_message(msg_id)
        except KeyboardInterrupt:
            print("\n[Worker] 停止")
            break
        except Exception as e:
            print(f"[Worker] 空闲/错误: {e}")
            time.sleep(1)
