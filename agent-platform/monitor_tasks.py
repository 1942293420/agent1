#!/usr/bin/env python3
"""AgentOS 任务监控 — 每 5 秒轮询，检测新建/状态变化"""
import json, time, sys, requests

API = "http://localhost:8001/api/tasks/"
last_state = {}

def poll():
    global last_state
    try:
        resp = requests.get(API, params={"page_size": 50, "ordering": "-created_at"}, timeout=5)
        tasks = resp.json().get("results", [])
    except Exception as e:
        print(f"[monitor] API 不可达: {e}", flush=True)
        return

    for t in tasks:
        tid = t["id"]
        status = t["status"]
        title = t["title"][:50]
        is_orch = t.get("contract", {}).get("orchestrator", False)
        prev = last_state.get(tid)

        if prev is None:
            print(f"🆕 Task#{tid} [{status}] {'🎯云枢' if is_orch else ''} {title}", flush=True)
        elif prev["status"] != status:
            emoji = {"in_progress": "⚙️", "completed": "✅", "failed": "❌", "pending": "⏳"}.get(status, "🔄")
            print(f"{emoji} Task#{tid} {prev['status']}→{status} {'🎯云枢' if is_orch else ''} {title}", flush=True)

        last_state[tid] = {"status": status}

print("🔍 AgentOS 任务监控已启动 (每5秒扫描)", flush=True)
print(f"   后端: {API}", flush=True)
print("   符号: 🆕新建 ⚙️执行中 ✅完成 ❌失败 🎯云枢调度", flush=True)
print("=" * 60, flush=True)

poll()  # 初始快照
while True:
    time.sleep(5)
    poll()
