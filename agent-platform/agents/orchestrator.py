#!/usr/bin/env python3
"""
Orchestrator v2 — 高效多 Agent 调度中台

设计原则（2026-06-22 重写）：
  - LLM 只调一次 → 生成完整可执行计划
  - Python 本地执行所有步骤（不调 LLM）
  - 步骤失败 → 先查 pitfall_memory → 没有再调 LLM
  - 自动学习：每次 LLM 修复成功 → 写入 pitfall_memory

Token 消耗模型：
  BEFORE: 1×PlanGen + N×ReAct(avg 5次LLM) + cron(每2分钟5000token空跑)
  AFTER:  1×PlanGen + 0×执行 + 仅异常时1×LLM
"""

import json
import os
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Optional

import requests

from .pitfall_memory import search_pitfall, apply_fix, record_pitfall

# ─── 配置 ──────────────────────────────────────────
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
AGENT_PLATFORM = "http://localhost:8001"
MAX_CONCURRENT = 3
STEP_TIMEOUT = 120  # 单步超时（秒）
MAX_RECOVERY_LLM_CALLS = 2  # 最多调几次 LLM 修复

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
    agent: str          # Agent 名称（用于角色画像）
    action: str         # terminal | read_file | write_file | search | reason | api
    command: str        # 具体的命令/内容/问题
    depends_on: list = field(default_factory=list)
    output_key: str = ""
    expect: str = ""    # 预期结果（用于校验）
    on_failure: str = "retry"  # retry | skip | ask_user
    note: str = ""      # 步骤说明
    status: str = "pending"
    result: Optional[str] = None
    duration: float = 0.0
    retry_count: int = 0
    llm_calls: int = 0  # 这个步骤调了几次 LLM


@dataclass
class ExecutionPlan:
    plan_id: str
    summary: str
    steps: list  # list[PlanStep]
    conversation_id: int = 0
    status: str = "pending"


# ═══════════════════════════════════════════════════
# Phase 1: PlanGen — LLM 自由探索 + 输出计划（仿 Hermes agent loop）
# ═══════════════════════════════════════════════════

HERMES_STYLE_PROMPT = """你是小温，范先生的多 Agent 豆角云枢。你有终端、代码搜索、文件读取等工具。

## 工作方式
用户给你任务后，直接用工具开始工作。边探索边分析，结束后用中文汇报结果。

## 可用工具
- terminal: 执行 shell 命令（工作目录 /home/jiangli）
- read_file: 读取文件内容（需要绝对路径）  
- search: 搜索项目文件/代码内容

## 规则
1. 收到任务立即动手，不要先说"我来了解一下"
2. 能并行的操作同时调多个工具
3. 只能操作 /home/jiangli/ 下的文件
4. 探索充分后直接输出分析结论，不要再调工具
5. 中文回复，结构清晰，用 Markdown 格式"""


def _call_llm_api(messages: list, max_tokens: int = 2000, temperature: float = 0.3) -> Optional[dict]:
    """单次 LLM 调用，返回完整响应（含 tool_calls）"""
    try:
        resp = requests.post(
            DEEPSEEK_URL,
            headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"},
            json={"model": "deepseek-v4-pro", "messages": messages,
                  "temperature": temperature, "max_tokens": max_tokens,
                  "tools": [
                      {"type": "function", "function": {
                          "name": "terminal", "description": "执行 shell 命令",
                          "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}
                      }},
                      {"type": "function", "function": {
                          "name": "read_file", "description": "读取文件",
                          "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
                      }},
                      {"type": "function", "function": {
                          "name": "search", "description": "搜索文件/内容",
                          "parameters": {"type": "object", "properties": {"pattern": {"type": "string"}}, "required": ["pattern"]}
                      }},
                  ]},
            timeout=60,
        )
        data = resp.json()
        if "error" in data:
            print(f"[Orchestrator] API error: {data['error']}")
            return None
        choice = data["choices"][0]
        msg = choice["message"]
        return {
            "content": msg.get("content", ""),
            "tool_calls": msg.get("tool_calls", [])
        }
    except Exception as e:
        print(f"[Orchestrator] LLM call failed: {e}")
        return None


def _call_llm(messages: list, max_tokens: int = 2000, temperature: float = 0.3) -> Optional[str]:
    """简单文本 LLM 调用（无工具），返回文本内容"""
    resp = _call_llm_api(messages, max_tokens, temperature)
    if resp:
        return resp.get("content", "")
    return None


def _execute_tool_call(tool_name: str, args: dict) -> str:
    """执行单个工具调用，返回结果字符串"""
    import subprocess as sp
    if tool_name == "terminal":
        cmd = args.get("command", "")
        if any(d in cmd for d in ["rm -rf", "sudo", "mkfs"]):
            return "[安全拦截]"
        try:
            r = sp.run(cmd, shell=True, capture_output=True, text=True, timeout=30,
                       cwd="/home/jiangli", env={**os.environ, "HOME": "/home/jiangli"})
            return (r.stdout + r.stderr)[:3000] or "(无输出)"
        except sp.TimeoutExpired:
            return "[超时]"
        except Exception as e:
            return f"[错误] {e}"
    elif tool_name == "read_file":
        path = args.get("path", "")
        if not path.startswith("/"):
            return "[错误] 需要绝对路径"
        try:
            with open(path) as f:
                lines = f.readlines()[:100]
            return "".join(lines)
        except FileNotFoundError:
            return f"[不存在] {path}"
        except Exception as e:
            return f"[错误] {e}"
    elif tool_name == "search":
        pattern = args.get("pattern", "")
        try:
            r = sp.run(["grep", "-rn", "--include=*.py", "--include=*.js", "--include=*.jsx",
                        "--include=*.md", "-l", pattern, "/home/jiangli/projects"],
                       capture_output=True, text=True, timeout=10)
            return r.stdout[:3000] or "(无匹配)"
        except Exception as e:
            return f"[错误] {e}"
    return f"[未知工具] {tool_name}"


def _parse_plan_from_text(text: str, valid_agent_names: set) -> Optional[ExecutionPlan]:
    """从 LLM 回复中提取 [PLAN]...[/PLAN] 并解析"""
    m = re.search(r'\[PLAN\](.*?)\[/PLAN\]', text, re.DOTALL | re.IGNORECASE)
    if not m:
        return None
    
    plan_text = m.group(1).strip()
    # 解析 YAML-like 格式
    summary = ""
    steps = []
    current_step = None
    
    for line in plan_text.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        if line.startswith('summary:') or line.startswith('summary：'):
            summary = line.split(':', 1)[1].strip().lstrip('：').strip()
        elif line.startswith('- id:') or line.startswith('- id：'):
            if current_step:
                steps.append(current_step)
            step_id = line.split(':', 1)[1].strip().lstrip('：').strip()
            current_step = {'id': step_id}
        elif current_step is not None:
            for key in ['action', 'command', 'depends_on', 'note']:
                if line.startswith(f'{key}:') or line.startswith(f'{key}：'):
                    val = line.split(':', 1)[1].strip().lstrip('：').strip()
                    if key == 'depends_on':
                        val = [x.strip() for x in val.strip('[]').split(',') if x.strip()]
                    current_step[key] = val
                    break
    
    if current_step:
        steps.append(current_step)
    
    if not steps:
        return None
    
    plan_steps = []
    for i, s in enumerate(steps):
        action = s.get('action', 'terminal')
        if action not in ('terminal', 'read_file', 'search', 'reason', 'write_file'):
            action = 'terminal'
        
        plan_steps.append(PlanStep(
            id=s.get('id', f'step_{i+1}'),
            agent='小温',
            action=action,
            command=s.get('command', ''),
            depends_on=s.get('depends_on', []),
            output_key=s.get('id', f'step_{i+1}') + '_result',
            note=s.get('note', ''),
        ))
    
    return ExecutionPlan(
        plan_id=f"plan_{int(time.time())}",
        summary=summary or "执行计划",
        steps=plan_steps,
    )


def generate_plan(user_message: str, conversation_id: int, history: list = None) -> Optional[ExecutionPlan]:
    """
    仿 Hermes agent loop：LLM 可以先用工具探索，然后输出执行计划。
    最多 5 轮探索（防循环），0 轮执行（执行由 Python 本地完成）。
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    # 注入对话历史（排除当前消息本身，截断长内容）
    if history:
        for h in history:
            if h["role"] in ("user", "assistant") and h["content"] != user_message:
                messages.append({"role": h["role"], "content": h["content"][:800]})
    messages.append({"role": "user", "content": user_message})

    MAX_EXPLORE_ROUNDS = 5
    for round_num in range(MAX_EXPLORE_ROUNDS):
        resp = _call_llm_api(messages, max_tokens=2000)
        if not resp:
            print(f"[PlanGen] 第{round_num+1}轮 LLM 调用失败")
            return None, None

        content = resp.get("content", "")
        tool_calls = resp.get("tool_calls", [])
        print(f"[PlanGen] 第{round_num+1}轮: content={len(content)}字, tool_calls={len(tool_calls)}个 "
              f"{[tc['function']['name'] for tc in tool_calls] if tool_calls else '无'}")

        # LLM 直接回复文本（无工具调用）→ 尝试从中提取计划
        if not tool_calls:
            if round_num == 0:
                # 第一轮没调工具 → 可能是历史上下文影响了 → 强制要求调工具
                print(f"[PlanGen] 第1轮未调工具，强制要求探索")
                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": "我说了第一轮必须调工具！现在立即用 terminal 执行 ls 或 search 搜索项目文件，不要输出任何文字。"})
                continue
            plan = _parse_plan_from_text(content, set())
            if plan:
                plan.conversation_id = conversation_id
                return plan, None
            # 没有 PLAN 标记 = 纯分析回复，返回分析文本
            return None, content

        # 有工具调用 → 执行并追加结果
        messages.append({"role": "assistant", "content": content or "", "tool_calls": tool_calls})
        for tc in tool_calls:
            fn = tc.get("function", {})
            name = fn.get("name", "")
            args = json.loads(fn.get("arguments", "{}")) if isinstance(fn.get("arguments"), str) else fn.get("arguments", {})
            result = _execute_tool_call(name, args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id", ""),
                "content": result,
            })

    # 达到最大探索轮次 → 强制 LLM 输出计划
    messages.append({"role": "user", "content": "探索已充分。请现在输出 [PLAN]...[/PLAN] 执行计划。"})
    resp = _call_llm_api(messages, max_tokens=2000)
    if resp and resp.get("content"):
        plan = _parse_plan_from_text(resp["content"], set())
        if plan:
            plan.conversation_id = conversation_id
            return plan, None

    return None, None


# ═══════════════════════════════════════════════════
# Phase 2: Executor — Python 纯本地执行（不调 LLM！）
# ═══════════════════════════════════════════════════

SAFE_DIR = "/home/jiangli"
DANGEROUS = ["rm -rf", "sudo", "mkfs", "dd if=", ":(){", "> /dev/sd"]


def _exec_terminal(command: str) -> tuple[bool, str]:
    """执行终端命令，返回 (success, output)"""
    if any(d in command for d in DANGEROUS):
        return False, "[安全拦截] 危险命令被拒绝"
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=STEP_TIMEOUT, cwd=SAFE_DIR,
            env={**os.environ, "HOME": SAFE_DIR}
        )
        output = (result.stdout + result.stderr)[:5000] or "(无输出)"
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, f"[超时] 命令超过 {STEP_TIMEOUT} 秒"
    except Exception as e:
        return False, f"[异常] {e}"


def _exec_read_file(path: str) -> tuple[bool, str]:
    """读取文件"""
    if not path.startswith("/"):
        return False, "[错误] 必须使用绝对路径"
    try:
        with open(path) as f:
            lines = f.readlines()[:200]
        return True, "".join(f"{i+1}|{l}" for i, l in enumerate(lines))
    except FileNotFoundError:
        return False, f"[错误] 文件不存在: {path}"
    except PermissionError:
        return False, f"[错误] 无权限: {path}"
    except Exception as e:
        return False, f"[错误] {e}"


def _exec_write_file(path: str, content: str) -> tuple[bool, str]:
    """写入文件（安全限制）"""
    if not path.startswith(SAFE_DIR + "/"):
        return False, f"[安全拦截] 只能写入 {SAFE_DIR}/ 下的文件"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return True, f"[OK] 已写入 {path} ({len(content)} 字符)"
    except Exception as e:
        return False, f"[错误] {e}"


def _exec_search(pattern: str, target: str = "content") -> tuple[bool, str]:
    """搜索文件或内容"""
    try:
        if target == "files" or pattern.startswith("glob:"):
            p = pattern.replace("glob:", "").strip()
            result = subprocess.run(
                ["find", SAFE_DIR, "-maxdepth", "5", "-name", p,
                 "-not", "-path", "*/node_modules/*", "-not", "-path", "*/.git/*",
                 "-not", "-path", "*/venv/*", "-not", "-path", "*/__pycache__/*"],
                capture_output=True, text=True, timeout=15
            )
            return True, result.stdout[:3000] or "(无匹配)"
        else:
            result = subprocess.run(
                ["grep", "-rn", "--include=*.py", "--include=*.js", "--include=*.jsx",
                 "--include=*.md", "--include=*.json", "--include=*.html",
                 "-l", pattern, f"{SAFE_DIR}/projects"],
                capture_output=True, text=True, timeout=15
            )
            return True, result.stdout[:3000] or "(无匹配)"
    except Exception as e:
        return False, f"[错误] {e}"


def _exec_reason(prompt: str, results: dict) -> tuple[bool, str]:
    """
    需要推理的步骤 — 调一次 LLM（不是 ReAct 循环！）
    仅用于 terminal/search 无法处理的复杂分析
    """
    context = "\n".join(
        f"[{k}]: {v.result[:1000] if v.result else '(空)'}"
        for k, v in results.items()
    )
    messages = [
        {"role": "system", "content": "你是技术分析助手。基于已有数据给出分析结论。用中文，简洁直接。200字以内。"},
        {"role": "user", "content": f"已有数据：\n{context}\n\n分析任务：{prompt}"}
    ]
    content = _call_llm(messages, max_tokens=500)
    if content:
        return True, content
    return False, "[LLM调用失败]"


def _execute_step(step: PlanStep, results: dict) -> tuple[str, str]:
    """
    执行单个步骤 — 纯机械执行，不调 LLM（reason 除外）
    返回 (status: done|failed|skipped, result_text)
    """
    t0 = time.time()

    # 注入上游结果
    command = step.command
    for dep_id in step.depends_on:
        if dep_id in results and results[dep_id].result:
            placeholder = f"${{{dep_id}}}"
            command = command.replace(placeholder, results[dep_id].result[:2000])

    # 按 action 分发
    if step.action == "terminal":
        ok, output = _exec_terminal(command)
    elif step.action == "read_file":
        ok, output = _exec_read_file(command)
    elif step.action == "write_file":
        parts = command.split("\n", 1)
        path = parts[0].strip()
        content = parts[1] if len(parts) > 1 else ""
        ok, output = _exec_write_file(path, content)
    elif step.action == "search":
        ok, output = _exec_search(command)
    elif step.action == "reason":
        ok, output = _exec_reason(command, results)
        step.llm_calls += 1  # reason 类型算一次 LLM
    else:
        ok, output = False, f"[错误] 未知 action: {step.action}"

    step.duration = time.time() - t0

    if ok:
        # 校验预期
        if step.expect:
            expect_lower = step.expect.lower()
            output_lower = output.lower()
            if "number" in expect_lower or "数字" in expect_lower:
                if not re.search(r'\d+', output):
                    return "failed", f"[校验失败] 预期包含数字，实际: {output[:200]}"
            elif "error" not in expect_lower and "失败" not in expect_lower:
                if "error" in output_lower or "错误" in output_lower or "失败" in output_lower:
                    return "failed", output[:2000]
        return "done", output[:5000]

    # ── 失败 → 尝试修复 ──
    return _recover_step(step, output, results)


def _recover_step(step: PlanStep, error: str, results: dict) -> tuple[str, str]:
    """
    步骤失败后的修复流程：
    1. 查 pitfall_memory → 命中则自动修复
    2. 未命中 → 调一次 LLM 获取修复方案
    3. 修复成功 → 写入 pitfall_memory
    """
    step.retry_count += 1

    # 1. 查坑位记忆
    pitfall = search_pitfall(error, context=f"action={step.action}, command={step.command[:100]}")
    if pitfall:
        print(f"[Orchestrator] 命中坑位 {pitfall['id']}: {pitfall.get('pattern', '?')}")
        ok, result = apply_fix(pitfall, {"step_id": step.id, "command": step.command})
        if ok:
            return "done", result
        # 坑位修复也失败了，继续往下走

    # 2. 如果配置了 skip
    if step.on_failure == "skip":
        return "skipped", f"[跳过] {error[:500]}"

    # 3. 如果重试次数耗尽
    if step.retry_count > MAX_RECOVERY_LLM_CALLS:
        return "failed", f"[重试耗尽] {error[:500]}"

    # 4. 调 LLM 获取修复方案（仅一次！）
    step.llm_calls += 1
    context = "\n".join(
        f"[已完成步骤 {k}]: {v.result[:500] if v.result else '(空)'}"
        for k, v in results.items()
    )
    recovery_prompt = f"""执行以下步骤时出错：

步骤: {step.agent} → {step.action}: {step.command[:200]}
错误: {error[:1000]}
已有上下文: {context[:1000]}

请给出修复方案。输出 JSON:
{{"fix_type": "retry_command|skip|replace_command|manual", "fix": "具体修复内容"}}

- retry_command: 给出修正后的完整命令
- skip: 跳过此步骤（非关键错误）
- replace_command: 用新命令替换
- manual: 需要人工介入

只输出 JSON，不要解释。"""

    messages = [
        {"role": "system", "content": "你是故障修复专家。根据错误信息给出精确修复方案。"},
        {"role": "user", "content": recovery_prompt}
    ]
    content = _call_llm(messages, max_tokens=500)
    if not content:
        return "failed", f"[LLM修复失败] {error[:500]}"

    try:
        start = content.find("{")
        end = content.rfind("}") + 1
        fix_data = json.loads(content[start:end])
    except (json.JSONDecodeError, ValueError):
        fix_data = {"fix_type": "skip", "fix": "LLM回复无法解析"}

    fix_type = fix_data.get("fix_type", "skip")
    fix = fix_data.get("fix", "")

    # 5. 记录到坑位记忆
    record_pitfall(
        pattern=error[:200],
        context=f"action={step.action}",
        fix_type=fix_type,
        fix_detail=fix
    )

    # 6. 应用修复
    if fix_type == "retry_command" and fix:
        ok, output = _exec_terminal(fix)
        if ok:
            return "done", f"[LLM修复成功] {output[:4000]}"
        return "failed", f"[LLM修复命令也失败了] {output[:500]}"
    elif fix_type == "replace_command" and fix:
        step.command = fix
        ok, output = _exec_terminal(fix)
        if ok:
            return "done", f"[LLM修复成功] {output[:4000]}"
    elif fix_type == "skip":
        return "skipped", f"[LLM建议跳过] {fix[:300]}"
    elif fix_type == "manual":
        return "failed", f"[需人工介入] {fix[:500]}"

    return "failed", f"[修复失败] {error[:500]}"


# ═══════════════════════════════════════════════════
# Phase 3: 计划执行引擎（依赖解析 + 并行调度）
# ═══════════════════════════════════════════════════

def execute_plan(plan: ExecutionPlan) -> dict:
    """
    执行计划：
    1. 拓扑排序
    2. 并行执行无依赖步骤
    3. 失败时自动修复（pitfall → LLM）
    """
    results = {}  # step_id → PlanStep (with result)
    pending = {s.id: s for s in plan.steps}
    plan.status = "running"

    total_llm_before = sum(s.llm_calls for s in plan.steps)

    print(f"[Orchestrator] 开始执行 {plan.plan_id}: {plan.summary} ({len(plan.steps)} 步)")

    while pending:
        # 找出依赖已完成的步骤
        ready = [
            s for s in pending.values()
            if all(dep in results and results[dep].status in ("done", "skipped")
                   for dep in s.depends_on)
        ]

        if not ready:
            # 检查是否有因上游失败而无法执行的
            stuck = False
            for s in list(pending.values()):
                for dep in s.depends_on:
                    if dep in results and results[dep].status == "failed":
                        s.status = "failed"
                        s.result = f"上游步骤 {dep} 执行失败"
                        del pending[s.id]
                        stuck = True
            if stuck:
                continue
            # 死锁
            print(f"[Orchestrator] 死锁：剩余 {list(pending.keys())}")
            for s in pending.values():
                s.status = "failed"
                s.result = "依赖步骤未完成"
            break

        # 并行执行 ready 步骤
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as executor:
            futures = {}
            for step in ready:
                del pending[step.id]
                step.status = "running"
                future = executor.submit(_execute_step, step, results)
                futures[future] = step

            for future in as_completed(futures, timeout=STEP_TIMEOUT + 30):
                step = futures[future]
                try:
                    status, result_text = future.result(timeout=10)
                    step.status = status
                    step.result = result_text
                    results[step.id] = step
                except Exception as e:
                    step.status = "failed"
                    step.result = str(e)
                    results[step.id] = step

                print(f"[Orchestrator] {step.id} → {step.status} "
                      f"({step.duration:.1f}s, LLM×{step.llm_calls})")

    # 统计
    total_llm_after = sum(s.llm_calls for s in plan.steps)
    done = sum(1 for s in results.values() if s.status == "done")
    failed = sum(1 for s in results.values() if s.status == "failed")

    plan.status = "done" if failed == 0 else ("partial_fail" if done > 0 else "failed")

    print(f"[Orchestrator] {plan.plan_id} 完成: {plan.status} "
          f"(done={done}, failed={failed}, LLM_calls={total_llm_after - total_llm_before})")

    return {
        "plan_id": plan.plan_id,
        "summary": plan.summary,
        "status": plan.status,
        "steps": [
            {"id": s.id, "agent": s.agent, "action": s.action,
             "command": s.command[:100], "status": s.status,
             "duration": round(s.duration, 1), "llm_calls": s.llm_calls,
             "result": s.result[:2000] if s.result else None}
            for s in plan.steps
        ],
        "stats": {
            "done": done, "failed": failed, "total": len(plan.steps),
            "llm_calls_plan": 1,
            "llm_calls_recovery": total_llm_after,
        }
    }


# ═══════════════════════════════════════════════════
# 对外入口
# ═══════════════════════════════════════════════════

def _describe_round(tool_calls: list, round_num: int) -> str:
    """把一轮的工具调用描述为精简中文节点（只描述操作类型）"""
    names = [tc.get("function", {}).get("name", "?") for tc in tool_calls]
    read_count = names.count("read_file")
    terminal_count = names.count("terminal")
    search_count = names.count("search")
    
    if read_count >= len(names) * 0.7:
        return f"📂 读取 {read_count} 个文件"
    if terminal_count >= len(names) * 0.7:
        return f"💻 执行 {terminal_count} 个命令"
    if search_count:
        return "🔍 搜索代码"
    # 混合
    parts = []
    if read_count: parts.append(f"读取 {read_count} 个文件")
    if terminal_count: parts.append(f"{terminal_count} 个命令")
    if search_count: parts.append("搜索")
    return "⚙️ " + "、".join(parts)


def _push_system_msg(conversation_id: int, content: str, metadata: dict = None):
    """推送一条系统消息到对话（中间节点）"""
    try:
        payload = {"conversation": conversation_id, "role": "system", "content": content, "source": "web"}
        if metadata:
            payload["metadata"] = json.dumps(metadata)
        requests.post(f"{AGENT_PLATFORM}/api/messages/", json=payload, timeout=5)
    except Exception:
        pass  # 推送失败不影响主流程


def _set_orch_state(conversation_id: int, state: str):
    """写入编排器状态到 Redis (running/paused/stopped/idle)"""
    try:
        import redis as _rds
        r = _rds.Redis.from_url("redis://localhost:6379/0")
        if state == 'idle':
            r.delete(f"orch:state:{conversation_id}")
        else:
            r.setex(f"orch:state:{conversation_id}", 600, state)
    except Exception:
        pass


def orchestrate(user_message: str, conversation_id: int, history: list = None) -> str:
    """
    Hermes 风格：LLM 自由使用工具完成任务，不需要中间计划层。
    最多 10 轮探索，防止循环——和 Hermes agent loop 一样。
    每轮推送系统消息到对话作为实时进度节点。
    """
    import json as _json
    
    messages = [{"role": "system", "content": HERMES_STYLE_PROMPT}]
    if history:
        for h in history:
            if h["role"] in ("user", "assistant") and h["content"] != user_message:
                messages.append({"role": h["role"], "content": h["content"][:800]})
    messages.append({"role": "user", "content": user_message})

    # 推送开始节点
    _push_system_msg(conversation_id, "🔍 开始分析任务...", {"orch": "start"})
    _set_orch_state(conversation_id, "running")

    MAX_ROUNDS = 10
    node_count = 0
    for round_num in range(MAX_ROUNDS):
        # 检查停止/暂停信号
        try:
            import redis as _redis
            _r = _redis.Redis.from_url("redis://localhost:6379/0")
            if _r.get(f"orch:stop:{conversation_id}"):
                _r.delete(f"orch:stop:{conversation_id}")
                _r.delete(f"orch:pause:{conversation_id}")
                _set_orch_state(conversation_id, "stopped")
                _push_system_msg(conversation_id, "⏹️ 用户停止，任务已中断", {"orch": "stopped"})
                return "⏹️ 任务已被用户手动停止"
            if _r.get(f"orch:pause:{conversation_id}"):
                _r.delete(f"orch:pause:{conversation_id}")
                _set_orch_state(conversation_id, "paused")
                _push_system_msg(conversation_id, "⏸️ 用户暂停，任务已中断", {"orch": "paused"})
                return "⏸️ 任务已被用户手动暂停"
        except Exception:
            pass
        
        resp = _call_llm_api(messages, max_tokens=2000)
        if not resp:
            _set_orch_state(conversation_id, "idle")
            _push_system_msg(conversation_id, "⚠️ LLM 调用失败", {"orch": "error"})
            return "⚠️ LLM 调用失败，请重试"

        content = resp.get("content", "")
        tool_calls = resp.get("tool_calls", [])
        tool_names = [tc.get("function", {}).get("name", "?") for tc in tool_calls]
        print(f"[Orchestrator] 第{round_num+1}轮: text={len(content)}字, tools={tool_names}")

        if not tool_calls:
            # 不再调工具 → LLM 认为任务完成
            _set_orch_state(conversation_id, "idle")
            _push_system_msg(conversation_id, "✅ 分析完成，生成报告...", {"orch": "done"})
            return content or "已完成探索，但没有输出分析内容"

        # 推送中间节点——每轮一个系统消息，精简描述
        node_count += 1
        node_desc = _describe_round(tool_calls, round_num + 1)
        _push_system_msg(conversation_id, node_desc, {"orch": "node", "round": round_num + 1, "tools": tool_names})

        # 执行工具调用
        assistant_msg = {"role": "assistant", "content": content or ""}
        if tool_calls:
            assistant_msg["tool_calls"] = tool_calls
        messages.append(assistant_msg)

        for tc in tool_calls:
            fn = tc.get("function", {})
            name = fn.get("name", "")
            try:
                args = _json.loads(fn.get("arguments", "{}")) if isinstance(fn.get("arguments"), str) else fn.get("arguments", {})
            except Exception:
                args = {}
            result = _execute_tool_call(name, args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id", ""),
                "content": result,
            })

    # 达到最大轮次 → 强制收尾
    print("[Orchestrator] 达到最大探索轮次，强制收尾")
    _push_system_msg(conversation_id, "📊 探索充分，汇总分析...", {"orch": "summarizing"})
    # 裁剪上下文：只保留 system prompt + 最近 3 轮工具交互，避免超 token
    trimmed = [messages[0]]  # system prompt
    # 从后往前找最近 3 轮 assistant+tool 消息
    recent = []
    for m in reversed(messages[1:]):
        if m["role"] in ("assistant", "tool"):
            recent.insert(0, m)
        if sum(1 for m in recent if m["role"] == "assistant") >= 3:
            break
    trimmed.extend(recent)
    trimmed.append({"role": "user", "content": "探索轮次已用尽。请根据以上探索结果，直接输出你的分析和建议（中文，Markdown 格式），不要调用任何工具。"})
    final = _call_llm(trimmed, max_tokens=2000)
    _set_orch_state(conversation_id, "idle")
    return final or "探索完成但 LLM 无法生成分析"


# ═══════════════════════════════════════════════════
# 守护进程入口（供 orchestrator_daemon.py 调用）
# ═══════════════════════════════════════════════════

def poll_and_execute():
    """
    检查 agent-platform 是否有待执行的编排任务。
    如果有：执行并推送结果到对话。
    返回 (executed_count, error)
    """
    try:
        resp = requests.get(f"{AGENT_PLATFORM}/api/tasks/",
                           params={"status": "pending", "page_size": 10, "ordering": "-created_at"},
                           timeout=5)
        tasks = resp.json().get("results", [])
    except Exception as e:
        return 0, str(e)

    # 筛选有 orchestrator 标记的
    orch_tasks = [
        t for t in tasks
        if isinstance(t.get("contract"), dict) and t.get("contract", {}).get("orchestrator")
    ]

    if not orch_tasks:
        return 0, None

    # 按 conversation_id 分组，同一对话的批量处理
    by_conv = {}
    for t in orch_tasks:
        cid = t.get("contract", {}).get("conversation_id", 0)
        by_conv.setdefault(cid, []).append(t)

    executed = 0
    for cid, task_group in by_conv.items():
        # 合成用户消息（从第一个 task 的描述中提取）
        desc = task_group[0].get("description", "")
        user_msg = desc or task_group[0].get("title", "执行任务")

        # 编排执行
        result_text = orchestrate(user_msg, cid)

        # 推送结果
        try:
            requests.post(f"{AGENT_PLATFORM}/api/messages/", json={
                "conversation": cid,
                "role": "system",
                "content": result_text,
                "source": "web",
            }, timeout=5)
        except Exception:
            pass

        # 标记所有 task 为 completed
        for t in task_group:
            try:
                requests.patch(f"{AGENT_PLATFORM}/api/tasks/{t['id']}/",
                              json={"status": "completed", "result": {"output": result_text[:500]}},
                              timeout=5)
            except Exception:
                pass

        executed += len(task_group)

    return executed, None
