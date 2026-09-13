"""Turn editable analysis results into reusable Skill packages."""

from __future__ import annotations

import json
import re
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any


def analysis_to_markdown(data: dict[str, Any]) -> str:
    """Render one structured analysis result as an author-editable document."""
    source = Path(str(data.get("source") or "未知素材")).name
    lines = [
        "# 素材拆解编辑稿",
        "",
        f"- 来源素材：{source}",
        f"- 拆解时间：{data.get('created_at') or '未记录'}",
        "",
    ]
    analyses = data.get("analyses")
    if not isinstance(analyses, list) or not analyses:
        lines.extend(["## 原始结果", "", json.dumps(data, ensure_ascii=False, indent=2)])
        return "\n".join(lines).strip() + "\n"

    for analysis in analyses:
        if not isinstance(analysis, dict):
            continue
        dimension = str(analysis.get("dimension") or "未分类")
        lines.extend([f"## {dimension}", ""])
        summary = str(analysis.get("summary") or "").strip()
        if summary:
            lines.extend(["### 总结", "", summary, ""])
        rules = analysis.get("rules")
        if not isinstance(rules, list) or not rules:
            lines.extend(["### 可复用规则", "", "暂未提取到规则。", ""])
            continue
        lines.extend(["### 可复用规则", ""])
        for index, rule in enumerate(rules, start=1):
            if not isinstance(rule, dict):
                continue
            content = str(rule.get("content") or "").strip()
            if not content:
                continue
            lines.append(f"{index}. **{content}**")
            lines.append(f"   - 重要度：{rule.get('weight', 50)}")
            explanation = str(rule.get("explanation") or "").strip()
            if explanation:
                lines.append(f"   - 原理：{explanation}")
            examples = rule.get("examples")
            if isinstance(examples, list):
                for example in examples:
                    example_text = str(example).strip()
                    if example_text:
                        lines.append(f"   - 例证：{example_text}")
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_analysis_skill_prompt(name: str, author_direction: str, edited_analysis: str) -> str:
    """Build a bounded prompt for converting evidence into a reusable Skill."""
    return (
        "请把作者编辑后的素材拆解结果，结合作者自己的创作要求，整理成一份可直接使用的 "
        "SKILL.md。不要照抄示例原文，不要把单个故事的专有名词写成通用规则。\n\n"
        f"Skill 显示名称：{name.strip()}\n"
        f"作者补充要求：\n{author_direction.strip()}\n\n"
        "生成要求：\n"
        "1. 输出完整 Markdown，并包含合法 YAML frontmatter，其中必须有 name 和 description。\n"
        "2. 只保留会改变创作判断的具体规则，删除空话、重复项和互相冲突的规则。\n"
        "3. 正文至少包含适用场景、创作流程、关键规则、自检标准和失败时的修正办法。\n"
        "4. 明确区分必须遵守的约束与可按题材调整的建议。\n"
        "5. 只输出 Skill 内容，不要附加解释或代码围栏。\n\n"
        f"作者编辑后的拆解结果：\n{edited_analysis.strip()}"
    )


def skill_slug(display_name: str) -> str:
    """Return a portable skill identifier accepted by common Skill loaders."""
    tokens = re.findall(r"[a-z0-9]+", display_name.lower())
    slug = "-".join(tokens).strip("-")
    return slug[:63] or "novel-writing-skill"


def _strip_generated_wrappers(text: str) -> str:
    value = text.strip()
    if value.startswith("```") and value.endswith("```"):
        value = re.sub(r"^```(?:markdown|md|yaml)?\s*\n?", "", value, flags=re.IGNORECASE)
        value = re.sub(r"\n?```$", "", value).strip()
    if value.startswith("---"):
        value = re.sub(r"\A---\s*\n.*?\n---\s*\n?", "", value, count=1, flags=re.DOTALL)
    return value.strip()


def normalize_skill_markdown(display_name: str, description: str, generated_text: str) -> str:
    """Guarantee required frontmatter while preserving the author's edited body."""
    body = _strip_generated_wrappers(generated_text)
    if not body:
        raise ValueError("Skill 内容不能为空")
    name = skill_slug(display_name)
    summary = description.strip() or f"用于执行{display_name.strip() or '小说创作'}的方法与规则。"
    frontmatter = (
        "---\n"
        f"name: {name}\n"
        f"description: {json.dumps(summary.replace(chr(10), ' '), ensure_ascii=False)}\n"
        "---\n\n"
    )
    if not body.startswith("# "):
        body = f"# {display_name.strip() or '小说创作 Skill'}\n\n{body}"
    return frontmatter + body.rstrip() + "\n"


def build_skill_zip(skill_id: str, skill_markdown: str) -> bytes:
    """Package a generated SKILL.md without writing temporary files."""
    root = skill_slug(skill_id)
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{root}/SKILL.md", skill_markdown.encode("utf-8"))
    return buffer.getvalue()
