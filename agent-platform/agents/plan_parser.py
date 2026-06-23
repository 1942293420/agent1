"""
PLAN 解析器 — v4 新增
解析 Yunshu 的 PLAN 命令输出，构建依赖图，计算护栏自适应。
"""
import re
from dataclasses import dataclass, field


@dataclass
class PlanNode:
    task_id: str
    agent_type: str
    description: str
    dependencies: list = field(default_factory=list)


@dataclass
class PlanGraph:
    complexity: str = "medium"
    nodes: list = field(default_factory=list)
    adjacency: dict = field(default_factory=dict)
    parallel_count: int = 0
    serial_count: int = 0

    @staticmethod
    def parse(text: str):
        """从 Yunshu 的 PLAN 输出解析。宽松匹配，容错。"""
        # 提取 complexity
        comp_match = re.search(r"complexity:\s*(simple|medium|complex)", text, re.I)
        complexity = comp_match.group(1).lower() if comp_match else "medium"

        # 提取 tasks 块
        tasks_block = re.search(r"tasks:\s*\n(.*?)(?=\n\S|\Z)", text, re.DOTALL)
        if not tasks_block:
            return None

        nodes = []
        task_pattern = re.compile(
            r"-\s*id:\s*(\S+).*?agent:\s*(\S+).*?desc:\s*(.+?)(?:\s+deps:\s*(\[.*?\]))?\s*$",
            re.MULTILINE
        )

        for m in task_pattern.finditer(tasks_block.group(1)):
            tid = m.group(1).rstrip(",")
            agent = m.group(2).lower()
            desc = m.group(3).strip().rstrip(",")
            deps_str = m.group(4) or "[]"
            deps = [d.strip('"\' []') for d in deps_str.strip("[]").split(",") if d.strip()]
            nodes.append(PlanNode(task_id=tid, agent_type=agent, description=desc, dependencies=deps))

        if not nodes:
            return None

        # 构建依赖图
        adjacency = {}
        for n in nodes:
            adjacency[n.task_id] = n.dependencies

        # 计算并行/串行
        has_deps = any(n.dependencies for n in nodes)
        no_deps = [n for n in nodes if not n.dependencies]
        parallel_count = len(no_deps)
        serial_count = len(nodes) - parallel_count if has_deps else 0

        return PlanGraph(
            complexity=complexity,
            nodes=nodes,
            adjacency=adjacency,
            parallel_count=parallel_count,
            serial_count=serial_count,
        )

    def get_suggested_max_spawn(self) -> int:
        mapping = {"simple": 1, "medium": 3, "complex": 5}
        return mapping.get(self.complexity, 3)

    def validate(self) -> bool:
        """验证依赖图无环，所有 task_id 唯一"""
        ids = set()
        for n in self.nodes:
            if n.task_id in ids:
                return False
            ids.add(n.task_id)
            for dep in n.dependencies:
                if dep not in {x.task_id for x in self.nodes}:
                    return False
        return True

    def get_parallel_groups(self) -> list:
        """返回并行组（无依赖的节点可以同时启动）"""
        groups = []
        remaining = {n.task_id: n for n in self.nodes}

        while remaining:
            group = [tid for tid, n in remaining.items()
                     if all(d not in remaining for d in n.dependencies)]
            if not group:
                break
            groups.append(group)
            for tid in group:
                del remaining[tid]
        return groups


def heuristic_complexity(user_message: str, plan_node_count: int) -> str:
    """Yunshu 未声明 complexity 时的启发式估算"""
    if len(user_message) > 200 or plan_node_count > 3:
        return "complex"
    return "medium"
