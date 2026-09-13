"""Project workspaces and independent local output storage."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from core.constants import DATA_DIR


WORKSPACE_ROOT = DATA_DIR / "workspaces"
DEFAULT_WORKSPACE_ID = "default"


FOLDERS = (
    ("小说资料", "Source novels and uploaded material"),
    ("参考章节", "Reference chapters"),
    ("章节内容", "Generated chapter content"),
    ("Skill", "Imported and combined Skills"),
    ("拆解结果", "Independent analysis outputs"),
    ("蒸馏结果", "Independent distilled rules"),
    ("创作结果", "World, characters and golden chapters"),
    ("迭代记录", "Feedback and version history"),
    ("任务记录", "Pause and resume task records"),
)


class WorkspaceStore:
    """File-backed workspace store designed for the right-hand file tree."""

    def __init__(self, workspace_id: str = DEFAULT_WORKSPACE_ID) -> None:
        self.workspace_id = workspace_id
        self.root = WORKSPACE_ROOT / workspace_id
        self.ensure()

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        for folder, _ in FOLDERS:
            (self.root / folder).mkdir(parents=True, exist_ok=True)

    def _resolve_write_path(self, folder: str, filename: str) -> Path:
        """Resolve a writable path and keep it inside this workspace."""
        root = self.root.resolve()
        base = (root / folder).resolve()
        path = (base / filename).resolve()
        if root not in path.parents or path == root:
            raise ValueError("文件路径必须位于当前工作区内")
        return path
    def save_text(self, folder: str, filename: str, content: str) -> Path:
        path = self._resolve_write_path(folder, filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def save_bytes(self, folder: str, filename: str, content: bytes) -> Path:
        path = self._resolve_write_path(folder, filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def save_json(self, folder: str, filename: str, data: Any) -> Path:
        return self.save_text(folder, filename, json.dumps(data, ensure_ascii=False, indent=2, default=str))

    def list_tree(self) -> list[dict[str, Any]]:
        self.ensure()
        tree: list[dict[str, Any]] = []
        for folder, description in FOLDERS:
            folder_path = self.root / folder
            files = sorted(
                path.relative_to(folder_path).as_posix()
                for path in folder_path.rglob("*")
                if path.is_file()
            )
            tree.append({"name": folder, "description": description, "files": files, "system": True})
        for folder_path in sorted(path for path in self.root.iterdir() if path.is_dir() and path.name not in {item[0] for item in FOLDERS}):
            files = sorted(path.relative_to(folder_path).as_posix() for path in folder_path.rglob("*") if path.is_file())
            tree.append({"name": folder_path.name, "description": "用户创建的文件夹", "files": files, "system": False})
        return tree

    def create_folder(self, name: str) -> Path:
        """Create a user folder inside the workspace root."""
        clean = Path(name.strip()).name
        if not clean or clean in {".", ".."}:
            raise ValueError("文件夹名称不能为空")
        if clean in {folder for folder, _ in FOLDERS}:
            raise ValueError("该名称是系统目录，不能重复创建")
        path = self.root / clean
        path.mkdir(parents=True, exist_ok=False)
        return path

    def create_file(self, folder: str, filename: str, content: str = "") -> Path:
        """Create a new editable text file in an existing workspace folder."""
        clean_folder = Path(folder.strip()).name
        folder_path = (self.root / clean_folder).resolve()
        root = self.root.resolve()
        if not clean_folder or root not in folder_path.parents or not folder_path.is_dir():
            raise FileNotFoundError("目标文件夹不存在")

        clean_name = Path(filename.strip()).name
        if not clean_name or clean_name in {".", ".."}:
            raise ValueError("文件名称不能为空")
        if not Path(clean_name).suffix:
            clean_name = f"{clean_name}.md"

        path = self._resolve_write_path(clean_folder, clean_name)
        if path.exists():
            raise FileExistsError("同名文件已经存在")
        path.write_text(content, encoding="utf-8")
        return path

    def delete_folder(self, name: str) -> None:
        """Delete a user-created folder, never a system folder."""
        clean = Path(name.strip()).name
        if clean in {folder for folder, _ in FOLDERS}:
            raise ValueError("系统目录不能删除")
        path = self.root / clean
        if not path.exists() or not path.is_dir():
            raise FileNotFoundError("文件夹不存在")
        import shutil
        shutil.rmtree(path)
    def read_file(self, relative_path: str) -> str:
        path = self.root / Path(relative_path)
        if not path.is_file() or self.root not in path.resolve().parents:
            raise FileNotFoundError("文件不存在")
        return path.read_text(encoding="utf-8", errors="replace")

    def write_file(self, relative_path: str, content: str) -> Path:
        path = self.root / Path(relative_path)
        if self.root not in path.resolve().parents:
            raise ValueError("文件路径无效")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def delete_file(self, relative_path: str) -> None:
        path = self.root / Path(relative_path)
        if not path.is_file() or self.root not in path.resolve().parents:
            raise FileNotFoundError("文件不存在")
        path.unlink()

    def project_profile(self) -> dict[str, Any]:
        path = self.root / "项目设定.json"
        if not path.exists():
            return {"name": "我的新小说", "genre": "", "premise": "", "audience": ""}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"name": "我的新小说", "genre": "", "premise": "", "audience": ""}

    def save_project_profile(self, profile: dict[str, Any]) -> Path:
        return self.save_json("", "项目设定.json", profile)
    def new_id(self) -> str:
        return uuid.uuid4().hex[:10]

    def timestamp(self) -> str:
        return datetime.now().isoformat(timespec="seconds")




