"""Local evaluation helpers for comparing Skill versions before adoption."""

from __future__ import annotations

import re
from typing import Any


def _metrics(text: str) -> dict[str, int]:
    return {
        "characters": len(text),
        "sections": len(re.findall(r"^#{1,3}\\s", text, re.M)),
        "rules": len(re.findall(r"(?:规则|必须|要求|禁止|输出|检查|验证)", text)),
        "examples": len(re.findall(r"(?:示例|例子|example)", text, re.I)),
        "rollback": len(re.findall(r"(?:回滚|撤销|失败|边界|风险)", text)),
    }


def compare_skills(name_a: str, text_a: str, name_b: str, text_b: str) -> dict[str, Any]:
    """Compare two versions with transparent local signals."""
    metrics_a = _metrics(text_a)
    metrics_b = _metrics(text_b)
    weights = {"sections": 10, "rules": 12, "examples": 8, "rollback": 8}
    score_a = min(100, sum(min(metrics_a[key], 5) * weight for key, weight in weights.items()))
    score_b = min(100, sum(min(metrics_b[key], 5) * weight for key, weight in weights.items()))
    winner = name_a if score_a > score_b else name_b if score_b > score_a else "平局"
    return {
        "winner": winner,
        "scores": {name_a: score_a, name_b: score_b},
        "metrics": {name_a: metrics_a, name_b: metrics_b},
        "decision": "建议先小规模试用胜出版本，再人工确认是否设为正式版本。",
    }
