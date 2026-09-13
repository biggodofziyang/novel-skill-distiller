"""Skill管理器.

提供Skill的创建、组合加权、版本化管理和生效规则提取功能.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from core.constants import (
    MAX_SKILL_VERSIONS,
    SkillLayer,
    SkillStatus,
)
from core.models import (
    Rule,
    RuleSet,
    Skill,
    SkillRule,
    SkillVersion,
)
from core.storage import StorageManager
from utils.logger import get_logger

logger = get_logger(__name__)

# 维度到Skill层级的映射
DIMENSION_TO_LAYER: dict[str, SkillLayer] = {
    "世界观": SkillLayer.BASE,
    "人设": SkillLayer.MIDDLE,
    "节奏": SkillLayer.MIDDLE,
    "悬念": SkillLayer.MIDDLE,
    "剧情架构": SkillLayer.MIDDLE,
    "文笔话术": SkillLayer.MIDDLE,
    "爽点": SkillLayer.MIDDLE,
    "避雷": SkillLayer.MIDDLE,
}


class SkillManager:
    """Skill管理器.

    负责Skill的生命周期管理，包括创建、组合、版本控制和规则提取.
    """

    def __init__(self, storage: StorageManager | None = None) -> None:
        """初始化Skill管理器.

        Args:
            storage: 存储管理器实例.
        """
        self._storage = storage or StorageManager()

    def create_skill(
        self,
        rule_set: RuleSet,
        name: str,
        description: str = "",
    ) -> Skill:
        """从规则集创建Skill.

        根据维度自动将规则分配到对应层级.

        Args:
            rule_set: 规则集.
            name: Skill名称.
            description: Skill描述.

        Returns:
            创建的Skill对象.
        """
        skill = Skill(name=name, description=description)

        for dimension, rules in rule_set.rules.items():
            layer = DIMENSION_TO_LAYER.get(dimension, SkillLayer.MIDDLE)
            for rule in rules:
                skill_rule = SkillRule(
                    layer=layer,
                    dimension=rule.dimension,
                    content=rule.content,
                    weight=rule.weight,
                    source_rule_ids=[rule.id],
                )
                skill.layers[layer.value].append(skill_rule)

        # 创建初始版本
        version = self._create_version(skill, "初始版本")
        skill.versions.append(version)
        skill.current_version = version.version

        logger.info("创建Skill: name=%s, rules=%d", name, sum(len(r) for r in skill.layers.values()))
        return skill

    def combine_skills(
        self,
        skills: list[Skill],
        weights: list[float] | None = None,
        name: str = "组合Skill",
        description: str = "",
    ) -> Skill:
        """加权组合多个Skill.

        Args:
            skills: 待组合的Skill列表.
            weights: 各Skill的权重列表，未提供时平均分配.
            name: 新Skill名称.
            description: 新Skill描述.

        Returns:
            组合后的新Skill.
        """
        if not skills:
            raise ValueError("至少需要提供一个Skill")

        if weights is None:
            weights = [1.0 / len(skills)] * len(skills)
        if len(weights) != len(skills):
            raise ValueError("权重数量与Skill数量不匹配")

        if any(weight < 0 for weight in weights) or sum(weights) <= 0:
            raise ValueError("Skill权重必须为非负数，且总和大于0")
        normalized_weights = [weight / sum(weights) for weight in weights]

        combined = Skill(name=name, description=description)
        rule_map: dict[str, tuple[SkillRule, float, float]] = {}

        for skill, weight in zip(skills, normalized_weights):
            for layer_rules in skill.layers.values():
                for rule in layer_rules:
                    key = f"{rule.dimension.value}:{rule.content}"
                    if key in rule_map:
                        existing, weighted_sum, contributing_weight = rule_map[key]
                        existing.source_rule_ids.extend(rule.source_rule_ids)
                        rule_map[key] = (
                            existing,
                            weighted_sum + rule.weight * weight,
                            contributing_weight + weight,
                        )
                    else:
                        new_rule = SkillRule(
                            layer=rule.layer,
                            dimension=rule.dimension,
                            content=rule.content,
                            weight=rule.weight,
                            source_rule_ids=list(rule.source_rule_ids),
                        )
                        rule_map[key] = (new_rule, rule.weight * weight, weight)

        # 同一规则只在实际包含它的 Skill 之间计算加权平均。
        for rule, weighted_sum, contributing_weight in rule_map.values():
            rule.weight = round(weighted_sum / contributing_weight)
            combined.layers[rule.layer.value].append(rule)

        # 创建初始版本
        version = self._create_version(combined, f"组合{len(skills)}个Skill")
        combined.versions.append(version)
        combined.current_version = version.version

        logger.info("组合Skill: name=%s, source_skills=%d", name, len(skills))
        return combined

    def bump_version(self, skill: Skill, changelog: str = "") -> Skill:
        """升级Skill版本.

        保存当前规则状态为新版本，并更新当前版本号.

        Args:
            skill: Skill对象.
            changelog: 版本变更说明.

        Returns:
            更新后的Skill对象.
        """
        new_version_str = self._increment_version(skill.current_version)
        version = SkillVersion(
            version=new_version_str,
            rules_snapshot={k: list(v) for k, v in skill.layers.items()},
            changelog=changelog or f"版本升级至 {new_version_str}",
        )
        skill.versions.append(version)
        skill.current_version = new_version_str

        # 限制版本历史数量
        if len(skill.versions) > MAX_SKILL_VERSIONS:
            skill.versions = skill.versions[-MAX_SKILL_VERSIONS:]

        logger.info("Skill版本升级: skill=%s, version=%s", skill.name, new_version_str)
        return skill

    def rollback_version(self, skill: Skill, version_str: str) -> Skill:
        """回滚到指定版本.

        Args:
            skill: Skill对象.
            version_str: 目标版本号.

        Returns:
            回滚后的Skill对象.

        Raises:
            ValueError: 当版本不存在时.
        """
        target_version: SkillVersion | None = None
        for v in skill.versions:
            if v.version == version_str:
                target_version = v
                break

        if target_version is None:
            raise ValueError(f"版本 {version_str} 不存在")

        # 恢复规则快照
        skill.layers = {k: list(v) for k, v in target_version.rules_snapshot.items()}
        skill.current_version = version_str
        skill.updated_at = datetime.now()

        logger.info("Skill版本回滚: skill=%s, version=%s", skill.name, version_str)
        return skill

    def get_effective_rules(self, skill: Skill, layer: SkillLayer | None = None) -> list[SkillRule]:
        """获取当前生效的规则列表.

        Args:
            skill: Skill对象.
            layer: 指定层级，None时返回全部层级.

        Returns:
            生效规则列表.
        """
        if layer:
            return list(skill.layers.get(layer.value, []))
        all_rules: list[SkillRule] = []
        for rules in skill.layers.values():
            all_rules.extend(rules)
        return all_rules

    def update_rule_weight(self, skill: Skill, rule_id: str, delta: int) -> Skill:
        """调整单条规则的权重.

        Args:
            skill: Skill对象.
            rule_id: 规则ID.
            delta: 权重调整值（可为负）.

        Returns:
            更新后的Skill对象.
        """
        for rules in skill.layers.values():
            for rule in rules:
                if rule.id == rule_id:
                    new_weight = rule.weight + delta
                    rule.weight = max(0, min(100, new_weight))
                    skill.updated_at = datetime.now()
                    logger.info(
                        "规则权重调整: skill=%s, rule=%s, weight=%d",
                        skill.name, rule_id, rule.weight,
                    )
                    return skill
        logger.warning("规则未找到: skill=%s, rule_id=%s", skill.name, rule_id)
        return skill

    def save_skill(self, skill: Skill) -> None:
        """持久化Skill到存储.

        Args:
            skill: Skill对象.
        """
        self._storage.save_skill(skill)
        logger.info("Skill已保存: id=%s", skill.id)

    def load_skill(self, skill_id: str) -> Skill:
        """从存储加载Skill.

        Args:
            skill_id: Skill ID.

        Returns:
            Skill对象.
        """
        return self._storage.load_skill(skill_id)

    def list_skills(self) -> list[Skill]:
        """列出全部Skill.

        Returns:
            Skill列表.
        """
        return self._storage.list_skills()

    @staticmethod
    def _create_version(skill: Skill, changelog: str) -> SkillVersion:
        """创建版本快照.

        Args:
            skill: Skill对象.
            changelog: 变更说明.

        Returns:
            版本快照对象.
        """
        return SkillVersion(
            version=skill.current_version,
            rules_snapshot={k: list(v) for k, v in skill.layers.items()},
            changelog=changelog,
        )

    @staticmethod
    def _increment_version(version: str) -> str:
        """递增版本号（简单的主.次.修格式）.

        Args:
            version: 当前版本号.

        Returns:
            递增后的版本号.
        """
        parts = version.split(".")
        try:
            if len(parts) >= 3:
                major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
                patch += 1
                if patch >= 100:
                    patch = 0
                    minor += 1
                if minor >= 100:
                    minor = 0
                    major += 1
                return f"{major}.{minor}.{patch}"
            if len(parts) == 2:
                major, minor = int(parts[0]), int(parts[1])
                minor += 1
                return f"{major}.{minor}.0"
            major = int(parts[0])
            return f"{major}.0.1"
        except ValueError:
            return "1.0.0"
