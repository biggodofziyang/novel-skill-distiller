"""反馈迭代引擎.

提供正负样本管理、微迭代权重调整和版本迭代修订草案生成功能.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from core.constants import (
    MICRO_ITERATION_WEIGHT_DELTA,
    FeedbackType,
)
from core.models import CreationProject, FeedbackSample, Skill, SkillRule
from core.storage import StorageManager
from services.llm_client import LLMClient
from services.skill_manager import SkillManager
from utils.logger import get_logger

logger = get_logger(__name__)


class FeedbackEngine:
    """反馈迭代引擎.

    收集用户反馈样本，触发微迭代（权重调整）或版本迭代（规则修订）.
    """

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        storage: StorageManager | None = None,
        skill_manager: SkillManager | None = None,
    ) -> None:
        """初始化反馈引擎.

        Args:
            llm_client: LLM客户端实例.
            storage: 存储管理器实例.
            skill_manager: Skill管理器实例.
        """
        self._llm = llm_client or LLMClient()
        self._storage = storage or StorageManager()
        self._skill_mgr = skill_manager or SkillManager(self._storage)

    def add_sample(
        self,
        project_id: str,
        feedback_type: FeedbackType,
        category: str,
        content: str,
        related_rule_ids: list[str] | None = None,
        suggested_weight_delta: int = 0,
    ) -> FeedbackSample:
        """添加反馈样本.

        Args:
            project_id: 关联项目ID.
            feedback_type: 反馈类型（正/负）.
            category: 问题分类.
            content: 反馈内容.
            related_rule_ids: 关联规则ID列表.
            suggested_weight_delta: 建议权重调整值.

        Returns:
            创建的反馈样本对象.
        """
        sample = FeedbackSample(
            project_id=project_id,
            feedback_type=feedback_type,
            category=category,
            content=content,
            related_rule_ids=related_rule_ids or [],
            suggested_weight_delta=suggested_weight_delta,
        )
        self._storage.save_feedback(sample)
        logger.info(
            "添加反馈样本: project=%s, type=%s, category=%s",
            project_id, feedback_type.value, category,
        )
        return sample

    def trigger_micro_iteration(
        self,
        skill: Skill,
        feedback_samples: list[FeedbackSample],
    ) -> Skill:
        """触发微迭代（权重调整）.

        根据反馈样本对关联规则的权重进行微调（±5）.

        Args:
            skill: 目标Skill.
            feedback_samples: 反馈样本列表.

        Returns:
            调整后的Skill.
        """
        delta = MICRO_ITERATION_WEIGHT_DELTA
        adjusted_count = 0

        for sample in feedback_samples:
            if not sample.related_rule_ids:
                continue

            for rule_id in sample.related_rule_ids:
                # 确定调整方向
                if sample.feedback_type == FeedbackType.POSITIVE:
                    weight_delta = delta
                else:
                    weight_delta = -delta

                # 如果用户有明确建议，优先使用
                if sample.suggested_weight_delta != 0:
                    weight_delta = sample.suggested_weight_delta

                # 查找并调整规则
                for layer_rules in skill.layers.values():
                    for rule in layer_rules:
                        if rule.id == rule_id:
                            old_weight = rule.weight
                            rule.weight = max(0, min(100, rule.weight + weight_delta))
                            if rule.weight != old_weight:
                                adjusted_count += 1
                                logger.info(
                                    "微迭代调整: rule=%s, %d -> %d",
                                    rule_id, old_weight, rule.weight,
                                )
                            break

        skill.updated_at = datetime.now()
        logger.info("微迭代完成: adjusted_rules=%d", adjusted_count)
        return skill

    def trigger_version_iteration(
        self,
        skill: Skill,
        feedback_samples: list[FeedbackSample],
    ) -> dict[str, Any]:
        """触发版本迭代（生成修订草案）.

        使用LLM基于反馈样本生成Skill规则修订建议.

        Args:
            skill: 目标Skill.
            feedback_samples: 反馈样本列表.

        Returns:
            包含修订草案和元信息的字典.
        """
        # 构建反馈摘要
        positive_samples = [s for s in feedback_samples if s.feedback_type == FeedbackType.POSITIVE]
        negative_samples = [s for s in feedback_samples if s.feedback_type == FeedbackType.NEGATIVE]

        # 构建当前规则摘要
        rules_summary = self._build_rules_summary(skill)

        # 构建LLM提示词
        prompt = self._build_iteration_prompt(
            rules_summary, positive_samples, negative_samples,
        )
        request = LLMRequest(prompt=prompt, temperature=0.6, max_tokens=4000)

        logger.info("触发版本迭代: skill=%s, feedback=%d", skill.name, len(feedback_samples))
        response = self._llm.chat(request, use_cache=False)

        if not response.success:
            logger.error("版本迭代失败: %s", response.error_message)
            return {
                "success": False,
                "error": response.error_message,
                "draft": "",
            }

        draft = response.content.strip()

        # 解析修订建议为结构化格式
        suggestions = self._parse_revision_suggestions(draft)

        result = {
            "success": True,
            "draft": draft,
            "suggestions": suggestions,
            "feedback_summary": {
                "positive": len(positive_samples),
                "negative": len(negative_samples),
            },
        }

        logger.info("版本迭代草案生成完成: suggestions=%d", len(suggestions))
        return result

    def apply_iteration_draft(
        self,
        skill: Skill,
        suggestions: list[dict[str, Any]],
        changelog: str = "",
    ) -> Skill:
        """应用版本迭代修订草案到Skill.

        Args:
            skill: 目标Skill.
            suggestions: 修订建议列表.
            changelog: 变更说明.

        Returns:
            更新后的Skill.
        """
        for suggestion in suggestions:
            action = suggestion.get("action", "")
            rule_content = suggestion.get("content", "")
            dimension = suggestion.get("dimension", "")
            weight = suggestion.get("weight", 50)

            if action == "add":
                # 添加新规则
                from core.constants import AnalysisDimension
                try:
                    dim_enum = AnalysisDimension(dimension)
                except ValueError:
                    dim_enum = AnalysisDimension.OTHER if hasattr(AnalysisDimension, 'OTHER') else list(AnalysisDimension)[0]

                layer = self._get_layer_for_dimension(dim_enum)
                new_rule = SkillRule(
                    layer=layer,
                    dimension=dim_enum,
                    content=rule_content,
                    weight=weight,
                )
                skill.layers[layer.value].append(new_rule)

            elif action == "remove":
                # 移除规则
                for rules in skill.layers.values():
                    for rule in rules:
                        if rule.content == rule_content:
                            rules.remove(rule)
                            break

            elif action == "modify":
                # 修改规则权重或内容
                for rules in skill.layers.values():
                    for rule in rules:
                        if rule.content == rule_content:
                            rule.weight = weight
                            if "new_content" in suggestion:
                                rule.content = suggestion["new_content"]
                            break

        # 升级版本
        skill = self._skill_mgr.bump_version(skill, changelog or "基于反馈迭代修订")
        self._skill_mgr.save_skill(skill)

        logger.info("应用迭代草案完成: skill=%s", skill.name)
        return skill

    def list_feedback(self, project_id: str) -> list[FeedbackSample]:
        """列出项目的全部反馈.

        Args:
            project_id: 项目ID.

        Returns:
            反馈样本列表.
        """
        return self._storage.list_feedback_by_project(project_id)

    def _build_rules_summary(self, skill: Skill) -> str:
        """构建Skill规则摘要文本.

        Args:
            skill: Skill对象.

        Returns:
            规则摘要文本.
        """
        lines: list[str] = [f"Skill: {skill.name}", ""]
        for layer_name, rules in skill.layers.items():
            if rules:
                lines.append(f"## {layer_name}")
                for rule in rules:
                    lines.append(f"- [{rule.dimension.value}] {rule.content} (权重:{rule.weight})")
                lines.append("")
        return "\n".join(lines)

    def _build_iteration_prompt(
        self,
        rules_summary: str,
        positive_samples: list[FeedbackSample],
        negative_samples: list[FeedbackSample],
    ) -> str:
        """构建版本迭代的LLM提示词.

        Args:
            rules_summary: 规则摘要.
            positive_samples: 正样本列表.
            negative_samples: 负样本列表.

        Returns:
            提示词文本.
        """
        lines: list[str] = [
            "你是一位网文Skill优化专家。请根据以下用户反馈，对现有写作规则进行修订。",
            "",
            "## 当前规则",
            rules_summary,
            "",
        ]

        if positive_samples:
            lines.append("## 正面反馈（读者喜欢的点）")
            for i, sample in enumerate(positive_samples, 1):
                lines.append(f"{i}. [{sample.category}] {sample.content}")
            lines.append("")

        if negative_samples:
            lines.append("## 负面反馈（需要改进的点）")
            for i, sample in enumerate(negative_samples, 1):
                lines.append(f"{i}. [{sample.category}] {sample.content}")
            lines.append("")

        lines.extend([
            "## 修订要求",
            "1. 保留被正面反馈验证有效的规则",
            "2. 针对负面反馈，提出具体规则修改或新增",
            "3. 可以删除被多次负面反馈针对的规则",
            "4. 每条修订建议需说明理由",
            "",
            "输出格式：",
            "- 对每个需要修改的规则，说明：action(add/modify/remove), dimension, content, weight, reason",
            "- 先输出修订说明，再输出修订后的完整规则列表",
        ])

        return "\n".join(lines)

    def _parse_revision_suggestions(self, draft: str) -> list[dict[str, Any]]:
        """解析LLM生成的修订草案为结构化建议.

        简单实现：从文本中提取带action标记的行.

        Args:
            draft: LLM生成的草案文本.

        Returns:
            结构化建议列表.
        """
        suggestions: list[dict[str, Any]] = []
        import re

        # 匹配 action: xxx, dimension: xxx, content: xxx, weight: xxx 格式
        pattern = re.compile(
            r'action[\s:"]*(add|modify|remove)[\s,"]*'
            r'(?:dimension[\s:"]*([^,"\n]+)[\s,"]*)?'
            r'(?:content[\s:"]*([^,"\n]+)[\s,"]*)?'
            r'(?:weight[\s:"]*(\d+)[\s,"]*)?',
            re.IGNORECASE,
        )

        for match in pattern.finditer(draft):
            suggestions.append({
                "action": match.group(1).lower(),
                "dimension": (match.group(2) or "").strip(),
                "content": (match.group(3) or "").strip(),
                "weight": int(match.group(4)) if match.group(4) else 50,
            })

        return suggestions

    @staticmethod
    def _get_layer_for_dimension(dimension: Any) -> Any:
        """根据维度获取对应层级.

        Args:
            dimension: 分析维度.

        Returns:
            Skill层级.
        """
        from core.constants import SkillLayer
        mapping = {
            "世界观": SkillLayer.BASE,
            "人设": SkillLayer.MIDDLE,
        }
        return mapping.get(dimension.value, SkillLayer.MIDDLE)
