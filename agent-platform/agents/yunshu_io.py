"""
Worker 文本协议 v4 — Yunshu I/O 循环
PLAN → SPAWN → WAIT → REFLECT → REPLY
"""
import subprocess, threading, time, re, os, json
from agent_registry import get_role_prompt, get_default_timeout
from plan_parser import PlanGraph
from checkpoint import CheckpointManager


# ══════ 命令匹配 v4 ══════
CMD_PATTERNS = {
    # v3 原有
    "SPAWN_BANNI": re.compile(r"^SPAWN_BANNI\s*:?\s*(.+)", re.I),
    "SPAWN_BASIR": re.compile(r"^SPAWN_BASIR\s*:?\s*(.+)", re.I),
    "CHECK":       re.compile(r"^CHECK\s+(\S+)", re.I),
    "WAIT_ALL":    re.compile(r"^WAIT_ALL", re.I),
    "KILL":        re.compile(r"^KILL\s+(\S+)", re.I),
    "REPLY":       re.compile(r"^REPLY\s*:?\s*(.+)", re.I | re.S),
    # v4 新增
    "PLAN":        re.compile(r"^PLAN\s*:?\s*(.*)", re.I),
    "REFLECT":     re.compile(r"^REFLECT\s*$", re.I),
    "REFLECT_PASS": re.compile(r"^REFLECT_PASS", re.I),
    "REFLECT_FAIL": re.compile(r"^REFLECT_FAIL\s*:?\s*(.+)", re.I),
}


class ReflectState:
    """REFLECT 模式状态机"""
    MAX_ROUNDS = 3

    def __init__(self):
        self.current_round = 0
        self.passed = False
        self.fail_reason = ""
        self._in_reflect = False

    @property
    def active(self): return self._in_reflect

    def enter(self): self._in_reflect = True

    def mark_pass(self):
        self.passed = True
        self._in_reflect = False

    def mark_fail(self, reason=""):
        self.current_round += 1
        self.fail_reason = reason
        if self.current_round >= self.MAX_ROUNDS:
            self._in_reflect = False
            return "FORCE_PASS"
        self._in_reflect = False
        return "FAIL"

    def get_checklist_prompt(self, children, user_message):
        lines = [
            "[REFLECT 自检模式]",
            f"用户需求: {user_message[:200]}",
            "",
            "子任务结果:",
        ]
        for tid, entry in children.items():
            obj = entry.get("obj")
            if obj:
                marker = f"[{obj.get('agent_name', '?')}|{tid}]"
                preview = (obj.get('result') or obj.get('error_info') or "")[:150]
                lines.append(f"  {marker} {obj.get('status', '?')}: {preview}")
        lines.extend([
            "",
            "请逐项检查:",
            "1. 事实是否有子Agent输出支撑？",
            "2. 修正是否完成？",
            "3. 是否遗漏用户需求？",
            "4. 结构是否完整？",
            "5. 是否有可操作建议？",
            "",
            "全部通过 → REFLECT_PASS",
            "未通过 → REFLECT_FAIL: <原因> <修正行动>",
        ])
        return "\n".join(lines)


class YunshuCommandHandler:
    def __init__(self, parent_id, conv_id, agent_profile="banni"):
        self.parent_id = parent_id
        self.conv_id = conv_id
        self.profile = agent_profile
        self.children = {}
        self._max_spawn = 3  # 护栏上限，PLAN 可调整
        self._absolute_max = 8
        self._in_reflect = False
        self.reflect_state = ReflectState()
        self._checkpoint_mgr = CheckpointManager(parent_id)

    def _guard_spawn(self):
        active = sum(1 for c in self.children.values()
                     if c["proc"].poll() is None)
        if active >= self._max_spawn:
            return f"ERROR 已达子任务上限(最多{self._max_spawn}个)"
        return None

    # ── PLAN ──
    def handle_plan(self, plan_text):
        plan = PlanGraph.parse(plan_text)
        if not plan:
            return "ERROR PLAN 解析失败"
        if not plan.validate():
            return "ERROR PLAN 依赖图有环或 task_id 重复"

        self._max_spawn = min(plan.get_suggested_max_spawn(), self._absolute_max)
        self._checkpoint_mgr.write_checkpoint(
            "PLAN_COMPLETED",
            {tid: {"status": "PENDING"} for tid in plan.adjacency}
        )
        return (f"OK plan_parsed: {plan.parallel_count}并行, "
                f"{plan.serial_count}串行, 护栏上限={self._max_spawn}")

    # ── REFLECT ──
    def handle_reflect(self, user_message):
        self.reflect_state.enter()
        return self.reflect_state.get_checklist_prompt(self.children, user_message)

    def handle_reflect_pass(self):
        result = self.reflect_state.mark_pass()
        if result is None:
            self._checkpoint_mgr.write_checkpoint(
                "REFLECT_PASSED",
                {tid: {"status": e["obj"].get("status", "UNKNOWN")}
                 for tid, e in self.children.items()}
            )
        return None

    def handle_reflect_fail(self, reason):
        result = self.reflect_state.mark_fail(reason)
        return f"REFLECT_FAIL round={self.reflect_state.current_round}/{self.reflect_state.MAX_ROUNDS}: {reason}"

    # ── SPAWN ──
    def spawn(self, agent, prompt):
        guard = self._guard_spawn()
        if guard:
            return guard
        prompt = prompt.strip()
        if not prompt:
            return "ERROR 任务描述不能为空"

        role_prompt = get_role_prompt(agent)
        timeout = get_default_timeout(agent)

        import requests
        r = requests.post(
            f"http://localhost:8001/api/child-tasks/",
            json={"parent_id": self.parent_id, "agent_name": agent,
                  "agent_profile": agent, "task_prompt": prompt},
            timeout=10
        )
        data = r.json()
        child_id = data.get("id")
        if not child_id:
            return "ERROR 创建子任务失败"

        proc = subprocess.Popen(
            ["hermes", "chat", "-q",
             f"<system_instruction>{role_prompt}</system_instruction>\n{prompt}",
             "-p", agent, "-Q", "--yolo"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            cwd=os.path.expanduser("~")
        )

        self.children[str(child_id)] = {"proc": proc, "prompt": prompt,
                                          "obj": {"agent_name": agent, "status": "RUNNING",
                                                   "result": None, "error_info": None}}

        def _timeout_killer():
            time.sleep(timeout)
            try:
                if proc.poll() is None:
                    proc.kill()
            except: pass
        threading.Thread(target=_timeout_killer, daemon=True).start()

        requests.patch(
            f"http://localhost:8001/api/child-tasks/{child_id}/",
            json={"status": "RUNNING", "pid": proc.pid}, timeout=5
        )

        self._checkpoint_mgr.write_checkpoint(
            "EXECUTING",
            {tid: {"status": "RUNNING"} for tid in self.children}
        )
        return f"OK {child_id}"

    def check(self, task_id):
        import requests
        entry = self.children.get(task_id)
        if entry:
            proc = entry["proc"]
            ret = proc.poll()
            if ret is not None:
                stdout = proc.stdout.read() if proc.stdout else ""
                result = stdout.strip() or "(无输出)"
                if result.startswith("session_id:"):
                    result = result.split("\n", 1)[1].strip() if "\n" in result else result
                status = "DONE" if ret == 0 else f"FAILED({ret})"
                requests.patch(
                    f"http://localhost:8001/api/child-tasks/{task_id}/",
                    json={"status": "DONE" if ret == 0 else "FAILED",
                          "result": result}, timeout=5)
                entry["obj"]["status"] = status
                entry["obj"]["result"] = result
                self._checkpoint_mgr.write_checkpoint(
                    "EXECUTING",
                    {tid: {"status": e["obj"].get("status", "UNKNOWN")}
                     for tid, e in self.children.items()}
                )
                return f"[{entry['obj'].get('agent_name','?')}|{task_id}] {status}: {result[:300]}"
            else:
                return f"RUNNING {task_id}"

        r = requests.get(f"http://localhost:8001/api/child-tasks/{task_id}/", timeout=5)
        if r.status_code == 404:
            return f"ERROR {task_id}: 不存在"
        data = r.json()
        return f"[{data.get('agent_name','?')}|{task_id}] {data.get('status','?')}"

    def wait_all(self):
        deadline = time.time() + 600
        while time.time() < deadline:
            all_done = True
            for entry in self.children.values():
                if entry["proc"].poll() is None:
                    all_done = False
                    break
            if all_done:
                break
            time.sleep(2)

        lines = []
        for tid, entry in self.children.items():
            proc = entry["proc"]
            result = ""
            if proc.poll() is not None:
                stdout = proc.stdout.read() if proc.stdout else ""
                result = stdout.strip() or "(无输出)"
                if result.startswith("session_id:"):
                    result = result.split("\n", 1)[1].strip() if "\n" in result else result
            status = "DONE" if proc.poll() == 0 else f"FAILED({proc.poll()})" if proc.poll() is not None else "RUNNING"
            marker = entry["obj"].get("agent_name", "?")
            lines.append(f"[{marker}|{tid}] {status}: {result[:500]}")

        return "\n\n".join(lines) if lines else "无子任务"

    def kill(self, task_id):
        entry = self.children.get(task_id)
        if entry:
            try:
                entry["proc"].kill()
            except Exception:
                pass
            entry["obj"]["status"] = "ABORTED"
            return f"KILLED {task_id}"
        return f"ERROR {task_id}: 不存在"

    def reply(self, markdown):
        if not markdown or not markdown.strip():
            return "ERROR 回复不能为空"
        import requests
        requests.patch(
            f"http://localhost:8001/api/parent-tasks/{self.parent_id}/",
            json={"status": "REPLY", "final_reply": markdown.strip()}, timeout=10
        )
        return None

    def _cleanup(self):
        for entry in self.children.values():
            try:
                if entry["proc"].poll() is None:
                    entry["proc"].kill()
            except Exception:
                pass
        self.children.clear()


# ══════ 主循环 v4 ══════

def run_yunshu_session(parent_id, conv_id, user_message, agent_profile="banni"):
    handler = YunshuCommandHandler(parent_id, conv_id, agent_profile)
    system_prompt = _load_system_prompt()

    import requests
    requests.patch(f"http://localhost:8001/api/parent-tasks/{parent_id}/",
                   json={"status": "PLANNING"}, timeout=5)

    context = f"{system_prompt}\n\n用户消息：{user_message}"
    max_rounds = 15
    plan_lines = []
    in_plan = False

    for round_n in range(max_rounds):
        reply = _hermes_q(context, agent_profile)
        print(f"[YunshuIO] Round {round_n}: {reply[:200]}", file=__import__('sys').stderr)

        if not reply:
            break

        lines = reply.strip().split("\n")
        response_lines = []
        any_command = False

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # PLAN 多行收集
            if in_plan:
                if line.startswith(("SPAWN_", "REPLY:", "WAIT_ALL", "REFLECT", "CHECK", "KILL")):
                    in_plan = False
                    response_lines.append(handler.handle_plan("\n".join(plan_lines)))
                    plan_lines = []
                else:
                    plan_lines.append(line)
                    continue

            matched = False
            for cmd_name, pattern in CMD_PATTERNS.items():
                m = pattern.match(line)
                if m:
                    matched = True
                    any_command = True
                    response = None

                    if cmd_name == "SPAWN_BANNI":
                        response = handler.spawn("banni", m.group(1))
                    elif cmd_name == "SPAWN_BASIR":
                        response = handler.spawn("basir", m.group(1))
                    elif cmd_name == "CHECK":
                        response = handler.check(m.group(1))
                    elif cmd_name == "WAIT_ALL":
                        response = handler.wait_all()
                    elif cmd_name == "KILL":
                        response = handler.kill(m.group(1))
                    elif cmd_name == "REPLY":
                        final = m.group(1).strip()
                        handler.reply(final)
                        handler._cleanup()
                        return final
                    elif cmd_name == "PLAN":
                        in_plan = True
                        plan_lines = [m.group(1).strip()]
                    elif cmd_name == "REFLECT":
                        response = handler.handle_reflect(user_message)
                    elif cmd_name == "REFLECT_PASS":
                        handler.handle_reflect_pass()
                    elif cmd_name == "REFLECT_FAIL":
                        response = handler.handle_reflect_fail(m.group(1))

                    if response:
                        response_lines.append(response)
                    break

            if not matched:
                pass  # 云枢自言自语，不加入 response_lines

        # 处理残留 PLAN
        if in_plan and plan_lines:
            in_plan = False
            response_lines.append(handler.handle_plan("\n".join(plan_lines)))

        # 兜底：整轮无命令 → 整段当 REPLY
        if not any_command:
            handler.reply(reply.strip())
            handler._cleanup()
            return reply.strip()

        pass

        # 构建下一轮
        if response_lines:
            if any("OK" in r for r in response_lines):
                wait_result = handler.wait_all()
                context = f"{system_prompt}\n\n子任务结果：\n{wait_result}"
            else:
                context = f"{system_prompt}\n\n上轮结果：\n" + "\n".join(response_lines)
        else:
            break

    handler._cleanup()
    return _fallback_reply(parent_id, conv_id)


def _hermes_q(message, profile):
    try:
        r = subprocess.run(
            ["hermes", "chat", "-q", message, "-p", profile, "-Q", "--yolo"],
            capture_output=True, text=True, timeout=300,
            cwd=os.path.expanduser("~")
        )
        raw = r.stdout.strip()
        if raw.startswith("session_id:"):
            raw = raw.split("\n", 1)[1].strip() if "\n" in raw else raw
        return raw or r.stderr.strip() or ""
    except Exception:
        return ""


def _load_system_prompt():
    path = os.path.expanduser("~/.hermes/profiles/banni/skills/yunshu-operations/hermes_agent_prompt.md")
    try:
        return open(path).read()
    except Exception:
        return _default_prompt()


def _default_prompt():
    return """# 云枢调度器 v4
你有 Banni(搜索/工程) 和 Basir(分析/推断)。

## 命令
SPAWN_BANNI: <任务>
SPAWN_BASIR: <任务>
WAIT_ALL
REPLY: <Markdown>
PLAN: complexity: <simple|medium|complex>, tasks: ...
REFLECT → REFLECT_PASS 或 REFLECT_FAIL

## 流程
1. 复杂任务先 PLAN 声明计划
2. SPAWN 派发 → WAIT_ALL 等结果
3. REPLY 前 REFLECT 自检
4. 发现修正信号 → 必须先重搜再 REPLY"""


def _fallback_reply(parent_id, conv_id):
    reply = "系统在处理您的请求时遇到问题，请稍后重试。"
    try:
        import requests
        requests.patch(
            f"http://localhost:8001/api/parent-tasks/{parent_id}/",
            json={"status": "FAILED", "final_reply": reply}, timeout=10
        )
    except Exception:
        pass
    return reply
