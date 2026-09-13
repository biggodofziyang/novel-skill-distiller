"""Local Skill package catalog and importer."""

from __future__ import annotations

import re
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path

from core.constants import DATA_DIR


SKILL_LIBRARY_DIR = DATA_DIR / "skill_library"
SOURCE_DIR = Path.home() / "Desktop" / "小说软件Skill"
BUILTIN_SKILL_PATH = Path(__file__).resolve().parent.parent / "config" / "builtin_skills" / "openai-docs" / "SKILL.md"


@dataclass(frozen=True)
class SkillPackage:
    package_id: str
    name: str
    description: str
    zip_path: Path
    root_name: str
    modules: tuple[str, ...]
    file_count: int

    def read_entry(self, suffix: str = "SKILL.md") -> str:
        """Read a text entry from the package without extracting it."""
        if self.zip_path.is_dir():
            entry = self.zip_path / suffix
            return entry.read_text(encoding="utf-8", errors="replace") if entry.is_file() else ""
        with zipfile.ZipFile(self.zip_path) as archive:
            candidates = [
                name for name in archive.namelist()
                if name.endswith(suffix) and not name.endswith("/")
            ]
            if not candidates:
                return ""
            return archive.read(candidates[0]).decode("utf-8", "replace")

    def prompt_context(self, max_chars: int = 16000) -> str:
        """Return the package entry point as bounded prompt context."""
        text = self.read_entry()
        if len(text) > max_chars:
            text = text[:max_chars] + "\n[Skill context truncated]"
        return f"## Skill: {self.name}\n{text}"


_PACKAGE_INFO: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("AI辅助的视频编辑工作流程", "video-editing", "AI辅助视频编辑与真实素材工作流", ("feedback", "creation")),
    ("小说剧本转分镜表", "storyboard-creator", "将小说或剧本转换为详细分镜表", ("creation", "feedback")),
    ("小说改编", "novel-outline", "小说改编为短剧大纲与质量门报告", ("distill", "feedback")),
    ("小说故事转视频请求", "dramaclaw", "小说到短剧视频的工程化流程", ("creation", "feedback")),
    ("小说续写", "story-import", "已有小说逆向导入为可续写工程", ("creation", "material")),
    ("短拆解", "story-short-analyze", "短篇网文结构、情绪和反转拆解", ("material", "distill")),
    ("长拆解", "story-long-analyze", "长篇黄金三章与全量结构拆解", ("material", "distill")),
    ("openai-docs", "openai-docs", "OpenAI 官方文档、API、模型、提示词和 Skill 规范", ("skill", "feedback", "settings", "creation")),
)


def _safe_name(value: str) -> str:
    return re.sub(r"[^\w\-\u4e00-\u9fff]+", "-", value).strip("-") or "skill"


def ensure_bundled_packages() -> None:
    """Copy the user's seven supplied packages into app-local storage once."""
    SKILL_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    if not SOURCE_DIR.exists():
        return
    for source in SOURCE_DIR.glob("*.zip"):
        target = SKILL_LIBRARY_DIR / source.name
        if not target.exists() or source.stat().st_mtime > target.stat().st_mtime:
            shutil.copy2(source, target)


def import_package(filename: str, content: bytes) -> Path:
    """Persist an uploaded Skill zip in the local library."""
    SKILL_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    target = SKILL_LIBRARY_DIR / f"{_safe_name(Path(filename).stem)}.zip"
    target.write_bytes(content)
    return target


def list_packages() -> list[SkillPackage]:
    ensure_bundled_packages()
    packages: list[SkillPackage] = []
    for path in sorted(SKILL_LIBRARY_DIR.glob("*.zip")):
        matched = next((item for item in _PACKAGE_INFO if item[0] in path.stem), None)
        if matched:
            name, package_id, description, modules = matched
        else:
            name = path.stem
            package_id = _safe_name(path.stem)
            description = "用户上传的 Skill 包"
            modules = ("skill",)
        try:
            with zipfile.ZipFile(path) as archive:
                file_count = len([n for n in archive.namelist() if not n.endswith("/")])
                root_name = archive.namelist()[0].split("/")[0] if archive.namelist() else ""
        except zipfile.BadZipFile:
            continue
        packages.append(SkillPackage(
            package_id=package_id,
            name=name,
            description=description,
            zip_path=path,
            root_name=root_name,
            modules=modules,
            file_count=file_count,
        ))
    if not any(package.package_id == "openai-docs" for package in packages) and BUILTIN_SKILL_PATH.is_file():
        packages.append(SkillPackage(
            package_id="openai-docs",
            name="OpenAI Docs",
            description="OpenAI 兼容接口和 Skill 使用基础说明",
            zip_path=BUILTIN_SKILL_PATH.parent,
            root_name="openai-docs",
            modules=("skill", "feedback", "settings", "creation", "chapters", "material", "distill"),
            file_count=1,
        ))
    return packages


def packages_for_module(module: str) -> list[SkillPackage]:
    return [package for package in list_packages() if module in package.modules or "skill" in package.modules]


def package_context(package_ids: list[str], max_chars: int = 18000) -> str:
    packages = {package.package_id: package for package in list_packages()}
    contexts = [packages[package_id].prompt_context() for package_id in package_ids if package_id in packages]
    context = "\n\n".join(contexts)
    return context[:max_chars]
