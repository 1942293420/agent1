#!/usr/bin/env python3
"""
Orchestrator — 多 Agent 调度中台

设计原则：
  - LLM 负责"想"：动态生成执行计划 JSON
  - Python 负责"做"：依赖解析、并行调度、超时重试、状态管理

Plan 结构：
{
  "summary": "一句话概述",
  "steps": [
    {"id": "step_1", "agent": "数据分析师", "task": "...", "depends_on": [], "output_key": "result"},
    {"id": "step_2", "agent": "全栈工程师", "task": "...",   "depends_on": ["step_1"]}
  ]
}
"""

import json, time, os, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Optional

import requests

# ─── 配置 ──────────────────────────────────────────
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
AGENT_PLATFORM = "http://localhost:8001"
MAX_CONCURRENT = 3
STEP_TIMEOUT = 300  # 单步超时（秒）

def _get_deepseek_key():
    env_path = os.path.expanduser("~/.hermes/profiles/Banni/.env")
    if os.path.exists(env_path):
        for line in open(env_path):
            if line.startswith("DEEPSEEK_API_KEY="):
                return line.split("=", 1)[1].strip().strip("'\"")
    return os.environ.get("DEEPSEEK_API_KEY", "")

DEEPSEEK_KEY = _get_deepseek_key()


# ═══════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════

@dataclass
class PlanStep:
    id: str
    agent: str
    task: str
    depends_on: list = field(default_factory=list)
    output_key: str = ""
    input_from: dict = field(default_factory=dict)
    status: str = "pending"        # pending | running | done | failed
    result: Optional[str] = None
    task_id: Optional[int] = None  # 对应的 platform Task ID
    started_at: Optional[float] = None
    duration: float = 0.0

@dataclass
class ExecutionPlan:
    plan_id: str
    summary: str
    steps: list  # list[PlanStep]
    conversation_id: int = 0
    status: str = "pending"  # pending | running | done | partial_fail | failed


# ═══════════════════════════════════════════════════
# Phase 1: PlanGen — LLM 动态生成执行计划
# ═══════════════════════════════════════════════════

PLAN_PROMPT = """你是多 Agent 系统的豆角云枢。根据用户指令和可用 Agent 列表，生成一个执行计划。

可用 Agent：
{agent_list}

输出一个严格 JSON，格式：
{{
  "summary": "一句话概述计划",
  "steps": [
    {{
      "id": "step_1",
      "agent": "Agent名称（必须从上面列表选）",
      "task": "该步骤详细任务描述（具体、可执行）",
      "depends_on": [],
      "output_key": "step_1_result"
    }},
    {{
      "id": "step_2",
      "agent": "Agent名称",
      "task": "任务描述",
      "depends_on": ["step_1"],
      "output_key": "step_2_result"
    }}
  ]
}}

规则：
1. agent 字段必须严格匹配可用 Agent 列表中的名称
2. 如果步骤依赖前面的步骤，必须在 depends_on 中注明其 id
3. 每个步骤的 task 要具体、可执行，不要模糊描述
4. 能并行的步骤不要串行（不依赖的就分开）
5. ⚠️ 每个步骤必须在 15-25 次工具调用内完成。大任务必须拆成多个小步骤，不要一个步骤试图"审计全部代码"
6. 超过 5 个步骤的计划，分阶段执行（先给用户第一阶段）
7. 只输出 JSON，不要任何解释文字"""


def get_available_agents() -> list[dict]:
    """从 agent-platform 获取在线 Agent 列表"""
    try:
        resp = requests.get(f"{AGENT_PLATFORM}/api/agents/",
                           params={"page_size": 50, "status": "online"}, timeout=5)
        agents = resp.json().get("results", [])
        return [
            {"name": a["name"], "portrait": a.get("portrait", "")[:200]}
            for a in agents
        ]
    except Exception:
        return [{"name": "数据分析师", "portrait": "数据分析专家"},
                {"name": "小温", "portrait": "全栈工程师，负责开发和运维"}]


def generate_plan(user_message: str, conversation_id: int) -> Optional[ExecutionPlan]:
    """LLM 根据用户消息 + 可用 Agent 生成执行计划"""
    agents = get_available_agents()
    agent_list = "\n".join(
        f"  - {a['name']}: {a['portrait'][:100]}" for a in agents
    )

    prompt = PLAN_PROMPT.format(agent_list=agent_list)
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"用户指令：{user_message}\n\n对话ID: {conversation_id}\n\n请生成执行计划JSON。"}
    ]

    try:
        resp = requests.post(
            DEEPSEEK_URL,
            headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"},
            json={"model": "deepseek-v4-pro", "messages": messages, "temperature": 0.3, "max_tokens": 2000},
            timeout=30,
        )
        content = resp.json()["choices"][0]["message"]["content"]

        # 提取 JSON（LLM 可能在前后加文字）
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            plan_dict = json.loads(content[start:end])
        else:
            return None

        # 校验 agent 名称
        valid_names = {a["name"] for a in agents}
        for s in plan_dict.get("steps", []):
            if s["agent"] not in valid_names:
                s["_warning"] = f"Agent '{s['agent']}' 不在线，将尝试调度"

        plan = ExecutionPlan(
            plan_id=f"plan_{int(time.time())}",
            summary=plan_dict.get("summary", "执行计划"),
            steps=[PlanStep(**s) for s in plan_dict.get("steps", [])],
            conversation_id=conversation_id,
        )
        return plan
    except Exception as e:
        print(f"[Orchestrator] PlanGen failed: {e}")
        return None


# ═══════════════════════════════════════════════════
# Agent 工具集 — 子 Agent 可调用的系统工具
# ═══════════════════════════════════════════════════

import subprocess, re as re_mod

TOOL_DEFINITIONS = """你可以使用以下工具来完成任务。在回复中插入工具调用标签来使用它们：

<tool name="terminal">命令</tool>
  执行 shell 命令，返回输出（前 3000 字符）。工作目录: /home/jiangli
  ⚠️ 命令必须是单个命令/脚本，不要用管道解释器（如 curl|python3）
  示例: <tool name="terminal">ls -la ~/projects</tool>
  示例: <tool name="terminal">wc -l ~/projects/agent-platform/agents/*.py</tool>

<tool name="read_file">文件路径</tool>
  读取文件内容（前 200 行）。必须是绝对路径。
  示例: <tool name="read_file">/home/jiangli/projects/agent-platform/README.md</tool>

<tool name="write_file">文件路径\n文件内容</tool>
  创建或覆盖文件。第一行是路径，之后是内容。慎重使用。
  示例: <tool name="write_file">/home/jiangli/test.txt\nhello world</tool>

<tool name="search_files">搜索模式</tool>
  搜索文件内容或文件名。用 glob: 前缀搜文件名，否则搜内容。
  示例: <tool name="search_files">glob:*.py</tool>
  示例: <tool name="search_files">def execute_plan</tool>

工作流程：
1. 分析任务，决定用什么工具
2. 发出工具调用标签
3. 根据工具结果继续分析或发出下一个工具调用
4. 最终给出完整的回复（不要再包含工具标签）"""


def _execute_tool(tool_name: str, tool_arg: str) -> str:
    """执行单个工具调用，返回结果字符串"""
    tool_arg = tool_arg.strip()
    
    if tool_name == "terminal":
        # 安全检查：拒绝危险命令
        dangerous = ["rm -rf", "sudo", "mkfs", "dd if=", ":(){", "> /dev/"]
        if any(d in tool_arg for d in dangerous):
            return "[拒绝] 危险命令"
        try:
            result = subprocess.run(
                tool_arg, shell=True, capture_output=True, text=True,
                timeout=30, cwd="/home/jiangli",
                env={**os.environ, "HOME": "/home/jiangli"}
            )
            output = (result.stdout + result.stderr)[:3000]
            return output or "(无输出)"
        except subprocess.TimeoutExpired:
            return "[超时] 命令执行超过 30 秒"
        except Exception as e:
            return f"[错误] {str(e)}"
    
    elif tool_name == "read_file":
        path = tool_arg.split("\n")[0].strip()
        if not path.startswith("/"):
            return "[错误] 必须使用绝对路径"
        try:
            with open(path) as f:
                lines = f.readlines()[:200]
            return "".join(f"{i+1}|{l}" for i, l in enumerate(lines))
        except FileNotFoundError:
            return f"[错误] 文件不存在: {path}"
        except PermissionError:
            return f"[错误] 无权限读取: {path}"
        except Exception as e:
            return f"[错误] {str(e)}"
    
    elif tool_name == "write_file":
        parts = tool_arg.split("\n", 1)
        if len(parts) < 2:
            return "[错误] 格式: <tool name=\"write_file\">路径\\n内容</tool>"
        path = parts[0].strip()
        content = parts[1]
        if not path.startswith("/home/jiangli/"):
            return "[错误] 只能写入 /home/jiangli/ 下的文件"
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(content)
            return f"[OK] 已写入 {path} ({len(content)} 字符)"
        except Exception as e:
            return f"[错误] {str(e)}"
    
    elif tool_name == "search_files":
        if tool_arg.startswith("glob:"):
            pattern = tool_arg[5:].strip()
            try:
                result = subprocess.run(
                    ["find", "/home/jiangli", "-maxdepth", "5", "-name", pattern,
                     "-not", "-path", "*/node_modules/*", "-not", "-path", "*/.git/*",
                     "-not", "-path", "*/venv/*", "-not", "-path", "*/__pycache__/*"],
                    capture_output=True, text=True, timeout=10
                )
                return result.stdout[:3000] or "(无匹配)"
            except Exception as e:
                return f"[错误] {str(e)}"
        else:
            # grep
            try:
                result = subprocess.run(
                    ["grep", "-rn", "--include=*.py", "--include=*.js", "--include=*.jsx",
                     "--include=*.md", "--include=*.html", "--include=*.css",
                     "-l", tool_arg, "/home/jiangli/projects"],
                    capture_output=True, text=True, timeout=10
                )
                return result.stdout[:3000] or "(无匹配)"
            except Exception as e:
                return f"[错误] {str(e)}"
    
    return f"[错误] 未知工具: {tool_name}"


def _execute_step_with_claude(step: PlanStep, results: dict) -> tuple[str, str]:
    """
    使用 Claude Code CLI 执行子任务——和调度平台完全相同的工具权限
    无轮次限制，能处理大型审计任务
    """
    agent_name = step.agent
    portrait = f"你是{agent_name}，一个有工具访问能力的AI助手。"
    try:
        resp = requests.get(f"{AGENT_PLATFORM}/api/agents/",
                           params={"search": agent_name, "page_size": 5}, timeout=5)
        for a in resp.json().get("results", []):
            if a.get("name") == agent_name and a.get("portrait"):
                portrait = a["portrait"]
                break
    except Exception:
        pass

    context = ""
    for dep_id, dep_info in step.input_from.items():
        src_step_id = dep_info.split(".")[0] if "." in dep_info else dep_info
        if src_step_id in results and results[src_step_id].result:
            context += f"\n\n上游步骤 {src_step_id} 的输出：\n{results[src_step_id].result[:2000]}"

    prompt = f"""{portrait}

任务：{step.task}{context}

请完成以上任务。你有完整的文件系统访问和命令执行权限。用中文回复最终结果。"""

    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--dangerously-skip-permissions", "--max-turns", "30",
             "--output-format", "text"],
            capture_output=True, text=True, timeout=STEP_TIMEOUT,
            cwd="/home/jiangli",
            env={**os.environ, "HOME": "/home/jiangli"}
        )
        output = result.stdout.strip()
        if result.returncode == 0 and output:
            return "completed", output[:3000]
        else:
            stderr = result.stderr[:500] if result.stderr else "无输出"
            return "failed", f"Claude Code 退出码={result.returncode}: {stderr}"
    except subprocess.TimeoutExpired:
        return "failed", "Claude Code 执行超时（5分钟）"
    except FileNotFoundError:
        return "claude_not_found", ""  # 回退到 ReAct
    except Exception as e:
        return "failed", str(e)


def _execute_step_with_tools(step: PlanStep, results: dict) -> tuple[str, str]:
    """
    子 Agent 执行入口：
      1. 优先用 Claude Code CLI（无限轮次，完整工具权限）
      2. 回退到 ReAct 循环（有限轮次）
    """
    # 先尝试 Claude Code
    status, result = _execute_step_with_claude(step, results)
    if status != "claude_not_found":
        print(f"[Orchestrator] Claude Code: {status} ← {result[:80] if result else '(空)'}")
        return status, result

    # 回退到 ReAct 循环
    agent_name = step.agent
    
    # 获取 Agent 画像
    portrait = f"你是{agent_name}，一个有工具访问能力的AI助手。"
    try:
        resp = requests.get(f"{AGENT_PLATFORM}/api/agents/",
                           params={"search": agent_name, "page_size": 5}, timeout=5)
        for a in resp.json().get("results", []):
            if a.get("name") == agent_name and a.get("portrait"):
                portrait = a["portrait"]
                break
    except Exception:
        pass

    # 构建提示词
    context = ""
    for dep_id, dep_info in step.input_from.items():
        src_step_id = dep_info.split(".")[0] if "." in dep_info else dep_info
        if src_step_id in results and results[src_step_id].result:
            context += f"\n\n【上游步骤 {src_step_id} 的输出】\n{results[src_step_id].result[:1000]}"

    system_prompt = f"""{portrait}

当前任务来自豆角云枢的分配。请认真完成。用中文回复。

{TOOL_DEFINITIONS}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"请完成以下任务：\n{step.task}{context}"}
    ]

    # ── ReAct 循环 ──
    MAX_ITERATIONS = 25
    for iteration in range(MAX_ITERATIONS):
        try:
            resp = requests.post(
                DEEPSEEK_URL,
                headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"},
                json={"model": "deepseek-v4-pro", "messages": messages, "temperature": 0.3, "max_tokens": 3000},
                timeout=120,
            )
            reply = resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return "failed", str(e)

        # 检查是否有工具调用
        tool_match = re_mod.search(r'<tool\s+name="(\w+)">(.*?)</tool>', reply, re_mod.DOTALL)
        
        if tool_match:
            tool_name = tool_match.group(1)
            tool_arg = tool_match.group(2)
            print(f"[Orchestrator] 工具调用: {tool_name} ← {tool_arg[:80]}")
            
            # 执行工具
            tool_result = _execute_tool(tool_name, tool_arg)
            
            # 追加到对话
            messages.append({"role": "assistant", "content": reply})
            messages.append({"role": "user", "content": f"<tool_result name=\"{tool_name}\">\n{tool_result}\n</tool_result>\n请继续。"})
        else:
            # 无工具调用 → 最终回复（清理可能的残余工具标签）
            clean_reply = re_mod.sub(r'<tool[^>]*>.*?</tool>', '', reply, flags=re_mod.DOTALL).strip()
            return "completed", clean_reply

    # 达到最大迭代次数 → 返回最后的有效回复（清理工具标签）
    clean_reply = re_mod.sub(r'<tool[^>]*>.*?</tool>', '', reply, flags=re_mod.DOTALL).strip()
    if not clean_reply:
        return "failed", f"任务执行达到最大轮次（{MAX_ITERATIONS}轮），未能完成。请简化任务重试。"
    return "partial", clean_reply


def _push_progress(conversation_id: int, step: PlanStep):
    """通过 agent-platform 推送进度消息到对话"""
    status_icon = {"running": "🔄", "done": "✅", "failed": "❌", "pending": "⏳"}
    icon = status_icon.get(step.status, "ℹ️")
    content = f"{icon} **{step.agent}** — {step.task[:80]}\n⏱️ {step.duration:.1f}s"
    if step.status == "done":
        content += f"\n📤 结果：{step.result[:200] if step.result else '(完成)'}"

    try:
        requests.post(f"{AGENT_PLATFORM}/api/messages/", json={
            "conversation": conversation_id,
            "role": "system",
            "content": content,
            "source": "web",
        }, timeout=5)
    except Exception:
        pass


def execute_plan(plan: ExecutionPlan) -> dict:
    """
    精确执行执行计划：
      1. 拓扑排序 → 确定执行顺序
      2. 并行调度无依赖步骤
      3. 收集结果 → 注入下游
      4. 超时/失败处理
    """
    results = {}  # step_id → PlanStep (with result)
    pending = {s.id: s for s in plan.steps}

    plan.status = "running"
    print(f"[Orchestrator] 开始执行 {plan.plan_id}: {plan.summary}")

    while pending:
        # ▶ 找出依赖已全部完成的步骤
        ready = [
            s for s in pending.values()
            if all(dep in results and results[dep].status in ("done", "partial") for dep in s.depends_on)
        ]

        if not ready:
            # 有步骤但无法执行 → 依赖循环或全部失败
            failed_deps = []
            for s in pending.values():
                for dep in s.depends_on:
                    if dep in results and results[dep].status == "failed":
                        failed_deps.append((s.id, dep))
            if failed_deps:
                for sid, did in failed_deps:
                    print(f"[Orchestrator] {sid} 跳过（依赖 {did} 失败）")
                    pending[sid].status = "failed"
                    pending[sid].result = f"上游步骤 {did} 执行失败"
                    del pending[sid]
                continue
            else:
                # 无法前进
                print(f"[Orchestrator] 死锁：剩余 {list(pending.keys())}")
                break

        # ▶ 并发调度所有 ready 步骤
        step_futures = {}
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as executor:
            for step in ready:
                del pending[step.id]
                step.status = "running"
                step.started_at = time.time()

                _push_progress(plan.conversation_id, step)

                # ReAct 循环：LLM + 工具调用
                future = executor.submit(_execute_step_with_tools, step, results)
                step_futures[future] = step

            # ▶ 等待并发步骤完成
            for future in as_completed(step_futures, timeout=STEP_TIMEOUT + 10):
                step = step_futures[future]
                try:
                    status, result_text = future.result(timeout=10)
                except Exception as e:
                    status, result_text = "failed", str(e)

                step.status = "done" if status == "completed" else (
                    "partial" if status == "partial" else "failed"
                )
                step.result = result_text
                step.duration = time.time() - (step.started_at or time.time())
                results[step.id] = step
                _push_progress(plan.conversation_id, step)

    # ── 聚合结果 ──
    done_count = sum(1 for s in results.values() if s.status == "done")
    plan.status = "done" if done_count == len(results) else (
        "partial_fail" if done_count > 0 else "failed"
    )

    return {
        "plan_id": plan.plan_id,
        "summary": plan.summary,
        "status": plan.status,
        "steps": [
            {"id": s.id, "agent": s.agent, "task": s.task,
             "status": s.status, "duration": round(s.duration, 1),
             "result": s.result[:1500] if s.result else None}
            for s in plan.steps
        ]
    }


# ═══════════════════════════════════════════════════
# Phase 3: Aggregator — 结果汇总
# ═══════════════════════════════════════════════════

def aggregate_results(execution_result: dict) -> str:
    """将多步结果聚合成一个自然语言回复"""
    status = execution_result["status"]
    summary = execution_result["summary"]

    if status == "done":
        lines = [f"✅ **{summary}** — 全部完成\n"]
    elif status == "partial_fail":
        lines = [f"⚠️ **{summary}** — 部分完成\n"]
    else:
        lines = [f"❌ **{summary}** — 执行失败\n"]

    for step in execution_result["steps"]:
        icon = {"done": "✅", "failed": "❌", "partial": "⚠️", "running": "🔄"}.get(step["status"], "⏳")
        lines.append(
            f"{icon} **{step['agent']}** ({step['duration']}s): {step['task'][:80]}"
        )
        if step["result"]:
            result_text = step["result"]
            if len(result_text) > 1500:
                result_text = result_text[:1500] + "\n...(结果过长已截断)"
            lines.append(f"```\n{result_text}\n```")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════
# 对外入口
# ═══════════════════════════════════════════════════

def _create_orchestration_tasks(plan: ExecutionPlan) -> list[int]:
    """将计划的每个步骤创建为 agent-platform Task 记录，返回 task_id 列表"""
    task_ids = []
    
    # 先获取 agent id 映射
    agent_ids = {}
    try:
        resp = requests.get(f"{AGENT_PLATFORM}/api/agents/",
                           params={"page_size": 50}, timeout=5)
        for a in resp.json().get("results", []):
            agent_ids[a["name"]] = a["id"]
    except Exception:
        pass

    for step in plan.steps:
        agent_id = agent_ids.get(step.agent)
        if not agent_id:
            print(f"[Orchestrator] 跳过 {step.id}: Agent '{step.agent}' 未找到")
            continue

        try:
            resp = requests.post(f"{AGENT_PLATFORM}/api/tasks/", json={
                "title": f"[{plan.plan_id}] {step.task[:50]}",
                "description": f"任务：{step.task}\n\nAgent: {step.agent}\n计划: {plan.summary}\n步骤ID: {step.id}\n对话ID: {plan.conversation_id}\n依赖: {step.depends_on}",
                "agent": agent_id,
                "status": "pending",
                "priority": "high",
                "source": "agent",
                "contract": {
                    "plan_id": plan.plan_id,
                    "step_id": step.id,
                    "conversation_id": plan.conversation_id,
                    "depends_on": step.depends_on,
                    "output_key": step.output_key,
                    "orchestrator": True,
                }
            }, timeout=10)
            task_data = resp.json()
            task_ids.append(task_data.get("id"))
            print(f"[Orchestrator] Task#{task_data.get('id')} ← {step.agent}: {step.task[:50]}")
        except Exception as e:
            print(f"[Orchestrator] 创建 Task 失败: {e}")

    return task_ids


def _check_and_aggregate(conversation_id: int, plan_id: str) -> Optional[str]:
    """检查指定计划的所有 Task 是否完成，如果完成则聚合并返回结果"""
    try:
        resp = requests.get(f"{AGENT_PLATFORM}/api/tasks/",
                           params={"page_size": 50, "ordering": "-created_at"}, timeout=5)
        tasks = resp.json().get("results", [])
        
        # 筛选属于本计划的 Task
        plan_tasks = [
            t for t in tasks
            if isinstance(t.get("contract"), dict)
            and t["contract"].get("plan_id") == plan_id
        ]
        
        if not plan_tasks:
            return None  # 还没有 Task 被创建
        
        # 检查是否全部完成
        done_count = sum(1 for t in plan_tasks if t["status"] in ("completed", "failed", "cancelled"))
        if done_count < len(plan_tasks):
            return None  # 还有未完成的
        
        # 全部完成 → 聚合
        steps = []
        for t in plan_tasks:
            result = t.get("result", {})
            if isinstance(result, dict):
                result_text = result.get("output", str(result))
            else:
                result_text = str(result) if result else "(无输出)"
            
            steps.append({
                "agent": t.get("agent_name", "?"),
                "task": t.get("title", "")[:80],
                "status": "done" if t["status"] == "completed" else "failed",
                "duration": 0,
                "result": result_text[:1500],
            })
        
        done_count = sum(1 for s in steps if s["status"] == "done")
        status = "done" if done_count == len(steps) else "partial_fail"
        return aggregate_results({
            "status": status,
            "summary": f"计划 {plan_id}",
            "steps": steps,
        })
    except Exception as e:
        print(f"[Orchestrator] 聚合检查失败: {e}")
        return None


def orchestrate(user_message: str, conversation_id: int) -> str:
    """异步调度入口：生成计划 → 写 Task → 返回进度消息"""
    # 1. 生成计划
    plan = generate_plan(user_message, conversation_id)
    if not plan or not plan.steps:
        return "⚠️ 无法解析您的指令，请更具体地描述需要做什么。"

    print(f"[Orchestrator] 计划生成: {plan.summary} ({len(plan.steps)} 步)")

    # 2. 推送计划概览
    step_list = "\n".join(
        f"  {i+1}. **{s.agent}** → {s.task[:60]}"
        + (f" (依赖: {', '.join(s.depends_on)})\n    → Task#{s.task_id}" if s.task_id else f" (依赖: {', '.join(s.depends_on)})")
        for i, s in enumerate(plan.steps)
    )
    try:
        requests.post(f"{AGENT_PLATFORM}/api/messages/", json={
            "conversation": conversation_id,
            "role": "system",
            "content": f"📋 **执行计划**：{plan.summary}\n{step_list}",
            "source": "web",
        }, timeout=5)
    except Exception:
        pass

    # 3. 创建 Task 记录（由 Hermes cron job 执行）
    task_ids = _create_orchestration_tasks(plan)

    if not task_ids:
        return "⚠️ 无法分配任务给 Agent，请检查 Agent 是否在线。"

    return (
        f"📋 **{plan.summary}**\n\n"
        f"已派发 {len(task_ids)} 个子任务到 Agent 执行队列：\n"
        + "\n".join(f"  • Task#{tid}" for tid in task_ids)
        + "\n\n⏳ Hermes 子 Agent 正在处理中，完成后我会汇总结果。"
    )
