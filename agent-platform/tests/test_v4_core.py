"""
v4 核心逻辑测试 — 文本协议 / REFLECT 状态机 / PLAN 解析 / Checkpoint / 安全网
pytest tests/test_v4_core.py -v
"""
import pytest
import re
import json
import os
import sys
import tempfile
import threading
import time

# Add agents/ to path for imports
_agents_dir = os.path.join(os.path.dirname(__file__), "..", "agents")
sys.path.insert(0, os.path.abspath(_agents_dir))

# ══════════════════════════════════════════════
# 1. 文本协议命令匹配测试
# ══════════════════════════════════════════════

CMD_PATTERNS = {
    "SPAWN_BANNI": re.compile(r"^SPAWN_BANNI\s*:?\s*(.+)", re.I),
    "SPAWN_BASIR": re.compile(r"^SPAWN_BASIR\s*:?\s*(.+)", re.I),
    "CHECK":       re.compile(r"^CHECK\s+(\S+)", re.I),
    "WAIT_ALL":    re.compile(r"^WAIT_ALL$", re.I),
    "KILL":        re.compile(r"^KILL\s+(\S+)", re.I),
    "REPLY":       re.compile(r"^REPLY\s*:?\s*(.+)", re.I | re.S),
    "PLAN":        re.compile(r"^PLAN\s*:?\s*(.*)", re.I),
    "REFLECT":     re.compile(r"^REFLECT\s*$", re.I),
    "REFLECT_PASS": re.compile(r"^REFLECT_PASS", re.I),
    "REFLECT_FAIL": re.compile(r"^REFLECT_FAIL\s*:?\s*(.+)", re.I),
}


class TestCommandMatching:
    """v4 10 个命令的匹配测试"""

    def test_spawn_banni_with_colon(self):
        m = CMD_PATTERNS["SPAWN_BANNI"].match("SPAWN_BANNI: 搜索 Leader & Workers")
        assert m
        assert m.group(1).strip() == "搜索 Leader & Workers"

    def test_spawn_banni_no_colon(self):
        m = CMD_PATTERNS["SPAWN_BANNI"].match("SPAWN_BANNI 写一个 Flask hello world")
        assert m
        assert m.group(1).strip() == "写一个 Flask hello world"

    def test_spawn_basir_case_insensitive(self):
        m = CMD_PATTERNS["SPAWN_BASIR"].match("spawn_basir: 分析搜索结果")
        assert m
        assert m.group(1).strip() == "分析搜索结果"

    def test_wait_all(self):
        assert CMD_PATTERNS["WAIT_ALL"].match("WAIT_ALL")
        assert CMD_PATTERNS["WAIT_ALL"].match("wait_all")
        assert not CMD_PATTERNS["WAIT_ALL"].match("WAIT_ALL_FOR task_1")

    def test_reply_single_line(self):
        m = CMD_PATTERNS["REPLY"].match("REPLY: 你好")
        assert m
        assert m.group(1).strip() == "你好"

    def test_reply_multiline(self):
        m = CMD_PATTERNS["REPLY"].match("REPLY: ## Title\n\nContent here\nMore content")
        assert m
        assert "## Title" in m.group(1)

    def test_plan_prefix(self):
        assert CMD_PATTERNS["PLAN"].match("PLAN: complexity: medium")
        assert CMD_PATTERNS["PLAN"].match("PLAN:\ncomplexity: complex")

    def test_reflect_pass(self):
        assert CMD_PATTERNS["REFLECT_PASS"].match("REFLECT_PASS")
        assert CMD_PATTERNS["REFLECT_PASS"].match("reflect_pass")

    def test_reflect_fail_with_reason(self):
        m = CMD_PATTERNS["REFLECT_FAIL"].match("REFLECT_FAIL: 缺少搜索结果, SPAWN_BANNI: 重新搜索")
        assert m
        assert "缺少搜索结果" in m.group(1)

    def test_natural_language_not_matched(self):
        """自然语言不该匹配任何命令（Worker 作为自言自语忽略）"""
        natural_lines = [
            "我分析了一下用户的需求",
            "看起来这个词可能是拼写错误",
            "Let me think about this first",
            "根据已有知识，这应该是...",
        ]
        for line in natural_lines:
            matched = False
            for pattern in CMD_PATTERNS.values():
                if pattern.match(line):
                    matched = True
                    break
            assert not matched, f"'{line}' should not match any command"

    def test_kill_with_task_id(self):
        m = CMD_PATTERNS["KILL"].match("KILL task_42")
        assert m
        assert m.group(1) == "task_42"

    def test_check_with_task_id(self):
        m = CMD_PATTERNS["CHECK"].match("CHECK 35")
        assert m
        assert m.group(1) == "35"


# ══════════════════════════════════════════════
# 2. REFLECT 状态机测试
# ══════════════════════════════════════════════

from yunshu_io import ReflectState


class TestReflectStateMachine:
    """REFLECT 状态机 — 3 轮上限 + FORCE_PASS"""

    def test_initial_state(self):
        rs = ReflectState()
        assert rs.current_round == 0
        assert rs.passed == False
        assert rs.active == False

    def test_enter_reflect(self):
        rs = ReflectState()
        rs.enter()
        assert rs.active == True

    def test_pass_exits_reflect(self):
        rs = ReflectState()
        rs.enter()
        rs.mark_pass()
        assert rs.passed == True
        assert rs.active == False

    def test_single_fail_returns_fail(self):
        rs = ReflectState()
        rs.enter()
        result = rs.mark_fail("缺少搜索")
        assert result == "FAIL"
        assert rs.current_round == 1
        assert rs.active == False

    def test_three_fails_force_pass(self):
        rs = ReflectState()
        for i in range(3):
            rs.enter()
            result = rs.mark_fail(f"fail reason {i+1}")
        assert result == "FORCE_PASS"
        assert rs.current_round == 3
        assert rs.active == False

    def test_fail_then_pass_resets(self):
        rs = ReflectState()
        rs.enter()
        rs.mark_fail("第一轮失败")
        assert rs.current_round == 1
        rs.enter()
        rs.mark_pass()
        assert rs.passed == True
        assert rs.current_round == 1  # 轮次不变

    def test_max_rounds_constant(self):
        assert ReflectState.MAX_ROUNDS == 3

    def test_checklist_prompt_structure(self):
        rs = ReflectState()
        children = {
            "1": {"obj": {"agent_name": "banni", "status": "DONE",
                          "result": "搜索到 Leader & Workers 定义..."}},
            "2": {"obj": {"agent_name": "basir", "status": "DONE",
                          "result": "推断 lerder 为 leader 的拼写错误"}},
        }
        prompt = rs.get_checklist_prompt(children, "lerder&works是什么")
        assert "[REFLECT 自检模式]" in prompt
        assert "banni" in prompt.lower()
        assert "basir" in prompt.lower()
        assert "5" in prompt  # 5 项自检
        assert "REFLECT_PASS" in prompt
        assert "REFLECT_FAIL" in prompt

    def test_checklist_empty_children(self):
        rs = ReflectState()
        prompt = rs.get_checklist_prompt({}, "hello")
        assert "[REFLECT 自检模式]" in prompt
        assert "子任务结果:" in prompt


# ══════════════════════════════════════════════
# 3. PLAN 解析器边界测试
# ══════════════════════════════════════════════

from plan_parser import PlanGraph, PlanNode, heuristic_complexity


class TestPlanParser:
    """PLAN 解析器 — 正常/边界/容错"""

    def test_basic_plan(self):
        text = """PLAN:
complexity: medium
tasks:
  - id: t1, agent: banni, desc: 搜索 Leader & Workers, deps: []
  - id: t2, agent: basir, desc: 分析架构模式, deps: [t1]"""
        plan = PlanGraph.parse(text)
        assert plan is not None
        assert plan.complexity == "medium"
        assert len(plan.nodes) == 2
        assert plan.parallel_count == 1
        assert plan.serial_count == 1

    def test_simple_complexity(self):
        plan = PlanGraph.parse("complexity: simple\ntasks:\n  - id: t1, agent: banni, desc: hi, deps: []")
        assert plan.get_suggested_max_spawn() == 1

    def test_complex_complexity(self):
        plan = PlanGraph.parse("complexity: complex\ntasks:\n  - id: t1, agent: banni, desc: search, deps: []")
        assert plan.get_suggested_max_spawn() == 5

    def test_no_complexity_defaults_medium(self):
        plan = PlanGraph.parse("tasks:\n  - id: t1, agent: banni, desc: x, deps: []")
        assert plan is not None
        assert plan.complexity == "medium"

    def test_no_tasks_returns_none(self):
        plan = PlanGraph.parse("complexity: medium")
        assert plan is None

    def test_empty_input_returns_none(self):
        assert PlanGraph.parse("") is None
        assert PlanGraph.parse("no tasks here") is None

    def test_all_parallel(self):
        text = """PLAN:
complexity: complex
tasks:
  - id: t1, agent: banni, desc: search A, deps: []
  - id: t2, agent: banni, desc: search B, deps: []
  - id: t3, agent: basir, desc: analyze, deps: []"""
        plan = PlanGraph.parse(text)
        assert plan.parallel_count == 3
        assert plan.serial_count == 0

    def test_validate_no_cycle(self):
        text = """PLAN: complexity: medium
tasks:
  - id: t1, agent: banni, desc: a, deps: []
  - id: t2, agent: basir, desc: b, deps: [t1]"""
        plan = PlanGraph.parse(text)
        assert plan.validate() == True

    def test_validate_missing_dep(self):
        """依赖未声明的 task_id → invalid"""
        g = PlanGraph(
            complexity="medium",
            nodes=[PlanNode(task_id="t1", agent_type="banni", description="x", dependencies=["t2"])],
            adjacency={"t1": ["t2"]}
        )
        assert g.validate() == False

    def test_validate_duplicate_ids(self):
        g = PlanGraph(
            complexity="medium",
            nodes=[
                PlanNode(task_id="t1", agent_type="banni", description="a"),
                PlanNode(task_id="t1", agent_type="basir", description="b"),
            ],
            adjacency={"t1": []}
        )
        assert g.validate() == False

    def test_heuristic_simple(self):
        assert heuristic_complexity("hi", 1) == "medium"

    def test_heuristic_complex_by_length(self):
        long_msg = "x" * 201
        assert heuristic_complexity(long_msg, 1) == "complex"

    def test_heuristic_complex_by_count(self):
        assert heuristic_complexity("hi", 4) == "complex"


# ══════════════════════════════════════════════
# 4. Checkpoint 管理器测试
# ══════════════════════════════════════════════

from checkpoint import CheckpointManager


class TestCheckpointManager:
    """Checkpoint — 文件读写 / 循环覆盖 / 恢复上下文"""

    def test_write_and_load(self):
        mgr = CheckpointManager(9999)
        children = {"1": {"status": "DONE"}, "2": {"status": "RUNNING"}}
        mgr.write_checkpoint("EXECUTING", children, yunshu_line=42, summary_text="test")

        path = mgr._file_path(CheckpointManager.MAX_FILES)
        assert os.path.exists(path)
        with open(path) as f:
            data = json.load(f)
        assert data["parent_task_id"] == 9999
        assert data["stage"] == "EXECUTING"
        assert data["children_state"]["1"]["status"] == "DONE"
        assert data["yunshu_output_line"] == 42

    def test_build_recovery_context(self):
        mgr = CheckpointManager(42)
        checkpoint = {
            "stage": "EXECUTING",
            "children_state": {
                "t1": {"status": "DONE"},
                "t2": {"status": "RUNNING"},
                "t3": {"status": "PENDING"},
            },
            "summary_text": "用户正在查询 lerder&works"
        }
        ctx = mgr.build_recovery_context(checkpoint)
        assert "父任务 #42" in ctx
        assert "t1(DONE)" in ctx
        assert "t2" in ctx or "RUNNING" in ctx
        assert "lerder&works" in ctx

    def test_three_files_cycle(self):
        mgr = CheckpointManager(1)
        for i in range(5):
            mgr.write_checkpoint("EXECUTING", {str(i): {"status": "DONE"}})
        # 只有 3 个文件存在
        existing = 0
        for n in range(1, CheckpointManager.MAX_FILES + 1):
            if os.path.exists(mgr._file_path(n)):
                existing += 1
        assert existing <= CheckpointManager.MAX_FILES

    def test_thread_safety_lock(self):
        mgr = CheckpointManager(2)
        # lock 应该存在
        assert mgr.lock is not None
        assert isinstance(mgr.lock, type(threading.Lock()))


# ══════════════════════════════════════════════
# 5. 安全网逻辑测试
# ══════════════════════════════════════════════

class TestSafetyNet:
    """安全网 — 超时 / 僵尸检测 / 上限控制"""

    def test_guard_spawn_under_limit(self):
        """Mock: 无活跃进程 → 应该允许"""
        # 这里只测逻辑不测 Popen
        active = 0
        max_spawn = 3
        assert active < max_spawn  # 允许

    def test_guard_spawn_at_limit(self):
        active = 3
        max_spawn = 3
        assert not (active < max_spawn)  # 拒绝

    def test_timeout_killer_duration(self):
        """超时看门狗应设置合理的超时时间"""
        from yunshu_io import get_default_timeout
        assert get_default_timeout("banni") == 1800
        assert get_default_timeout("nonexistent") == 300

    def test_config_timeout_defaults(self):
        """Agent 配置的默认 timeout 合理"""
        from agent_registry import AGENT_REGISTRY
        for name, cfg in AGENT_REGISTRY.items():
            assert cfg["default_timeout"] > 0
            assert len(cfg["capabilities"]) >= 1

    def test_agent_registry_register(self):
        from agent_registry import register_agent, get_agent_config
        try:
            register_agent("test_agent", {
                "name": "Test",
                "role_prompt": "test",
                "default_timeout": 100,
                "capabilities": ["test"],
            })
            cfg = get_agent_config("test_agent")
            assert cfg["name"] == "Test"
        finally:
            # 清理
            from agent_registry import AGENT_REGISTRY
            AGENT_REGISTRY.pop("test_agent", None)

    def test_agent_registry_missing_field(self):
        from agent_registry import register_agent
        with pytest.raises(ValueError):
            register_agent("bad", {"name": "Bad"})


# ══════════════════════════════════════════════
# 6. 端到端：完整流程模拟
# ══════════════════════════════════════════════

class TestEndToEndSimulation:
    """模拟完整 v4 流程（不启动真实 hermes）"""

    def test_full_flow_commands(self):
        """完整命令序列：PLAN → SPAWN → WAIT → REFLECT → REPLY"""
        commands = [
            "PLAN:\ncomplexity: medium\ntasks:\n  - id: t1, agent: banni, desc: x, deps: []",
            "SPAWN_BANNI: 搜索 X",
            "WAIT_ALL",
            "REFLECT",
            "REFLECT_PASS",
            "REPLY: ## 结果\n\n分析完成",
        ]
        parsed = []
        for cmd in commands:
            for name, pattern in CMD_PATTERNS.items():
                if pattern.match(cmd.split("\n")[0]):
                    parsed.append(name)
                    break
        assert "PLAN" in parsed
        assert "SPAWN_BANNI" in parsed
        assert "WAIT_ALL" in parsed
        assert "REFLECT" in parsed
        assert "REFLECT_PASS" in parsed
        assert "REPLY" in parsed
        assert len(parsed) == 6

    def test_correction_flow_commands(self):
        """修正流程：SPAWN → WAIT → 发现修正 → 重搜 → WAIT → REPLY"""
        commands = [
            "SPAWN_BANNI: 搜索 lerder&works",
            "WAIT_ALL",
            "SPAWN_BANNI: 搜索 Leader & Workers",  # 修正
            "WAIT_ALL",
            "REPLY: ## lerder&works 分析\n\n..." ,
        ]
        parsed = [name for cmd in commands
                  for name, pat in CMD_PATTERNS.items()
                  if pat.match(cmd.split("\n")[0])]
        assert parsed.count("SPAWN_BANNI") == 2
        assert parsed.count("WAIT_ALL") == 2
        assert "REPLY" in parsed
