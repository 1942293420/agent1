#!/usr/bin/env python3
"""
Redis Worker v7.0: 多Agent协同 — 完整状态机 + 五维监控 + 云枢决策
"""
import os, sys, json, time, subprocess, threading, re, signal, psutil
import requests
import redis

REDIS_URL = "redis://localhost:6379/0"
AGENT_PLATFORM = "http://localhost:8001"
TASK_TIMEOUT = 600
HERMES_TIMEOUT = 600
CHILD_TIMEOUT = 300
CHILD_HEARTBEAT_MAX_GAP = 120  # 心跳最大间隔
CHILD_STALL_SECONDS = 180      # 输出停滞判定
CHILD_MAX_PROGRESS = 1000      # 单子任务最大进度事件
CHILD_MEMORY_LIMIT_MB = 4096   # 内存上限
QUEUE_BACKLOG_WARN = 100

QUEUE_KEY = "msg_queue"
r = redis.Redis.from_url(REDIS_URL)

import yunshu_io

def _api(path, method="get", data=None):
    try:
        fn = {"get": requests.get, "post": requests.post, "patch": requests.patch}[method]
        r = fn(f"http://localhost:8001/api/{path}", json=data, timeout=10) if method != "get" else             fn(f"http://localhost:8001/api/{path}", timeout=10)
        return r.json()
    except:
        return {}

def _run_hermes(msg, profile):
    r = subprocess.run(["hermes","chat","-q",msg,"-p",profile,"-Q","--yolo"],
        capture_output=True,text=True,timeout=HERMES_TIMEOUT,cwd=os.path.expanduser("~"))
    raw = r.stdout.strip()
    if raw.startswith("session_id:"):
        raw = raw.split("\n",1)[1].strip() if "\n" in raw else ""
    return raw or r.stderr.strip() or f"⚠️ exit {r.returncode}"

def _parse_plan(reply):
    m = re.search(r'<plan>\s*(\{.*?\})\s*</plan>', reply, re.DOTALL)
    if not m: return None
    try: return json.loads(m.group(1))
    except: return None


def _parse_decision(reply):
    """解析云枢的 <decision> JSON"""
    m = re.search(r'<decision>\s*(\{.*?\})\s*</decision>', reply, re.DOTALL)
    if not m: return None
    try: return json.loads(m.group(1))
    except: return None


# ══════ 五维监控 + 僵尸保护 ══════

def _child_guard(child_id, proc, msg_id):
    """包装子进程：心跳线程 + 资源监控 + 超时保护 + 僵尸清理"""
    stop = threading.Event()
    progress_seq = [0]

    def heartbeat_loop():
        while not stop.is_set():
            try:
                _api(f"child-tasks/{child_id}/heartbeat/", 'post')
            except: pass
            time.sleep(10)

    def resource_monitor():
        try:
            p = psutil.Process(proc.pid)
            while not stop.is_set():
                try:
                    mem_mb = p.memory_info().rss / 1024 / 1024
                    if mem_mb > CHILD_MEMORY_LIMIT_MB:
                        print(f"[Worker] #{msg_id} child={child_id} 内存超限 {mem_mb:.0f}MB > {CHILD_MEMORY_LIMIT_MB}MB")
                        proc.terminate()
                        time.sleep(10)
                        if proc.poll() is None:
                            proc.kill()
                        stop.set()
                        break
                except psutil.NoSuchProcess:
                    break
                time.sleep(15)
        except: pass

    hb = threading.Thread(target=heartbeat_loop, daemon=True)
    rm = threading.Thread(target=resource_monitor, daemon=True)
    hb.start()
    rm.start()

    try:
        stdout, stderr = proc.communicate(timeout=CHILD_TIMEOUT)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
        stop.set()
        hb.join(2); rm.join(2)
        _api(f"child-tasks/{child_id}/", 'patch', {
            "status": "TIMED_OUT",
            "error_info": {"type":"TIMEOUT","seconds":CHILD_TIMEOUT}
        })
        return f"⚠️ 子任务超时({CHILD_TIMEOUT}s)"

    stop.set()
    hb.join(2); rm.join(2)

    raw = (stdout or "").strip()
    if raw.startswith("session_id:"):
        raw = raw.split("\n",1)[1].strip() if "\n" in raw else raw
    result = raw or (stderr or "").strip() or "(无输出)"

    if proc.returncode == 0:
        _api(f"child-tasks/{child_id}/", 'patch', {"status":"DONE","result":result})
    else:
        _api(f"child-tasks/{child_id}/", 'patch', {
            "status":"FAILED","result":result,
            "error_info":{"exit_code":proc.returncode}
        })
    return result


# ══════ 消息处理 ══════

def process_message(msg_id):
    """文本协议版：启动云枢 Hermes → 拦截 stdout 命令 → 执行 → 回复"""
    start = time.time()
    print(f"[Worker] #{msg_id} 开始")

    resp = requests.get(f"{AGENT_PLATFORM}/api/messages/pending/?limit=50", timeout=10)
    target = next((m for m in resp.json().get("messages", []) if m["id"] == msg_id), None)
    if not target:
        print(f"[Worker] #{msg_id} 未找到"); return

    conv_id = target["conversation_id"]
    user_msg = target["content"]
    agent_profile = target.get("agent_profile", "banni")

    # 创建父任务
    pt = _api("parent-tasks/", 'post', {
        "conversation_id": conv_id, "user_message": user_msg,
        "source": target.get("source", "web")
    })
    parent_id = pt.get("id")
    if not parent_id:
        print(f"[Worker] #{msg_id} 创建父任务失败"); return

    _push_msg(conv_id, "✅ 已收到，云枢调度中...", "received")

    # ── 文本协议：启动云枢，拦截命令 ──
    final_reply = yunshu_io.run_yunshu_session(parent_id, conv_id, user_msg, agent_profile)

    # 保存回复
    if final_reply:
        _save_reply(target, final_reply)
    _mark_processed(msg_id)
    _relay_feishu(target)

    elapsed = time.time() - start
    print(f"[Worker] #{msg_id} ({elapsed:.1f}s) parent={parent_id}")

    try:
        requests.post(f"{AGENT_PLATFORM}/api/messages/", json={
            "conversation":conv_id,"role":"system","content":content,
            "source":"web","metadata":json.dumps({"orch":orch})
        }, timeout=5)
    except: pass

def _push_msg(conv_id, content, orch="summarizing"):
    try:
        requests.post(f"http://localhost:8001/api/messages/", json={
            "conversation":conv_id,"role":"system","content":content,
            "source":"web","metadata":json.dumps({"orch":orch})
        }, timeout=5)
    except: pass

def _save_reply(target, reply):
    try:
        requests.post(f"{AGENT_PLATFORM}/api/messages/", json={
            "conversation":target["conversation_id"],"role":"agent",
            "content":reply,"source":target.get("source","web"),"processed":True
        }, timeout=10)
    except: pass

def _mark_processed(msg_id):
    try:
        requests.post(f"{AGENT_PLATFORM}/api/messages/mark-processed/",
                      json={"ids":[msg_id]}, timeout=10)
    except: pass

def _relay_feishu(target):
    if target.get("source")!="feishu" or not target.get("feishu_chat_id"): return
    try:
        subprocess.run(["python3",
            os.path.expanduser("~/.hermes/profiles/banni/scripts/relay_feishu.py"),
            target["feishu_chat_id"], target.get("content","")],
            capture_output=True,text=True,timeout=30)
    except: pass


# ══════ 主循环 ══════

if __name__ == "__main__":
    from concurrent.futures import ThreadPoolExecutor
    MAX_WORKERS = 20


    print(f"[Worker] v7.0 ({MAX_WORKERS} workers, child_timeout={CHILD_TIMEOUT}s)")
    print(f"[Worker] 监听 msg_queue...")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {}
        while True:
            try:
                done = [f for f in futures if f.done()]
                for f in done:
                    mid, _ = futures.pop(f)
                    try:
                        f.result(timeout=0)
                    except Exception as e:
                        print(f"[Worker] #{mid} 异常: {e}")

                qlen = r.llen(QUEUE_KEY)
                if qlen > QUEUE_BACKLOG_WARN:
                    print(f"[Worker] 积压: {qlen}")

                result = r.brpop(QUEUE_KEY, timeout=5)
                if result:
                    _, raw = result
                    mid = int(raw)
                    print(f"[Worker] 收到 #{mid} (活跃={len(futures)}/{MAX_WORKERS}, 队列={qlen})")
                    if qlen > QUEUE_BACKLOG_WARN * 5:
                        print(f"[Worker] 严重积压 跳过")
                        continue
                    future = pool.submit(process_message, mid)
                    futures[future] = (mid, time.time())

            except KeyboardInterrupt:
                print("\n[Worker] 停止")
                for f in futures:
                    f.cancel()
                break
            except Exception as e:
                print(f"[Worker] 主循环: {e}")
                time.sleep(1)
