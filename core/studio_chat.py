"""Persistent multi-turn chat sessions for AI-assisted creation modules."""

from __future__ import annotations

import json
from typing import Any

from core.workspace import WorkspaceStore


STUDIO_MODULES = ("material", "creation", "chapters", "distill")

MODULE_LABELS = {
    "material": "素材拆解",
    "chapters": "章节写作",
    "distill": "规则蒸馏",
    "creation": "分步创作",
}

MODULE_CONTRACTS = {
    "material": (
        "围绕提供的小说素材拆解故事结构、人物目标、情绪、节奏、悬念和写作方法。"
        "区分原文证据与推断，不得编造未提供的剧情。允许作者通过对话纠正结论，"
        "并结合作者要求整理成可复用的 Skill 草稿。"
    ),
    "chapters": (
        "围绕当前章节目标、冲突、人物状态和前文连续性创作。"
        "需要正文时直接给出可继续编辑的章节正文，不要只给提纲。"
    ),
    "distill": (
        "从现有 Skill、拆解结果、正文表现、设定追踪和审查反馈中提炼"
        "可执行、可验证、可回滚的写作规则，并说明规则依据。"
    ),
    "creation": (
        "围绕当前选择的世界观、人物关系或黄金三章推进。"
        "保持三个产物相互一致，并给出可直接保存的完整草稿。"
    ),
}


def _validate_module(module: str) -> None:
    if module not in STUDIO_MODULES:
        raise ValueError(f"不支持的创作模块：{module}")


def new_session(store: WorkspaceStore, module: str) -> dict[str, Any]:
    """Create an empty module-scoped studio session."""
    _validate_module(module)
    now = store.timestamp()
    return {
        "id": store.new_id(),
        "module": module,
        "title": "新对话",
        "messages": [],
        "created_at": now,
        "updated_at": now,
    }


def save_session(store: WorkspaceStore, session: dict[str, Any]) -> None:
    """Persist one studio session without mixing module histories."""
    module = str(session.get("module", ""))
    _validate_module(module)
    session_id = str(session.get("id", "")).strip()
    if not session_id:
        raise ValueError("会话 ID 不能为空")
    session["updated_at"] = store.timestamp()
    store.save_json(
        "迭代记录",
        f"studio_{module}_{session_id}.json",
        session,
    )


def load_sessions(store: WorkspaceStore, module: str) -> list[dict[str, Any]]:
    """Load newest sessions for a module, skipping damaged files."""
    _validate_module(module)
    paths = sorted(
        (store.root / "迭代记录").glob(f"studio_{module}_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    sessions: list[dict[str, Any]] = []
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        if (
            isinstance(data, dict)
            and data.get("module") == module
            and isinstance(data.get("messages"), list)
            and data.get("id")
        ):
            sessions.append(data)
    return sessions


def build_studio_prompt(
    module: str,
    user_prompt: str,
    messages: list[dict[str, str]],
    metadata: dict[str, Any],
) -> str:
    """Build a bounded prompt that preserves recent multi-turn intent."""
    _validate_module(module)
    recent = messages[-10:]
    transcript = "\n".join(
        f"{'作者' if item.get('role') == 'user' else 'AI'}：{str(item.get('content', ''))[:4000]}"
        for item in recent
        if item.get("content")
    )
    metadata_text = json.dumps(metadata, ensure_ascii=False, indent=2, default=str)
    history = transcript or "暂无历史对话"
    return (
        f"你正在 OpenWrite 的“{MODULE_LABELS[module]}”工作台中与作者协作。\n"
        f"模块职责：{MODULE_CONTRACTS[module]}\n\n"
        "工作要求：\n"
        "1. 先承接作者最新意图，再利用已选择的 Skill 和提供的项目上下文完成任务。\n"
        "2. 需要澄清时只问真正阻碍创作的问题；信息足够时直接给出内容。\n"
        "3. 输出应便于继续对话修改，也应能直接进入当前草稿。\n"
        "4. 不得声称已经保存文件；只有作者点击保存后才算落盘。\n\n"
        f"当前创作设置：\n{metadata_text}\n\n"
        f"最近对话：\n{history}\n\n"
        f"作者最新要求：\n{user_prompt}"
    )
