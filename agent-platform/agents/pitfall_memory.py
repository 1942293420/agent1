#!/usr/bin/env python3
"""
Pitfall Memory — 异常踩坑学习系统

设计原则：
  - 不调 LLM：纯本地模式匹配
  - 自我成长：每次 LLM 修复成功后自动记录
  - 防止重复踩坑：遇到相同错误直接应用已知修复

存储格式（JSON 文件）：
{
  "version": 1,
  "entries": [
    {
      "id": "pit_001",
      "pattern": "错误关键词或正则",
      "context": "什么场景下出现（shell命令、文件操作等）",
      "fix_type": "command_fix | retry | skip | replace | ask_user",
      "fix_detail": "具体修复指令",
      "created_at": "ISO时间",
      "hit_count": 3,
      "last_hit": "ISO时间"
    }
  ]
}
"""

import json
import os
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

PITFALL_FILE = os.path.expanduser("~/.hermes/profiles/Banni/pitfall_memory.json")
TZ = timezone(timedelta(hours=8))


def _now() -> str:
    return datetime.now(TZ).isoformat()


def _load() -> dict:
    """加载坑位记忆"""
    if not os.path.exists(PITFALL_FILE):
        return {"version": 1, "entries": []}
    try:
        with open(PITFALL_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"version": 1, "entries": []}


def _save(data: dict):
    """保存坑位记忆"""
    os.makedirs(os.path.dirname(PITFALL_FILE), exist_ok=True)
    with open(PITFALL_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def search_pitfall(error_text: str, context: str = "") -> Optional[dict]:
    """
    搜索已知坑位：用 error_text 匹配所有条目
    返回匹配到的条目，或 None
    """
    data = _load()
    error_lower = error_text.lower()

    for entry in data["entries"]:
        patterns = entry.get("pattern", [])
        if isinstance(patterns, str):
            patterns = [patterns]

        for pattern in patterns:
            # 支持简单正则（用 /pattern/ 包裹）或纯文本子串匹配
            if pattern.startswith("/") and pattern.endswith("/"):
                try:
                    if re.search(pattern[1:-1], error_text, re.IGNORECASE):
                        entry["hit_count"] = entry.get("hit_count", 0) + 1
                        entry["last_hit"] = _now()
                        _save(data)
                        return entry
                except re.error:
                    pass
            elif pattern.lower() in error_lower:
                entry["hit_count"] = entry.get("hit_count", 0) + 1
                entry["last_hit"] = _now()
                _save(data)
                return entry

    return None


def record_pitfall(pattern: str, context: str, fix_type: str, fix_detail: str) -> str:
    """
    记录一个新坑位（通常在 LLM 修复成功后调用）
    返回条目 ID
    """
    data = _load()
    entry_id = f"pit_{len(data['entries']) + 1:03d}"

    entry = {
        "id": entry_id,
        "pattern": [pattern],
        "context": context,
        "fix_type": fix_type,
        "fix_detail": fix_detail,
        "created_at": _now(),
        "hit_count": 0,
        "last_hit": None,
    }
    data["entries"].append(entry)
    _save(data)
    return entry_id


def apply_fix(entry: dict, step_context: dict) -> tuple[bool, str]:
    """
    应用已知修复。返回 (success, result_or_error)
    
    fix_type:
      - command_fix:  执行 fix_detail 中的命令
      - retry:        重试原步骤（with modifications from fix_detail）
      - skip:         跳过此步骤
      - replace:      用 fix_detail 替换步骤内容
      - ask_user:     返回需要用户介入的消息
    """
    fix_type = entry.get("fix_type", "retry")

    if fix_type == "command_fix":
        import subprocess
        try:
            result = subprocess.run(
                entry["fix_detail"], shell=True,
                capture_output=True, text=True, timeout=30,
                cwd="/home/jiangli",
                env={**os.environ, "HOME": "/home/jiangli"}
            )
            output = (result.stdout + result.stderr)[:3000]
            if result.returncode == 0:
                return True, output
            return False, f"修复命令失败(exit={result.returncode}): {output[:500]}"
        except Exception as e:
            return False, f"修复命令异常: {e}"

    elif fix_type == "retry":
        return True, f"[pitfall] 已应用重试策略: {entry['fix_detail']}"

    elif fix_type == "skip":
        return True, f"[pitfall] 已跳过（已知问题）: {entry['fix_detail']}"

    elif fix_type == "replace":
        return True, f"[pitfall] 已替换: {entry['fix_detail']}"

    elif fix_type == "ask_user":
        return False, f"[pitfall] 需要用户介入: {entry['fix_detail']}"

    return False, f"未知 fix_type: {fix_type}"


def get_stats() -> dict:
    """获取坑位记忆统计"""
    data = _load()
    entries = data["entries"]
    total_hits = sum(e.get("hit_count", 0) for e in entries)
    return {
        "total_entries": len(entries),
        "total_hits": total_hits,
        "top_hits": sorted(entries, key=lambda e: e.get("hit_count", 0), reverse=True)[:5],
        "recent": sorted(
            [e for e in entries if e.get("last_hit")],
            key=lambda e: e["last_hit"], reverse=True
        )[:5],
    }


def export_as_skill() -> str:
    """将坑位记忆导出为可读的技能描述（用于手动审查/分享）"""
    data = _load()
    if not data["entries"]:
        return "暂无坑位记忆。"

    lines = ["# 踩坑记忆导出", f"共 {len(data['entries'])} 条记录\n"]
    for e in sorted(data["entries"], key=lambda x: x.get("hit_count", 0), reverse=True):
        patterns = e.get("pattern", [])
        if isinstance(patterns, str):
            patterns = [patterns]
        lines.append(f"## {e['id']} — 命中 {e.get('hit_count', 0)} 次")
        lines.append(f"- **错误特征**: {', '.join(patterns)}")
        lines.append(f"- **场景**: {e.get('context', '无')}")
        lines.append(f"- **修复方式**: {e.get('fix_type')}")
        lines.append(f"- **修复指令**: {e.get('fix_detail', '无')}")
        lines.append("")
    return "\n".join(lines)
