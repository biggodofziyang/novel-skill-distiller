"""本地文件存储管理器.

封装全部CRUD操作，支持素材、拆解文件、规则集、Skill、项目、反馈的持久化.
数据格式支持JSON（结构化数据）和Markdown（可读文本）.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from core.constants import (
    ANALYSIS_DIR,
    FEEDBACK_DIR,
    MATERIAL_DIR,
    PROJECT_STORAGE_DIR,
    RULE_DIR,
    SKILL_DIR,
    TEMP_DIR,
)
from core.models import (
    AnalysisFile,
    CreationProject,
    FeedbackSample,
    NovelMaterial,
    RuleSet,
    Skill,
)
from utils.logger import get_logger

logger = get_logger(__name__)


class StorageManager:
    """本地存储管理器.

    负责所有领域对象的文件持久化，自动创建目录结构，
    提供统一的加载、保存、列表、删除接口.
    """

    def __init__(self) -> None:
        """初始化存储管理器，确保所有存储目录存在."""
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """创建全部存储目录（幂等）."""
        for directory in [
            MATERIAL_DIR,
            ANALYSIS_DIR,
            RULE_DIR,
            SKILL_DIR,
            PROJECT_STORAGE_DIR,
            FEEDBACK_DIR,
            TEMP_DIR,
        ]:
            directory.mkdir(parents=True, exist_ok=True)
            logger.debug("确保目录存在: %s", directory)

    # ============================ 通用工具方法 ============================

    @staticmethod
    def _write_json(path: Path, data: dict[str, Any]) -> None:
        """将字典写入JSON文件.

        Args:
            path: 目标文件路径.
            data: 要写入的字典数据.
        """
        try:
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            logger.debug("写入JSON文件: %s", path)
        except Exception as e:
            logger.error("写入JSON文件失败: %s, 错误: %s", path, e)
            raise

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        """从JSON文件读取字典.

        Args:
            path: 源文件路径.

        Returns:
            读取的字典数据.
        """
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error("读取JSON文件失败: %s, 错误: %s", path, e)
            raise

    @staticmethod
    def _write_markdown(path: Path, content: str) -> None:
        """将文本写入Markdown文件.

        Args:
            path: 目标文件路径.
            content: 要写入的文本内容.
        """
        try:
            path.write_text(content, encoding="utf-8")
            logger.debug("写入Markdown文件: %s", path)
        except Exception as e:
            logger.error("写入Markdown文件失败: %s, 错误: %s", path, e)
            raise

    @staticmethod
    def _read_markdown(path: Path) -> str:
        """从Markdown文件读取文本.

        Args:
            path: 源文件路径.

        Returns:
            读取的文本内容.
        """
        try:
            return path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error("读取Markdown文件失败: %s, 错误: %s", path, e)
            raise

    # ============================ 素材管理 ============================

    def save_material(self, material: NovelMaterial) -> Path:
        """保存素材.

        Args:
            material: 素材对象.

        Returns:
            保存的文件路径.
        """
        path = MATERIAL_DIR / f"{material.id}.json"
        self._write_json(path, material.model_dump(mode="json"))
        logger.info("保存素材: id=%s, path=%s", material.id, path)
        return path

    def load_material(self, material_id: str) -> NovelMaterial:
        """加载素材.

        Args:
            material_id: 素材ID.

        Returns:
            素材对象.
        """
        path = MATERIAL_DIR / f"{material_id}.json"
        data = self._read_json(path)
        return NovelMaterial.model_validate(data)

    def list_materials(self) -> list[NovelMaterial]:
        """列出全部素材.

        Returns:
            素材对象列表.
        """
        materials: list[NovelMaterial] = []
        for path in sorted(MATERIAL_DIR.glob("*.json")):
            try:
                data = self._read_json(path)
                materials.append(NovelMaterial.model_validate(data))
            except Exception as e:
                logger.warning("加载素材失败 %s: %s", path.name, e)
        return materials

    def delete_material(self, material_id: str) -> bool:
        """删除素材.

        Args:
            material_id: 素材ID.

        Returns:
            是否成功删除.
        """
        path = MATERIAL_DIR / f"{material_id}.json"
        if path.exists():
            path.unlink()
            logger.info("删除素材: id=%s", material_id)
            return True
        logger.warning("素材不存在，无法删除: id=%s", material_id)
        return False

    # ============================ 拆解文件管理 ============================

    def save_analysis(self, analysis: AnalysisFile) -> Path:
        """保存拆解结果.

        Args:
            analysis: 拆解结果对象.

        Returns:
            保存的文件路径.
        """
        path = ANALYSIS_DIR / f"{analysis.id}.json"
        self._write_json(path, analysis.model_dump(mode="json"))
        logger.info("保存拆解结果: id=%s, dimension=%s", analysis.id, analysis.dimension.value)
        return path

    def load_analysis(self, analysis_id: str) -> AnalysisFile:
        """加载拆解结果.

        Args:
            analysis_id: 拆解结果ID.

        Returns:
            拆解结果对象.
        """
        path = ANALYSIS_DIR / f"{analysis_id}.json"
        data = self._read_json(path)
        return AnalysisFile.model_validate(data)

    def list_analysis_by_material(self, material_id: str) -> list[AnalysisFile]:
        """按素材ID列出全部拆解结果.

        Args:
            material_id: 素材ID.

        Returns:
            拆解结果列表.
        """
        results: list[AnalysisFile] = []
        for path in sorted(ANALYSIS_DIR.glob("*.json")):
            try:
                data = self._read_json(path)
                if data.get("material_id") == material_id:
                    results.append(AnalysisFile.model_validate(data))
            except Exception as e:
                logger.warning("加载拆解结果失败 %s: %s", path.name, e)
        return results

    def delete_analysis(self, analysis_id: str) -> bool:
        """删除拆解结果.

        Args:
            analysis_id: 拆解结果ID.

        Returns:
            是否成功删除.
        """
        path = ANALYSIS_DIR / f"{analysis_id}.json"
        if path.exists():
            path.unlink()
            logger.info("删除拆解结果: id=%s", analysis_id)
            return True
        return False

    # ============================ 规则集管理 ============================

    def save_rule_set(self, rule_set: RuleSet) -> Path:
        """保存规则集.

        Args:
            rule_set: 规则集对象.

        Returns:
            保存的文件路径.
        """
        path = RULE_DIR / f"{rule_set.id}.json"
        self._write_json(path, rule_set.model_dump(mode="json"))
        logger.info("保存规则集: id=%s, name=%s", rule_set.id, rule_set.name)
        return path

    def load_rule_set(self, rule_set_id: str) -> RuleSet:
        """加载规则集.

        Args:
            rule_set_id: 规则集ID.

        Returns:
            规则集对象.
        """
        path = RULE_DIR / f"{rule_set_id}.json"
        data = self._read_json(path)
        return RuleSet.model_validate(data)

    def list_rule_sets(self) -> list[RuleSet]:
        """列出全部规则集.

        Returns:
            规则集列表.
        """
        rule_sets: list[RuleSet] = []
        for path in sorted(RULE_DIR.glob("*.json")):
            try:
                data = self._read_json(path)
                rule_sets.append(RuleSet.model_validate(data))
            except Exception as e:
                logger.warning("加载规则集失败 %s: %s", path.name, e)
        return rule_sets

    def delete_rule_set(self, rule_set_id: str) -> bool:
        """删除规则集.

        Args:
            rule_set_id: 规则集ID.

        Returns:
            是否成功删除.
        """
        path = RULE_DIR / f"{rule_set_id}.json"
        if path.exists():
            path.unlink()
            logger.info("删除规则集: id=%s", rule_set_id)
            return True
        return False

    # ============================ Skill管理 ============================

    def save_skill(self, skill: Skill) -> Path:
        """保存Skill.

        Args:
            skill: Skill对象.

        Returns:
            保存的文件路径.
        """
        path = SKILL_DIR / f"{skill.id}.json"
        self._write_json(path, skill.model_dump(mode="json"))
        logger.info("保存Skill: id=%s, name=%s", skill.id, skill.name)
        return path

    def load_skill(self, skill_id: str) -> Skill:
        """加载Skill.

        Args:
            skill_id: Skill ID.

        Returns:
            Skill对象.
        """
        path = SKILL_DIR / f"{skill_id}.json"
        data = self._read_json(path)
        return Skill.model_validate(data)

    def list_skills(self) -> list[Skill]:
        """列出全部Skill.

        Returns:
            Skill列表.
        """
        skills: list[Skill] = []
        for path in sorted(SKILL_DIR.glob("*.json")):
            try:
                data = self._read_json(path)
                skills.append(Skill.model_validate(data))
            except Exception as e:
                logger.warning("加载Skill失败 %s: %s", path.name, e)
        return skills

    def delete_skill(self, skill_id: str) -> bool:
        """删除Skill.

        Args:
            skill_id: Skill ID.

        Returns:
            是否成功删除.
        """
        path = SKILL_DIR / f"{skill_id}.json"
        if path.exists():
            path.unlink()
            logger.info("删除Skill: id=%s", skill_id)
            return True
        return False

    # ============================ 项目管理 ============================

    def save_project(self, project: CreationProject) -> Path:
        """保存创作项目.

        Args:
            project: 创作项目对象.

        Returns:
            保存的文件路径.
        """
        path = PROJECT_STORAGE_DIR / f"{project.id}.json"
        self._write_json(path, project.model_dump(mode="json"))
        logger.info("保存项目: id=%s, name=%s", project.id, project.name)
        return path

    def load_project(self, project_id: str) -> CreationProject:
        """加载创作项目.

        Args:
            project_id: 项目ID.

        Returns:
            创作项目对象.
        """
        path = PROJECT_STORAGE_DIR / f"{project_id}.json"
        data = self._read_json(path)
        return CreationProject.model_validate(data)

    def list_projects(self) -> list[CreationProject]:
        """列出全部创作项目.

        Returns:
            创作项目列表.
        """
        projects: list[CreationProject] = []
        for path in sorted(PROJECT_STORAGE_DIR.glob("*.json")):
            try:
                data = self._read_json(path)
                projects.append(CreationProject.model_validate(data))
            except Exception as e:
                logger.warning("加载项目失败 %s: %s", path.name, e)
        return projects

    def delete_project(self, project_id: str) -> bool:
        """删除创作项目及其关联快照.

        Args:
            project_id: 项目ID.

        Returns:
            是否成功删除.
        """
        # 删除JSON文件
        path = PROJECT_STORAGE_DIR / f"{project_id}.json"
        if path.exists():
            path.unlink()

        # 删除关联的锁定快照文件
        project_dir = PROJECT_STORAGE_DIR / project_id
        if project_dir.exists():
            shutil.rmtree(project_dir)

        logger.info("删除项目: id=%s", project_id)
        return True

    def save_locked_snapshot(self, project_id: str, step: str, content: str) -> Path:
        """保存锁定步骤的快照为Markdown文件.

        Args:
            project_id: 项目ID.
            step: 步骤名称.
            content: 锁定内容.

        Returns:
            保存的文件路径.
        """
        project_dir = PROJECT_STORAGE_DIR / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        path = project_dir / f"{step}.locked.md"
        self._write_markdown(path, content)
        logger.info("保存锁定快照: project=%s, step=%s", project_id, step)
        return path

    def load_locked_snapshot(self, project_id: str, step: str) -> str:
        """加载锁定步骤的快照.

        Args:
            project_id: 项目ID.
            step: 步骤名称.

        Returns:
            快照内容.
        """
        path = PROJECT_STORAGE_DIR / project_id / f"{step}.locked.md"
        if path.exists():
            return self._read_markdown(path)
        return ""

    # ============================ 反馈管理 ============================

    def save_feedback(self, feedback: FeedbackSample) -> Path:
        """保存反馈样本.

        Args:
            feedback: 反馈样本对象.

        Returns:
            保存的文件路径.
        """
        path = FEEDBACK_DIR / f"{feedback.id}.json"
        self._write_json(path, feedback.model_dump(mode="json"))
        logger.info("保存反馈: id=%s, type=%s", feedback.id, feedback.feedback_type.value)
        return path

    def load_feedback(self, feedback_id: str) -> FeedbackSample:
        """加载反馈样本.

        Args:
            feedback_id: 反馈ID.

        Returns:
            反馈样本对象.
        """
        path = FEEDBACK_DIR / f"{feedback_id}.json"
        data = self._read_json(path)
        return FeedbackSample.model_validate(data)

    def list_feedback_by_project(self, project_id: str) -> list[FeedbackSample]:
        """按项目ID列出全部反馈.

        Args:
            project_id: 项目ID.

        Returns:
            反馈样本列表.
        """
        samples: list[FeedbackSample] = []
        for path in sorted(FEEDBACK_DIR.glob("*.json")):
            try:
                data = self._read_json(path)
                if data.get("project_id") == project_id:
                    samples.append(FeedbackSample.model_validate(data))
            except Exception as e:
                logger.warning("加载反馈失败 %s: %s", path.name, e)
        return samples

    def delete_feedback(self, feedback_id: str) -> bool:
        """删除反馈样本.

        Args:
            feedback_id: 反馈ID.

        Returns:
            是否成功删除.
        """
        path = FEEDBACK_DIR / f"{feedback_id}.json"
        if path.exists():
            path.unlink()
            logger.info("删除反馈: id=%s", feedback_id)
            return True
        return False

    # ============================ 数据转换 ============================

    @staticmethod
    def to_markdown(rule_set: RuleSet) -> str:
        """将规则集转换为Markdown格式.

        Args:
            rule_set: 规则集对象.

        Returns:
            Markdown格式字符串.
        """
        lines: list[str] = [
            f"# {rule_set.name}",
            "",
            f"- 蒸馏模式: {rule_set.distill_mode.value}",
            f"- 创建时间: {rule_set.created_at}",
            f"- 来源素材数: {len(rule_set.source_material_ids)}",
            "",
            "## 规则列表",
            "",
        ]
        for dimension, rules in rule_set.rules.items():
            lines.append(f"### {dimension}")
            lines.append("")
            for i, rule in enumerate(rules, 1):
                lines.append(f"{i}. **{rule.content}** (权重: {rule.weight})")
                if rule.conflicting_rule_ids:
                    lines.append(f"   - 冲突规则: {', '.join(rule.conflicting_rule_ids)}")
                lines.append("")
        return "\n".join(lines)

    @staticmethod
    def skill_to_markdown(skill: Skill) -> str:
        """将Skill转换为Markdown格式.

        Args:
            skill: Skill对象.

        Returns:
            Markdown格式字符串.
        """
        lines: list[str] = [
            f"# Skill: {skill.name}",
            "",
            f"- 描述: {skill.description}",
            f"- 状态: {skill.status.value}",
            f"- 当前版本: {skill.current_version}",
            f"- 创建时间: {skill.created_at}",
            f"- 更新时间: {skill.updated_at}",
            "",
        ]
        for layer, rules in skill.layers.items():
            lines.append(f"## {layer}")
            lines.append("")
            for i, rule in enumerate(rules, 1):
                lines.append(
                    f"{i}. **[{rule.dimension.value}]** {rule.content} (权重: {rule.weight})"
                )
            lines.append("")
        return "\n".join(lines)
