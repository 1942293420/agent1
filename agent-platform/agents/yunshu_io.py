"""
Worker 文本协议 v4 - Yunshu I/O 循环
PLAN → SPAWN → WAIT → REFLECT → REPLY
"""
import subprocess, threading, time, re, os, json
import requests
API_BASE = "http://localhost:8001"
from agent_registry import get_role_prompt, get_default_timeout
from plan_parser import PlanGraph
from checkpoint import CheckpointManager
from pitfall_memory import search_pitfall, record_pitfall

# Django ORM (already configured by worker — import silently if available)
try:
    from agents.models import ParentTask, TaskNode
    from django.utils import timezone as django_timezone
    _HAS_DJANGO = True
except Exception:
    _HAS_DJANGO = False


# ══════ 命令匹配 v4 ══════
CMD_PATTERNS = {
    # v3 原有
    "SPAWN_BANNI": re.compile(r"^SPAWN_BANNI\s*:?\s*(.+)", re.I),
    "SPAWN_BASIR": re.compile(r"^SPAWN_BASIR\s*:?\s*(.+)", re.I),
    "SPAWN_YUNHENG": re.compile(r"^SPAWN_YUNHENG\s*:?\s*(.+)", re.I),
    "CHECK":       re.compile(r"^CHECK\s+(\S+)", re.I),
    "WAIT_ALL":    re.compile(r"^WAIT_ALL$", re.I),
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
        self._in_reflect = False
        self.passed = False
        self.fail_reason = ""

    @property
    def active(self): return self._in_reflect

    def enter(self): self._in_reflect = True

    def mark_pass(self):
        self.passed = True
        self._in_reflect = False

    def mark_fail(self, reason=""):
        self.current_round += 1
        self.fail_reason = reason
        self._in_reflect = False
        if self.current_round >= self.MAX_ROUNDS:
            return "FORCE_PASS"
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
        self._children_lock = threading.Lock()  # P0 修复：线程安全
        self._max_spawn = 3  # 护栏上限，PLAN 可调整
        self._absolute_max = 8
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

        # ── TaskNode: PLAN → build_from_plan ──
        try:
            if not _HAS_DJANGO: raise RuntimeError("Django not available")
            pt = ParentTask.objects.get(pk=self.parent_id)
            # Build plan_data dict from PlanGraph nodes
            nodes_data = []
            for i, node in enumerate(plan.nodes):
                nodes_data.append({
                    'task_id': node.task_id,
                    'agent_type': node.agent_type,
                    'description': node.description,
                    'dependencies': node.dependencies,
                })
            plan_data = {'nodes': nodes_data}
            TaskNode.build_from_plan(pt, plan_data)
            # Also store dispatch_plan on ParentTask via API
            requests.patch(
                f"{API_BASE}/api/parent-tasks/{self.parent_id}/",
                json={'dispatch_plan': plan_data}, timeout=5
            )
        except Exception as e:
            import sys
            print(f"[YunshuIO] TaskNode build_from_plan failed: {e}", file=sys.stderr)

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
    def spawn(self, agent, prompt, node_id=None):
        guard = self._guard_spawn()
        if guard:
            return guard
        prompt = prompt.strip()
        if not prompt:
            return "ERROR 任务描述不能为空"

        role_prompt = get_role_prompt(agent)
        timeout = get_default_timeout(agent)

        r = requests.post(
            f"{API_BASE}/api/child-tasks/",
            json={"parent_id": self.parent_id, "agent_name": agent,
                  "agent_profile": agent, "task_prompt": prompt},
            timeout=10
        )
        data = r.json()
        child_id = data.get("id")
        if not child_id:
            return "ERROR 创建子任务失败"

        # ── TaskNode: SPAWN → 关联 child_task ──
        if node_id and _HAS_DJANGO:
            try:
                tn = TaskNode.objects.get(
                    parent_task_id=self.parent_id, node_id=node_id
                )
                tn.child_task_id = child_id
                tn.status = TaskNode.NodeStatus.RUNNING
                tn.started_at = django_timezone.now()
                tn.save()
            except TaskNode.DoesNotExist:
                pass
            except Exception as e:
                import sys
                print(f"[YunshuIO] TaskNode SPAWN link failed: {e}", file=sys.stderr)

        # ── 权限控制：staff用项目目录，非staff禁terminal/file+沙箱隔离 ──
        tools = "terminal,file,web,feishu_doc,feishu_drive"
        work_dir = os.path.expanduser("~/projects")
        if _HAS_DJANGO:
            try:
                pt = ParentTask.objects.select_related('conversation__user').get(pk=self.parent_id)
                if pt.conversation and pt.conversation.user:
                    # 沙箱隔离：非admin用户限定工作目录，但工具权限相同
                    work_dir = f"/home/jiangli/sandboxes/user_{pt.conversation.user.id}"
                    os.makedirs(work_dir, exist_ok=True)
            except Exception:
                pass

        proc = subprocess.Popen(
            ["hermes", "chat", "-q",
             f"<system_instruction>{role_prompt}</system_instruction>\n{prompt}",
             "-p", agent, "-Q", "--yolo",
             "-t", tools],
            bufsize=1, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            cwd=work_dir, env={**os.environ, "HOME": work_dir}
        )

        with self._children_lock:
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
            f"{API_BASE}/api/child-tasks/{child_id}/",
            json={"status": "RUNNING", "pid": proc.pid}, timeout=5
        )

        self._checkpoint_mgr.write_checkpoint(
            "EXECUTING",
            {tid: {"status": "RUNNING"} for tid in self.children}
        )
        return f"OK {child_id}"

    def check(self, task_id):
        entry = self.children.get(task_id)
        if entry:
            proc = entry["proc"]
            ret = proc.poll()
            if ret is not None:
                try:
                    out, err = proc.communicate(timeout=30)
                    result = (out or "").strip() or (err or "").strip() or "(无输出)"
                except Exception:
                    result = "(输出读取超时)"
                if result.startswith("session_id:"):
                    result = result.split("\n", 1)[1].strip() if "\n" in result else result
                status = "DONE" if ret == 0 else f"FAILED({ret})"
                requests.patch(
                    f"{API_BASE}/api/child-tasks/{task_id}/",
                    json={"status": "DONE" if ret == 0 else "FAILED",
                          "result": result}, timeout=5)
                entry["obj"]["status"] = status
                entry["obj"]["result"] = result
                self._checkpoint_mgr.write_checkpoint(
                    "EXECUTING",
                    {tid: {"status": e["obj"].get("status", "UNKNOWN")}
                     for tid, e in self.children.items()}
                )

                # ── TaskNode: CHECK → 更新状态/duration_ms ──
                if _HAS_DJANGO:
                    try:
                        tn = TaskNode.objects.filter(
                            parent_task_id=self.parent_id, child_task_id=task_id
                        ).first()
                        if tn:
                            tn.status = TaskNode.NodeStatus.DONE if ret == 0 else TaskNode.NodeStatus.FAILED
                            tn.finished_at = django_timezone.now()
                            if tn.started_at:
                                delta = tn.finished_at - tn.started_at
                                tn.duration_ms = int(delta.total_seconds() * 1000)
                            tn.save()
                    except Exception as e:
                        import sys
                        print(f"[YunshuIO] TaskNode CHECK update failed: {e}", file=sys.stderr)

                return f"[{entry['obj'].get('agent_name','?')}|{task_id}] {status}: {result[:8000]}"
            else:
                return f"RUNNING {task_id}"

        r = requests.get(f"{API_BASE}/api/child-tasks/{task_id}/", timeout=5)
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
                try:
                    out, err = proc.communicate(timeout=30)
                    result = (out or "").strip() or (err or "").strip() or "(无输出)"
                except Exception:
                    result = "(输出读取超时)"
                if result.startswith("session_id:"):
                    result = result.split("\n", 1)[1].strip() if "\n" in result else result
            status = "DONE" if proc.poll() == 0 else f"FAILED({proc.poll()})" if proc.poll() is not None else "RUNNING"
            marker = entry["obj"].get("agent_name", "?")
            lines.append(f"[{marker}|{tid}] {status}: {result[:8000]}")

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
        requests.patch(
            f"{API_BASE}/api/parent-tasks/{self.parent_id}/",
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


# ══════ 方案 B：代码按 PlanGraph 自动调度 ══════

def execute_plan_graph(handler: YunshuCommandHandler, plan: PlanGraph) -> dict:
    """
    按 PlanGraph 的依赖图自动执行所有子任务。
    返回 {"results": [...], "summary": "..."}

    - 用 get_parallel_groups() 分批执行
    - 每批并行 spawn → wait_all → 收集结果
    - 维护 plan_task_id → api_child_id 映射
    """
    task_map = {}  # plan_task_id → api_child_id
    step_results = []
    groups = plan.get_parallel_groups()

    import sys
    print(f"[YunshuIO] PlanGraph: {len(groups)} 组, "
          f"共 {sum(len(g) for g in groups)} 个任务", file=sys.stderr)

    for group_idx, group in enumerate(groups):
        print(f"[YunshuIO] 第 {group_idx+1}/{len(groups)} 组: {group}", file=sys.stderr)

        # 找到本组所有 PlanNode
        group_nodes = []
        for tid in group:
            node = next((n for n in plan.nodes if n.task_id == tid), None)
            if node:
                group_nodes.append((tid, node))

        if not group_nodes:
            continue

        # 步骤 1: 并行 spawn
        for tid, node in group_nodes:
            prompt = f"[任务 {tid}]\\n{node.description}"
            resp = handler.spawn(node.agent_type, prompt, node_id=tid)
            print(f"[YunshuIO]   SPAWN {node.agent_type}({tid}): {resp[:80]}", file=sys.stderr)

            # 记录映射 (spawn 返回 "OK <api_id>")
            if resp.startswith("OK "):
                api_id = resp[3:].strip()
                task_map[tid] = api_id
            else:
                step_results.append({
                    "task_id": tid, "agent": node.agent_type,
                    "status": "SPAWN_FAILED", "result_preview": resp[:200],
                })

        # 步骤 2: wait_all 等待本组全部完成
        wait_output = handler.wait_all()
        print(f"[YunshuIO]   等待完成", file=sys.stderr)

        # 步骤 3: check 每个子任务结果
        for tid, node in group_nodes:
            api_id = task_map.get(tid)
            if not api_id:
                continue  # 已在 spawn 阶段标记失败
            check_result = handler.check(api_id)
            entry = handler.children.get(api_id, {})
            obj = entry.get("obj", {}) if isinstance(entry, dict) else {}
            status = obj.get("status", "UNKNOWN")
            result_text = obj.get("result", "") or ""

            step_results.append({
                "task_id": tid,
                "agent": node.agent_type,
                "description": node.description[:100],
                "status": status,
                "result_preview": result_text[:500],
            })

    # 构建摘要
    summary_lines = []
    for sr in step_results:
        summary_lines.append(
            f"- [{sr['agent']}|{sr['task_id']}] {sr['status']}: "
            f"{sr.get('result_preview', '')[:200]}"
        )
    summary = "\\n".join(summary_lines) if summary_lines else "无执行结果"

    return {"results": step_results, "summary": summary}


def _collect_children_results(handler):
    """从 handler.children 捞出所有子任务的完整结果"""
    lines = []
    for tid, entry in handler.children.items():
        obj = entry.get("obj", {}) if isinstance(entry, dict) else {}
        agent = obj.get("agent_name", "?")
        status = obj.get("status", "UNKNOWN")
        result = obj.get("result", "") or ""
        lines.append(f"[{agent}|{tid}] {status}:\n{result[:8000]}")
    return "\n\n".join(lines) if lines else "无子任务"


# ══════ 主循环 v4 ══════

def run_yunshu_session(parent_id, conv_id, user_message, agent_profile="banni"):
    handler = YunshuCommandHandler(parent_id, conv_id, agent_profile)
    system_prompt = _load_system_prompt()

    requests.patch(f"{API_BASE}/api/parent-tasks/{parent_id}/",
                   json={"status": "PLANNING"}, timeout=5)

    context = f"{system_prompt}\n\n用户消息：{user_message}"

    # 聚合跨端上下文（飞书 + Web）
    try:
        from context_aggregator import aggregate_cross_source_context
        cross_ctx = aggregate_cross_source_context(conv_id, user_message)
        if cross_ctx:
            context = (
                f"{system_prompt}\n\n"
                f"{cross_ctx}\n\n"
                f"用户消息：{user_message}"
            )
    except Exception:
        pass
    max_rounds = 15
    plan_lines = []
    in_plan = False
    plan_graph = None  # 方案 B: 保存解析后的 PlanGraph

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
                    plan_text = "\n".join(plan_lines)
                    plan_graph = PlanGraph.parse(plan_text)  # 方案 B: 保存解析结果
                    response_lines.append(handler.handle_plan(plan_text))
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
                    elif cmd_name == "SPAWN_YUNHENG":
                        response = handler.spawn("yunheng", m.group(1))
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
            plan_text = "\n".join(plan_lines)
            plan_graph = PlanGraph.parse(plan_text)  # 方案 B: 保存解析结果
            response_lines.append(handler.handle_plan(plan_text))

        # 兜底：整轮无命令 → 整段当 REPLY
        if not any_command:
            handler.reply(reply.strip())
            handler._cleanup()
            return reply.strip()

        # 构建下一轮 context
        if response_lines or handler.reflect_state.passed:
            # ═══ 方案 B: PLAN 刚解析 → 代码接管执行 ═══
            if any("plan_parsed" in r for r in response_lines):
                if plan_graph and plan_graph.validate():
                    # 代码按依赖图自动 spawn + wait + collect
                    exec_result = execute_plan_graph(handler, plan_graph)
                    results_text = _collect_children_results(handler)
                    context = (
                        f"# REFLECT 自检\n\n"
                        f"用户需求：{user_message[:300]}\n\n"
                        f"## 子任务执行结果\n{results_text}\n\n"
                        f"## 5 项自检清单\n"
                        f"1. 事实是否有子Agent输出支撑？\n"
                        f"2. 修正是否完成？\n"
                        f"3. 是否遗漏用户需求？\n"
                        f"4. 结构是否完整？\n"
                        f"5. 是否有可操作建议？\n\n"
                        f"## 指令\n"
                        f"全部通过 → 输出: REFLECT_PASS\n"
                        f"未通过   → 输出: REFLECT_FAIL: <原因> <修正行动>\n"
                        f"禁止输出自检表格，禁止重新 PLAN，禁止输出任何其他内容。"
                    )
                else:
                    context = f"{system_prompt}\n\n用户消息：{user_message}\n\nPLAN 解析失败，请用单行 desc 重新输出 PLAN。"
                plan_graph = None  # 只执行一次

            # REFLECT 失败 → 修正轮（精简 prompt，不让 LLM 看到 PLAN）
            elif any("REFLECT_FAIL" in r for r in response_lines):
                fail_info = "\n".join(response_lines)
                results_text = _collect_children_results(handler)
                # 🔗 先查 pitfall_memory，有已知修复就自动应用
                pitfall_hint = ""
                pitfall = search_pitfall(fail_info, results_text)
                if pitfall:
                    pitfall_hint = (
                        f"\n\n💡 **踩坑记忆命中**（hit={pitfall.get('hit_count',0)}次）：\n"
                        f"已知修复方案 ({pitfall['fix_type']})：{pitfall.get('fix_detail','')[:300]}"
                    )
                context = (
                    f"# 修正轮\n\n"
                    f"你的上次 REFLECT 自检未通过：\n{fail_info}\n\n"
                    f"当前子任务结果：\n{results_text}\n\n"
                    f"{pitfall_hint}\n"
                    f"## 你只有两个选择，禁止其他输出：\n"
                    f"1. 修正 → 输出 SPAWN_BANNI: <任务> 或 SPAWN_BASIR: <任务>\n"
                    f"2. 已修好 → 输出 REFLECT_PASS\n\n"
                    f"禁止 PLAN。禁止 WAIT_ALL。禁止 REPLY。禁止输出分析表格。"
                )

            # SPAWN / WAIT → 子任务完成 → REFLECT
            elif any("OK" in r for r in response_lines):
                wait_result = handler.wait_all()
                context = (
                    f"# REFLECT 自检\n\n"
                    f"用户需求：{user_message[:300]}\n\n"
                    f"## 子任务结果\n{wait_result}\n\n"
                    f"## 指令\n"
                    f"全部通过 → 输出: REFLECT_PASS\n"
                    f"未通过   → 输出: REFLECT_FAIL: <原因> <修正行动>\n"
                    f"禁止输出自检表格，禁止重新 PLAN。"
                )

            # REFLECT 通过 → 构造 REPLY（不用 system_prompt，避免 PLAN 干扰）
            elif any("REFLECT_PASS" in r for r in response_lines):
                results_text = handler.wait_all()
                context = (
                    f"# 最终回复\n\n"
                    f"用户需求：{user_message[:300]}\n\n"
                    f"## 子任务结果\n{results_text}\n\n"
                    f"## 指令\n"
                    f"REFLECT 已通过。根据子任务结果和用户需求，"
                    f"立即 REPLY 输出最终回答（Markdown格式）。"
                    f"禁止 SPAWN，禁止 PLAN。"
                )

            # CHECK / 其他
            else:
                context = f"{system_prompt}\n\n上轮结果：\n" + "\n".join(response_lines)

        # REFLECT 刚通过，response_lines 为空 → 构造 REPLY 上下文
        elif handler.reflect_state.passed:
            # 🔗 如果之前有 REFLECT_FAIL，自动记录到 pitfall_memory
            if handler.reflect_state.fail_reason:
                try:
                    record_pitfall(
                        pattern=handler.reflect_state.fail_reason[:200],
                        context="Yunshu REFLECT self-check",
                        fix_type="retry",
                        fix_detail="REFLECT_FAIL → LLM修正 → REFLECT_PASS"
                    )
                except Exception:
                    pass  # 记录失败不影响主流程
            results_text = handler.wait_all()
            context = (
                f"# 最终回复\n\n"
                f"用户需求：{user_message[:300]}\n\n"
                f"## 子任务结果\n{results_text}\n\n"
                f"## 指令\n"
                f"REFLECT 已通过。根据子任务结果和用户需求，"
                f"立即 REPLY 输出最终回答（Markdown格式）。"
                f"禁止 SPAWN，禁止 PLAN。"
            )
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
    except Exception as e:
        import sys
        print(f"[YunshuIO] _hermes_q error: {e}", file=sys.stderr)
        return ""

def _load_system_prompt():
    path = os.path.expanduser("~/.hermes/profiles/banni/skills/yunshu-operations/hermes_agent_prompt.md")
    try:
        return open(path).read()
    except Exception:
        return _default_prompt()


def _default_prompt():
    return """# 云枢调度器 v4.1

你是云枢调度器。你有三个子Agent：
- Banni(搜索/工程) — 信息采集、代码编写、文件操作
- Basir(分析/推断) — 数据分析、逻辑推理、报告生成
- 云衡(测试/审查) — 代码审查、安全扫描、TDD测试、缺陷诊断
他们都有 feishu_doc/feishu_drive 工具，可以创建飞书云文档。

## ⚠️ 强制规则（违反规则的任务将被拒绝执行）
- **任何需要子Agent的任务，第一轮只能输出 PLAN，禁止输出其他任何内容**
- **严禁**在 PLAN 之前输出"已派发"、"正在执行"、"我来帮你"等自然语言
- **严禁**跳过 PLAN 直接说"好的，我来安排"之类的话
- 你的第一轮回复必须是且只能是 PLAN 格式，不能有任何前缀或后缀文字
- 用户要求"用飞书云文档回复"时，必须在 PLAN 中包含创建飞书文档的任务
- PLAN 之后代码会自动按依赖图执行，你不需要输出 SPAWN
- 子任务完成后你会收到结果摘要，此时必须 REFLECT → REPLY
- **禁止**在收到子任务结果之前 REPLY

## PLAN 格式（⚠️ desc 必须单行，禁止 > 多行语法）
PLAN:
complexity: medium
tasks:
  - id: t1, agent: banni, desc: 简短任务描述(单行), deps: []
  - id: t2, agent: basir, desc: 简短任务描述(单行), deps: [t1]
  - id: t3, agent: yunheng, desc: 代码审查和测试, deps: [t1]

## 输出面板
用户明确要求「用输出面板」时，在 REPLY 末尾用 OUTPUT_PANEL 标记。平常直接 REPLY 回复即可。格式：
【OUTPUT_PANEL】
你的 Markdown 报告...
【/OUTPUT_PANEL】
系统会自动推送到用户输出面板，用户可预览和下载 .md 文件。

## 完整流程
1. 分析用户需求 → 输出 PLAN（第一轮必须！）
2. 等待子任务结果（代码自动执行，你只需等待）
3. 收到结果后 REFLECT 自检
4. 通过后 REFLECT_PASS → REPLY 输出最终回答"""


def _fallback_reply(parent_id, conv_id):
    reply = "系统在处理您的请求时遇到问题，请稍后重试。"
    try:
        requests.patch(
            f"{API_BASE}/api/parent-tasks/{parent_id}/",
            json={"status": "FAILED", "final_reply": reply}, timeout=10
        )
    except Exception:
        pass
    return reply
