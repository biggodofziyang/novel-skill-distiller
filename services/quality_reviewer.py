"""Local, deterministic quality checks for novel chapters."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any


def review_chapter(text: str, title: str = "未命名章节") -> dict[str, Any]:
    """Return actionable chapter metrics without sending text to an API."""
    content = text.strip()
    paragraphs = [item.strip() for item in re.split(r"\n\s*\n|\n", content) if item.strip()]
    sentences = [item for item in re.split(r"[。！？!?；;]+", content) if item.strip()]
    dialogue = len(re.findall(r"[“\"「『].*?[”\"」』]", content, re.S))
    hook_markers = ("却", "突然", "没想到", "就在这时", "原来", "怎么办", "门外", "声音")
    ending = content[-180:] if content else ""
    issues: list[dict[str, Any]] = []

    if len(content) < 1200:
        issues.append({"level": "warn", "code": "short", "message": "章节正文偏短，可能不足以完成一个完整冲突单元。"})
    if len(paragraphs) and max(len(item) for item in paragraphs) > 420:
        issues.append({"level": "warn", "code": "dense", "message": "存在过长段落，移动端阅读可能过于拥挤。"})
    if len(sentences) >= 8 and sum(len(item) for item in sentences) / len(sentences) > 85:
        issues.append({"level": "warn", "code": "slow", "message": "平均句子偏长，建议增加动作、对白或节奏断点。"})
    if content and not any(marker in ending for marker in hook_markers):
        issues.append({"level": "warn", "code": "ending", "message": "章末暂未检测到明显悬念或转折信号。"})
    repeated = [item for item, count in Counter(re.findall(r"[\u4e00-\u9fff]{5,12}", content)).items() if count >= 3]
    if repeated:
        issues.append({"level": "info", "code": "repeat", "message": f"检测到可能重复的短语：{', '.join(repeated[:5])}"})
    if not dialogue and len(content) > 800:
        issues.append({"level": "info", "code": "dialogue", "message": "本章对白较少，可检查人物互动和信息交换是否足够。"})

    score = max(0, min(100, 100 - sum(15 if item["level"] == "warn" else 6 for item in issues)))
    return {
        "title": title,
        "score": score,
        "metrics": {
            "characters": len(content),
            "paragraphs": len(paragraphs),
            "sentences": len(sentences),
            "dialogue_blocks": dialogue,
            "ending_preview": ending,
        },
        "issues": issues,
        "recommendations": [item["message"] for item in issues],
    }
