"""
Worker 文本协议 v4 - Yunshu I/O 循环
PLAN → SPAWN → WAIT → REFLECT → REPLY
"""
import subprocess, threading, time, re, os, json
import requests
API_BASE = "http://localhost:8001"
from agent_registry import get_role_prompt, get_default_timeout, get_model_for_task, infer_task_type
from plan_parser import PlanGraph
from checkpoint import CheckpointManager
from pitfall_memory import search_pitfall, record_pitfall


def _push_progress(conv_id, msg, source="web"):
    """推送进度节点消息到聊天界面（静默失败不影响主流程）"""
    try:
        requests.post(
            f"{API_BASE}/api/messages/",
            json={"conversation": conv_id, "role": "system", "content": msg, "source": source},
            timeout=5
        )
    except Exception:
        pass

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
    "SPAWN_TESTER": re.compile(r"^SPAWN_TESTER\s*:?\s*(.+)", re.I),
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
    def __init__(self, parent_id, conv_id, agent_profile="banni", source="web"):
        self.parent_id = parent_id
        self.conv_id = conv_id
        self.profile = agent_profile
        self.source = source  # 消息来源: "web" | "feishu"
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
        # ── PLAN FAIL 是系统提示词要求的合规响应（无任务），非解析错误 ──
        stripped = plan_text.strip()
        if stripped.upper().startswith("FAIL"):
            import sys
            print(f"[YunshuIO] PLAN FAIL (无任务): {stripped[:100]}", file=sys.stderr)
            return "OK no_task"

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
    def spawn(self, agent, prompt, node_id=None, model_profile=None):
        guard = self._guard_spawn()
        if guard:
            return guard
        prompt = prompt.strip()
        if not prompt:
            return "ERROR 任务描述不能为空"

        role_prompt = get_role_prompt(agent)
        timeout = get_default_timeout(agent)

        # ── 模型分级：未指定时根据 agent+description 自动推断 ──
        if model_profile is None:
            model_profile = get_model_for_task(agent, prompt)
        import sys
        print(f"[YunshuIO] spawn {agent} → model={model_profile} task_type={infer_task_type(agent, prompt)}", file=sys.stderr)

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

        cmd = [
            "hermes", "chat", "-q",
            f"<system_instruction>{role_prompt}</system_instruction>\n{prompt}",
            "-Q", "--yolo",
            "-t", tools,
        ]
        env = {**os.environ, "HERMES_PROFILE": agent, "HOME": work_dir}
        # ── 模型分级：通过 -m 覆盖模型 ──
        if model_profile:
            cmd.extend(["-m", model_profile])

        proc = subprocess.Popen(
            cmd,
            bufsize=1, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            cwd=work_dir, env=env
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
                            # 保存错误/输出信息到 metadata
                            if ret != 0:
                                tn.metadata = {"error": result[:500], "exit_code": ret}
                            else:
                                tn.metadata = {"output": result[:500]}
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
        if _looks_like_code_or_garbage(markdown):
            import sys
            print(f"[YunshuIO] ⚠️ reply()出口校验：拒绝疑似代码/测试内容", file=sys.stderr)
            return "ERROR 回复疑似代码/测试内容，拒绝保存"
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

    # ── 推送 PLAN 概览到聊天 ──
    node_list = ", ".join(f"{n.agent_type}({n.task_id})" for n in plan.nodes)
    _push_progress(handler.conv_id,
        f"📋 PLAN: {len(plan.nodes)} 节点, {len(groups)} 组 — {node_list}",
        source=handler.source)

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

            # ── 推送 SPAWN 到聊天 ──
            _push_progress(handler.conv_id,
                f"🔄 {tid} {node.agent_type} 启动 — {node.description[:60]}...",
                source=handler.source)

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

        # ── 推送节点完成到聊天 ──
        for tid, node in group_nodes:
            api_id = task_map.get(tid)
            if api_id:
                entry = handler.children.get(api_id, {})
                obj = entry.get("obj", {}) if isinstance(entry, dict) else {}
                status = obj.get("status", "UNKNOWN")
                icon = "✅" if status in ("DONE",) else "❌"
                _push_progress(handler.conv_id,
                    f"{icon} {tid} {node.agent_type} 完成",
                    source=handler.source)

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


def _strip_diff_wrapper(result_text):
    """剥离 hermes chat diff 格式外壳，还原真实 Markdown 内容"""
    if not result_text:
        return result_text
    text = result_text
    # 1. 去掉 tirith 警告行
    if "⚠ tirith" in text[:100]:
        text = text.split("\n", 1)[1] if "\n" in text else text
    # 2. 去掉 "┊ review diff" 头
    if "┊ review diff" in text[:200]:
        text = text.split("\n", 1)[1] if "\n" in text else text
    # 3. 跳过 diff 元数据行（a/... → b/... / @@ ... @@ / --- / +++）
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        s = line.strip()
        if s.startswith(("a/", "b/")) or s.startswith("@@") or s == "---" or s.startswith("+++"):
            continue
        # 4. 去掉行首的 + 前缀（diff 新增行标记）
        if line.startswith("+"):
            line = line[1:]
        cleaned.append(line)
    return "\n".join(cleaned)


def _extract_core_summary(result_text, max_chars=600):
    """从子Agent产出的 Markdown 报告中提取核心结论（结构化摘要）"""
    if not result_text:
        return "(无输出)"
    # 先剥离 diff 外壳
    result_text = _strip_diff_wrapper(result_text)
    if len(result_text) <= max_chars:
        return result_text

    # 提取 score 行、结论/建议/亮点/问题等关键段落
    score_pattern = re.compile(r'(?:评分|分数|得分|Score)[：:]\s*.+', re.I)
    section_pattern = re.compile(
        r'^#{1,3}\s*(?:结论|建议|总结|汇总|亮点|问题|推荐|核心|摘要|审查'
        r'|结论|方案|实施|代码质量|最终'
        r'|Conclusion|Summary|Recommend|Key|Result)',
        re.I | re.M
    )

    parts = []
    # 开头（概览/范围）
    parts.append(result_text[:200].strip())

    # 评分行
    for m in score_pattern.finditer(result_text):
        parts.append(m.group().strip())

    # 关键章节
    for m in section_pattern.finditer(result_text):
        start = m.start()
        end = min(start + 300, len(result_text))
        section_text = result_text[start:end].strip()
        parts.append(section_text)

    # 拼接并截断
    summary = "\n".join(parts)
    if len(summary) > max_chars:
        # 优先保留评分和结论，从后往前裁
        lines = summary.split("\n")
        kept = []
        remaining = max_chars
        for line in reversed(lines):
            if remaining <= 0:
                break
            if len(line) + 1 <= remaining:
                kept.insert(0, line)
                remaining -= len(line) + 1
            else:
                kept.insert(0, line[:remaining])
                break
        summary = "\n".join(kept)

    return summary[:max_chars]


def _summarize_children_results(handler, max_per_child=600):
    """结构化摘要：每个子Agent结果只取核心结论，总量从 ~24000 降到 ~2000
    过滤掉 RUNNING 状态和空结果的子任务，避免 LLM 混乱"""
    lines = []
    for tid, entry in handler.children.items():
        obj = entry.get("obj", {}) if isinstance(entry, dict) else {}
        agent = obj.get("agent_name", "?")
        status = obj.get("status", "UNKNOWN")
        result = obj.get("result", "") or ""
        # 跳过 RUNNING 和空结果的子任务
        if status in ("RUNNING",) or not result.strip():
            lines.append(f"[{agent}|{tid}] {status}: (结果为空/未完成)")
            continue
        core = _extract_core_summary(result, max_per_child)
        lines.append(f"[{agent}|{tid}] {status}:\n{core}")
    return "\n\n".join(lines) if lines else "无子任务"


def _collect_children_results(handler):
    """从 handler.children 捞出所有子任务的完整结果（保留兼容，内部调用摘要版）"""
    return _summarize_children_results(handler, max_per_child=2000)


def _looks_like_code_or_garbage(text):
    """检测输出是否为代码/测试/诊断内容，而非正常的用户回复"""
    if not text or len(text) < 10:
        return False
    text_stripped = text.strip()

    # 1. 以代码块开头
    if text_stripped.startswith("```"):
        return True

    # 2. 包含 review diff 模式
    if "┊ review diff" in text_stripped or "review diff" in text_stripped[:200]:
        return True

    # 3. 以 unified diff 开头
    if text_stripped.startswith("@@") or text_stripped.startswith("--- a/") or text_stripped.startswith("+++ b/"):
        return True

    # 4. 代码特征密度过高
    code_indicators = [
        "#!/usr/bin/env python", "import sys", "def test(", "def test_",
        "PlanGraph.parse", "test(\"", 'print(f\'===', "sqlite3",
    ]
    code_hits = sum(1 for ci in code_indicators if ci in text_stripped)
    if code_hits >= 2:
        return True

    # 5. 诊断报告模式（含 plan_parser / 根因 / 失败模式 等关键词）
    diagnostic_keywords = ["诊断报告", "失败模式", "根因", "plan_parser", "PlanGraph.parse"]
    diag_hits = sum(1 for dk in diagnostic_keywords if dk in text_stripped)
    if diag_hits >= 2:
        return True

    # 6. 代码行占比过高（以 + / - 开头的行 > 30%）
    lines = text_stripped.split("\n")
    if len(lines) > 5:
        diff_lines = sum(1 for l in lines if l.startswith("+") or l.startswith("-"))
        if diff_lines > len(lines) * 0.3:
            return True

    return False


# ══════ 主循环 v4 ══════

def classify_intent(user_message: str, conv_id: int) -> str:
    """
    轻量意图分类 — 单次 hermes 小调用，复用云枢当前模型
    返回: "TASK" | "CHAT" | "CONTINUE"
    失败兜底: 返回 "TASK"（走原有流程，零风险）
    """
    # ── 检查是否有未完成的任务上下文 ──
    has_pending = False
    try:
        pending = requests.get(
            f"{API_BASE}/api/parent-tasks/list/?conversation={conv_id}&status=PLANNING",
            timeout=3
        ).json()
        if pending and len(pending) > 0:
            has_pending = True
    except Exception:
        pass

    pending_hint = ""
    if has_pending:
        pending_hint = "\n注意：此会话有未完成的任务，用户可能在继续追问。"

    classify_prompt = f"""你是一个消息分类器。分析用户消息，只输出一个标签。

标签定义：
- TASK: 包含明确可执行指令。例如："帮我写一个爬虫""创建飞书文档""修复这个bug""分析这个数据"
- CHAT: 纯问答/讨论/反馈/闲聊/追问。例如："为什么你的方案和云筑的相差这么大""这个想法怎么样""什么是XX""你觉得呢"
- CONTINUE: 明确延续上一轮任务。例如："继续""刚才那个不对""换一个方案""再试一次"

{pending_hint}

用户消息：
{user_message}

只输出一个标签，不要解释："""

    try:
        result = subprocess.run(
            ["hermes", "chat", "-q", classify_prompt, "-Q", "--yolo",
             "-m", "deepseek-chat"],
            capture_output=True, text=True, timeout=30,
            cwd=os.path.expanduser("~"), stdin=subprocess.DEVNULL
        )
        raw = result.stdout.strip()
        if raw.startswith("session_id:"):
            raw = raw.split("\n", 1)[1].strip() if "\n" in raw else raw

        for label in ["TASK", "CHAT", "CONTINUE"]:
            if label in raw.upper():
                return label

        return "TASK"  # 兜底
    except Exception as e:
        print(f"[YunshuIO] classify_intent error: {e}", file=sys.stderr)
        return "TASK"


def _direct_chat_reply(user_message: str, system_prompt: str) -> str:
    """
    非任务类消息：直接回复，不派生子Agent
    用精简的对话型 prompt，明确告知不要 PLAN
    """
    chat_prompt = f"""# 对话模式

{system_prompt[:800]}

你是云枢，一个 AI 助手。用户正在和你闲聊/讨论/提问，这不是一个需要执行的任务。

## 规则
- 用自然对话回复，Markdown 格式
- 不要输出 PLAN、不要分派子任务
- 不要说"我来帮你做XX"（没有任务要做）
- 直接、简洁地回答

用户消息：
{user_message}"""

    try:
        result = subprocess.run(
            ["hermes", "chat", "-q", chat_prompt, "-Q", "--yolo",
             "-m", "deepseek-chat"],
            capture_output=True, text=True, timeout=120,
            cwd=os.path.expanduser("~"), stdin=subprocess.DEVNULL
        )
        raw = result.stdout.strip()
        if raw.startswith("session_id:"):
            raw = raw.split("\n", 1)[1].strip() if "\n" in raw else raw
        return raw or "收到，我再想想怎么回答。"
    except Exception as e:
        print(f"[YunshuIO] direct_chat_reply error: {e}", file=sys.stderr)
        return "抱歉，处理您的消息时出了点问题。"


def _build_continue_context(conv_id: int) -> str:
    """
    查找上一轮的 PLAN 和子任务结果，构建继续上下文。
    返回空字符串表示无法恢复上下文 → 降级为 TASK。
    """
    try:
        prev_tasks = requests.get(
            f"{API_BASE}/api/parent-tasks/list/?conversation={conv_id}&status=REPLY",
            timeout=5
        ).json()
        if not prev_tasks:
            return ""

        last = prev_tasks[0]
        task_id = last.get("id")

        # 获取该任务的子任务结果
        children = requests.get(
            f"{API_BASE}/api/child-tasks/by-parent/{task_id}/",
            timeout=5
        ).json()

        lines = [
            f"上一条任务（#{task_id}）已完成。",
            f"最终回复摘要：{last.get('final_reply', '')[:300]}",
            ""
        ]
        for c in children:
            agent = c.get("agent_name", "?")
            status = c.get("status", "?")
            result_preview = (c.get("result") or "")[:200]
            lines.append(
                f"- [{agent}] {status}: {result_preview}"
            )

        return "\n".join(lines)
    except Exception:
        return ""


def run_yunshu_session(parent_id, conv_id, user_message, agent_profile="banni", source="web"):
    handler = YunshuCommandHandler(parent_id, conv_id, agent_profile, source=source)
    system_prompt = _load_system_prompt()

    # ══════════════════════════════════════════
    # [新增] Step 0: 意图分类 — CHAT 直接回复，不走子Agent
    # ══════════════════════════════════════════
    intent = classify_intent(user_message, conv_id)
    print(f"[YunshuIO] Intent: {intent}", file=__import__('sys').stderr)

    if intent == "CHAT":
        chat_reply = _direct_chat_reply(user_message, system_prompt)
        requests.patch(
            f"{API_BASE}/api/parent-tasks/{parent_id}/",
            json={"status": "REPLY", "final_reply": chat_reply}, timeout=10
        )
        handler._cleanup()
        return chat_reply

    # ── CONTINUE 路径：构建上下文后降级为 TASK ──
    continue_ctx = ""
    if intent == "CONTINUE":
        continue_ctx = _build_continue_context(conv_id)

    # ══════════════════════════════════════════
    # 以下为原有流程（TASK / CONTINUE降级）
    # ══════════════════════════════════════════

    requests.patch(f"{API_BASE}/api/parent-tasks/{parent_id}/",
                   json={"status": "PLANNING"}, timeout=5)

    # 检查上一条任务状态 — 如果已失败/完成，不继承上下文
    prev_ctx = ""
    try:
        prev_tasks = requests.get(
            f"{API_BASE}/api/parent-tasks/list/?conversation={conv_id}", timeout=5
        ).json()
        prev_failed = [t for t in prev_tasks if t.get("id") != parent_id and t.get("status") in ("FAILED","REPLY")]
        if prev_failed:
            last = prev_failed[0]
            prev_ctx = f"\n\n⚠️ 上一条任务（#{last['id']}）已结束（状态: {last.get('status')}），本次为新任务。"
    except Exception:
        pass

    # [新增] CONTINUE 上下文注入
    if continue_ctx:
        context = (
            f"{system_prompt}{prev_ctx}\n\n"
            f"## 上轮上下文\n{continue_ctx}\n\n"
            f"用户消息：{user_message}"
        )
    else:
        context = f"{system_prompt}{prev_ctx}\n\n用户消息：{user_message}"

    # 聚合跨端上下文（飞书 + Web），作为额外上下文注入而非覆盖
    try:
        from context_aggregator import aggregate_cross_source_context
        cross_ctx = aggregate_cross_source_context(conv_id, user_message)
        if cross_ctx:
            # 注意：追加在 system_prompt 之后、user_message 之前，不丢失 prev_ctx/continue_ctx
            context = (
                f"{system_prompt}{prev_ctx}\n\n"
                f"{cross_ctx}\n\n"
            )
            if continue_ctx:
                context += f"## 上轮上下文\n{continue_ctx}\n\n"
            context += f"用户消息：{user_message}"
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

        # ═══ REPLY 阶段防护：如果当前上下文是最终回复，LLM 却输出 PLAN，
        #      说明 LLM 混乱，直接 fallback ═══
        _in_reply_phase = context.startswith("# 最终回复")
        if _in_reply_phase and ("PLAN FAIL" in reply or "PLAN:" in reply[:200]):
            import sys
            print(f"[YunshuIO] ⚠️ REPLY阶段LLM输出PLAN（混乱），直接fallback", file=sys.stderr)
            _push_progress(conv_id, "⚠️ 云枢响应异常，使用兜底回复", source=handler.source)
            handler._cleanup()
            return _fallback_reply(parent_id, conv_id, source=handler.source)

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
                    elif cmd_name == "SPAWN_TESTER":
                        response = handler.spawn("tester", m.group(1))
                    elif cmd_name == "CHECK":
                        response = handler.check(m.group(1))
                    elif cmd_name == "WAIT_ALL":
                        response = handler.wait_all()
                    elif cmd_name == "KILL":
                        response = handler.kill(m.group(1))
                    elif cmd_name == "REPLY":
                        final = m.group(1).strip()
                        err = handler.reply(final)
                        if err and err.startswith("ERROR"):
                            import sys
                            print(f"[YunshuIO] ⚠️ REPLY命令出口校验拒绝: {final[:80]}", file=sys.stderr)
                            # 不返回，让兜底逻辑处理
                        else:
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

        # 兜底：整轮无命令 → 跑偏检测 + 重试
        if not any_command:
            reply_text = reply.strip()
            if _looks_like_code_or_garbage(reply_text):
                import sys
                print(f"[YunshuIO] ⚠️ 兜底检测：输出疑似代码/测试内容，重试一轮", file=sys.stderr)
                retry_ctx = (
                    f"# 紧急重试\n\n"
                    f"刚才的输出不像是给用户的最终回复。\n\n"
                    f"用户需求：{user_message[:300]}\n\n"
                    f"请直接输出最终回复（Markdown格式），不要输出代码、测试、或诊断内容。"
                )
                retry_reply = _hermes_q(retry_ctx, agent_profile)
                if retry_reply and not _looks_like_code_or_garbage(retry_reply):
                    err = handler.reply(retry_reply.strip())
                    if err and err.startswith("ERROR"):
                        print(f"[YunshuIO] ⚠️ 重试后 reply() 拒绝: {err}", file=sys.stderr)
                    else:
                        handler._cleanup()
                        return retry_reply.strip()
                print(f"[YunshuIO] ⚠️ 重试仍跑偏，使用兜底回复", file=sys.stderr)
                handler._cleanup()
                return _fallback_reply(parent_id, conv_id, source=handler.source)
            handler.reply(reply_text)
            handler._cleanup()
            return reply_text

        # 构建下一轮 context
        if response_lines:
            # ── PLAN FAIL（云枢判定无任务）→ 直接友好回复，不进入 REFLECT 循环 ──
            if any("no_task" in r for r in response_lines):
                reply = "您好！我是云枢调度器。请下发一个具体任务，我会协调 Banni（搜索/工程）、Basir（分析/推断）、云衡（测试/审查）三个子Agent为您服务。"
                handler.reply(reply)
                handler._cleanup()
                return reply

            # ═══ 方案 B: PLAN 刚解析 → 代码接管执行 ═══
            if any("plan_parsed" in r for r in response_lines):
                if plan_graph and plan_graph.validate():
                    # 代码按依赖图自动 spawn + wait + collect
                    exec_result = execute_plan_graph(handler, plan_graph)
                    results_text = _collect_children_results(handler)
                    _push_progress(conv_id, "🔍 REFLECT 自检中...", source=handler.source)
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
                # 反射轮次耗尽 → 强制结束
                if handler.reflect_state.current_round >= handler.reflect_state.MAX_ROUNDS:
                    _save_failed_reply(parent_id, conv_id, handler, source=handler.source)
                    break

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
                results_text = _summarize_children_results(handler, max_per_child=600)
                context = (
                    f"# 最终回复\n\n"
                    f"用户需求：{user_message[:300]}\n\n"
                    f"## 子任务结果（核心摘要）\n{results_text}\n\n"
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
            results_text = _summarize_children_results(handler, max_per_child=600)
            context = (
                f"# 最终回复\n\n"
                f"用户需求：{user_message[:300]}\n\n"
                f"## 子任务结果（核心摘要）\n{results_text}\n\n"
                f"## 指令\n"
                f"REFLECT 已通过。根据子任务结果和用户需求，"
                f"立即 REPLY 输出最终回答（Markdown格式）。"
                f"禁止 SPAWN，禁止 PLAN。"
            )
        else:
            break

    handler._cleanup()
    return _fallback_reply(parent_id, conv_id, source=handler.source)


def _hermes_q(message, profile):
    try:
        env = os.environ.copy()
        env["HERMES_PROFILE"] = profile
        r = subprocess.run(
            ["hermes", "chat", "-q", message, "-Q", "--yolo"],
            capture_output=True, text=True, timeout=300,
            cwd=os.path.expanduser("~"), env=env, stdin=subprocess.DEVNULL
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
- **收到任务时，第一轮只能输出 PLAN，禁止输出其他任何内容**
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
  - id: t3, agent: tester, desc: 代码审查和测试, deps: [t1]

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


def _fallback_reply(parent_id, conv_id, source="web"):
    reply = "系统在处理您的请求时遇到问题，请稍后重试。"
    _save_failed_reply(parent_id, conv_id, None, reply, source=source)
    return reply

def _save_failed_reply(parent_id, conv_id, handler=None, reply=None, source="web"):
    """保存失败结果到数据库 + 写入会话消息"""
    if reply is None:
        reason = handler.reflect_state.fail_reason if handler else "未知错误"
        children_count = len(handler.children) if handler else 0
        reply = f"## ⚠️ 任务执行失败\n\n**原因**: {reason[:200]}\n\n**子任务数**: {children_count}\n\n**建议**: 请检查 Agent Profile 配置后重试。"
    try:
        # 标记 parent task 为 FAILED
        current = requests.get(f"{API_BASE}/api/parent-tasks/{parent_id}/", timeout=5).json()
        if current.get("status") not in ("REPLY",):
            requests.patch(
                f"{API_BASE}/api/parent-tasks/{parent_id}/",
                json={"status": "FAILED", "final_reply": reply}, timeout=10
            )
    except Exception:
        pass
    try:
        # 写入会话消息，让用户看到失败原因（携带 source 以保留来源追踪）
        requests.post(
            f"{API_BASE}/api/messages/",
            json={"conversation": conv_id, "role": "agent", "content": reply, "source": source},
            timeout=10
        )
    except Exception:
        pass
    return reply
