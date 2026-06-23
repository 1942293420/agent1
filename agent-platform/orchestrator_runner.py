#!/usr/bin/env python3
"""
Task 编排执行器 — 单次调用内完成整个依赖链（不等待下一轮）

流程：
1. GET /api/tasks/?page_size=50 → 筛选 contract.orchestrator=true 的 Task
2. 按 plan_id 分组
3. 对每个 plan，循环直到无可执行步骤：
   a. 找 status=pending 且 depends_on 全部 completed 的 Task（同 plan）
   b. 无则退出
   c. 每次最多 2 个，逐个标记 in_progress → 输出给 Hermes 执行 → 标记 completed/failed
   d. 立即回到 a，刚完成的可解锁新步骤
4. 不聚合不推送，只改 Task 状态
"""

import requests
import json
import sys
import time
from typing import Optional
from collections import defaultdict

API_BASE = "http://localhost:8001/api"


def fetch_tasks() -> list[dict]:
    """拉取所有 orchestrator task"""
    resp = requests.get(f"{API_BASE}/tasks/", params={"page_size": 200}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    all_tasks = data.get("results", [])
    # 如果有多页，继续拉取
    next_url = data.get("next")
    while next_url:
        resp = requests.get(next_url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        all_tasks.extend(data.get("results", []))
        next_url = data.get("next")
    return all_tasks


def filter_orchestrator_tasks(tasks: list[dict]) -> list[dict]:
    """筛选 contract.orchestrator=true 的 Task"""
    return [t for t in tasks if t.get("contract", {}).get("orchestrator") is True]


def group_by_plan(tasks: list[dict]) -> dict[str, list[dict]]:
    """按 plan_id 分组"""
    groups = defaultdict(list)
    for t in tasks:
        plan_id = t.get("contract", {}).get("plan_id", "__no_plan__")
        groups[plan_id].append(t)
    return dict(groups)


def patch_task_status(task_id: int, status: str, result: Optional[dict] = None) -> dict:
    """PATCH 更新 Task 状态"""
    payload = {"status": status}
    if result is not None:
        payload["result"] = result
    resp = requests.patch(
        f"{API_BASE}/tasks/{task_id}/",
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def find_ready_tasks(plan_tasks: list[dict]) -> list[dict]:
    """
    找到当前 plan 中所有可执行的 Task：
    - status = pending
    - depends_on 中的所有 task（同 plan 内）都是 completed
    """
    # 构建 step_id → task 映射
    step_map = {}
    for t in plan_tasks:
        step_id = t.get("contract", {}).get("step_id")
        if step_id:
            step_map[step_id] = t

    ready = []
    for t in plan_tasks:
        if t.get("status") != "pending":
            continue
        depends = t.get("contract", {}).get("depends_on", [])
        if not depends:
            # 无依赖，直接可执行
            ready.append(t)
            continue

        # 检查所有依赖是否已完成
        all_deps_satisfied = True
        for dep_step_id in depends:
            dep_task = step_map.get(dep_step_id)
            if dep_task is None:
                # 依赖的 step_id 不存在于同 plan 中 → 视为不满足
                all_deps_satisfied = False
                break
            if dep_task.get("status") != "completed":
                all_deps_satisfied = False
                break

        if all_deps_satisfied:
            ready.append(t)

    return ready


def run_plan(plan_id: str, plan_tasks: list[dict], max_parallel: int = 2) -> list[dict]:
    """
    执行一个 plan 的完整依赖链。
    返回执行结果列表，每个元素包含 task_id、status、output。
    注意：实际的 delegate_task 调用由 Hermes 层面完成；
    本函数只做状态管理和「告诉 Hermes 该执行什么」。
    """
    execution_queue = []  # 返回给 Hermes 的待执行任务列表
    completed_in_round = []

    while True:
        ready = find_ready_tasks(plan_tasks)
        if not ready:
            break

        # 每次最多 max_parallel 个
        batch = ready[:max_parallel]

        for task in batch:
            task_id = task["id"]
            step_id = task.get("contract", {}).get("step_id", "?")
            desc = task.get("description", "")

            # 标记 in_progress
            try:
                patch_task_status(task_id, "in_progress")
            except Exception as e:
                print(f"[ERROR] 标记 Task#{task_id} in_progress 失败: {e}", file=sys.stderr)
                continue

            # 添加到待执行队列（Hermes 层会读取并调用 delegate_task）
            execution_queue.append({
                "task_id": task_id,
                "plan_id": plan_id,
                "step_id": step_id,
                "description": desc,
                "toolsets": ["terminal", "file", "web"],
            })

            # 在内存中标记为 in_progress（以便下一轮 find_ready 能正确判断）
            task["status"] = "in_progress"
            completed_in_round.append(task)

    return execution_queue


def main():
    """主入口：分析当前所有 plan 并返回待执行任务列表（JSON 输出到 stdout）"""
    try:
        all_tasks = fetch_tasks()
    except Exception as e:
        print(json.dumps({"error": f"拉取任务失败: {e}"}), file=sys.stderr)
        sys.exit(1)

    orch_tasks = filter_orchestrator_tasks(all_tasks)
    if not orch_tasks:
        print(json.dumps({"message": "无 orchestrator 任务", "queue": []}))
        return

    plans = group_by_plan(orch_tasks)

    all_queue = []
    for plan_id, plan_tasks in plans.items():
        queue = run_plan(plan_id, plan_tasks)
        all_queue.extend(queue)

    print(json.dumps({
        "plans": list(plans.keys()),
        "total_orchestrator_tasks": len(orch_tasks),
        "ready_to_execute": len(all_queue),
        "queue": all_queue,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
