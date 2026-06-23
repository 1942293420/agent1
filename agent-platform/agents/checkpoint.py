"""
Checkpoint 管理器 — v4 新增
检查点持久化 + Worker 崩溃恢复。
"""
import json
import os
import threading

CHECKPOINT_DIR = os.path.expanduser("~/projects/agent-platform/checkpoints")
MAX_FILES = 3


class CheckpointManager:
    MAX_FILES = 3  # class-level constant
    def __init__(self, parent_task_id: int):
        self.parent_id = parent_task_id
        self.lock = threading.Lock()
        os.makedirs(CHECKPOINT_DIR, exist_ok=True)

    def _file_path(self, n: int) -> str:
        return os.path.join(CHECKPOINT_DIR, f"checkpoint_{n}.json")

    def write_checkpoint(self, stage: str, children_state: dict,
                         yunshu_line: int = 0, summary_text: str = ""):
        """写检查点到文件 + DB"""
        data = {
            "parent_task_id": self.parent_id,
            "stage": stage,
            "children_state": children_state,
            "yunshu_output_line": yunshu_line,
            "summary_text": summary_text,
        }
        with self.lock:
            # 循环覆盖：最多 3 个文件
            for n in range(1, MAX_FILES):
                src = self._file_path(n + 1)
                dst = self._file_path(n)
                if os.path.exists(src):
                    os.rename(src, dst)
            with open(self._file_path(MAX_FILES), "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            # 同步写 DB
            self._write_db(stage, children_state, yunshu_line, summary_text)

    def _write_db(self, stage: str, children_state: dict,
                  yunshu_line: int, summary_text: str):
        try:
            import requests
            requests.post(
                f"http://localhost:8001/api/checkpoints/",
                json={
                    "parent_task_id": self.parent_id,
                    "stage": stage,
                    "children_state": children_state,
                    "yunshu_output_line": yunshu_line,
                    "summary_text": summary_text,
                },
                timeout=5,
            )
        except Exception:
            pass

    def load_latest(self) -> dict | None:
        """从 DB 读取最新检查点"""
        try:
            import requests
            r = requests.get(
                f"http://localhost:8001/api/checkpoints/?parent_task_id={self.parent_id}&latest=1",
                timeout=5,
            )
            data = r.json()
            checkpoints = data if isinstance(data, list) else data.get("checkpoints", [])
            return checkpoints[0] if checkpoints else None
        except Exception:
            return None

    def build_recovery_context(self, checkpoint: dict) -> str:
        """构造恢复上下文摘要"""
        children = checkpoint.get("children_state", {})
        done = [f"{tid}({st['status']})" for tid, st in children.items()
                if st.get("status") in ("DONE", "FAILED", "TIMED_OUT")]
        pending = [tid for tid, st in children.items()
                   if st.get("status") in ("PENDING", "RUNNING")]

        lines = [
            "[恢复上下文]",
            f"父任务 #{self.parent_id} 从 {checkpoint.get('stage', '?')} 恢复",
            f"已完成: {', '.join(done) if done else '无'}",
            f"待执行: {', '.join(pending) if pending else '无'}",
        ]
        if checkpoint.get("summary_text"):
            lines.append(f"摘要: {checkpoint['summary_text']}")
        return "\n".join(lines)
