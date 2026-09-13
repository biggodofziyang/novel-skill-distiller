"""分步创作引擎.

提供分步锁稿创作功能，支持实时规则校验和步骤快照保存.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from core.constants import CreationStep
from core.models import CreationProject, LLMRequest, Skill, SkillRule
from core.storage import StorageManager
from services.llm_client import LLMClient
from utils.logger import get_logger

logger = get_logger(__name__)

PROMPT_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "config" / "prompt_templates"


class CreationEngine:
    """分步创作引擎.

    支持三步创作流程（世界观->人设->前三章），
    每步可锁稿并基于已锁定内容继续创作.
    """

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        storage: StorageManager | None = None,
    ) -> None:
        """初始化创作引擎.

        Args:
            llm_client: LLM客户端实例.
            storage: 存储管理器实例.
        """
        self._llm = llm_client or LLMClient()
        self._storage = storage or StorageManager()

    def create_project(self, name: str, skill_id: str) -> CreationProject:
        """创建新的创作项目.

        Args:
            name: 项目名称.
            skill_id: 使用的Skill ID.

        Returns:
            创建的项目对象.
        """
        project = CreationProject(name=name, skill_id=skill_id)
        self._storage.save_project(project)
        logger.info("创建创作项目: id=%s, name=%s", project.id, name)
        return project

    def generate_step(
        self,
        project: CreationProject,
        skill: Skill,
        step: CreationStep,
        user_prompt: str = "",
    ) -> str:
        """生成指定步骤的内容.

        自动注入已锁定的前置步骤内容和Skill规则.

        Args:
            project: 创作项目.
            skill: 使用的Skill.
            step: 当前创作步骤.
            user_prompt: 用户的额外提示/要求.

        Returns:
            生成的内容.
        """
        if not self._can_enter_step(project, step):
            raise ValueError("请先完成并锁定前置步骤，再进入下一步创作。")

        # 构建提示词
        prompt = self._build_creation_prompt(project, skill, step, user_prompt)
        request = LLMRequest(
            prompt=prompt,
            temperature=0.75,
            max_tokens=6000,
        )

        logger.info("生成创作内容: project=%s, step=%s", project.id, step.value)
        response = self._llm.chat(request, use_cache=False)

        if not response.success:
            logger.error("创作生成失败: %s", response.error_message)
            return f"生成失败: {response.error_message}"

        content = response.content.strip()
        # 保存到项目
        project.step_contents[step.value] = content
        project.current_step = step
        project.updated_at = datetime.now()
        self._storage.save_project(project)

        return content

    def validate_content(
        self,
        content: str,
        skill: Skill,
        step: CreationStep,
    ) -> dict[str, Any]:
        """校验内容是否符合Skill规则.

        重点检查避雷规则，同时验证当前步骤相关规则.

        Args:
            content: 待校验内容.
            skill: 使用的Skill.
            step: 当前步骤.

        Returns:
            校验报告字典.
        """
        violations: list[dict] = []
        warnings: list[dict] = []

        rules = self._get_relevant_rules(skill, step)

        for rule in rules:
            # 简单关键词匹配作为本地预筛
            if rule.dimension.value == "避雷":
                # 避雷规则：检查是否出现规则中提到的负面模式
                check_result = self._check_pitfall_rule(content, rule)
                if check_result["violated"]:
                    violations.append({
                        "rule_id": rule.id,
                        "dimension": rule.dimension.value,
                        "content": rule.content,
                        "message": check_result["message"],
                    })
            else:
                # 其他规则：使用LLM进行语义校验（仅对高权重规则）
                if rule.weight >= 70:
                    check_result = self._llm_validate_rule(content, rule)
                    if check_result["violated"]:
                        violations.append({
                            "rule_id": rule.id,
                            "dimension": rule.dimension.value,
                            "content": rule.content,
                            "message": check_result["message"],
                        })
                    elif check_result["warning"]:
                        warnings.append({
                            "rule_id": rule.id,
                            "dimension": rule.dimension.value,
                            "content": rule.content,
                            "message": check_result["message"],
                        })

        score = max(0, 100 - len(violations) * 15 - len(warnings) * 5)

        report = {
            "score": score,
            "total_rules_checked": len(rules),
            "violations": violations,
            "warnings": warnings,
            "passed": len(violations) == 0,
        }

        logger.info(
            "内容校验完成: score=%d, violations=%d, warnings=%d",
            score, len(violations), len(warnings),
        )
        return report

    def lock_step(self, project: CreationProject, step: CreationStep) -> CreationProject:
        """锁定步骤并保存快照.

        锁定后该步骤内容不可修改，后续步骤基于此内容创作.

        Args:
            project: 创作项目.
            step: 要锁定的步骤.

        Returns:
            更新后的项目对象.
        """
        if not self._can_enter_step(project, step):
            raise ValueError("前置步骤尚未锁定，不能锁定当前步骤。")

        content = project.step_contents.get(step.value, "").strip()
        if not content:
            raise ValueError("当前步骤没有内容，不能锁定。")

        # 保存Markdown快照
        snapshot_path = self._storage.save_locked_snapshot(
            project_id=project.id,
            step=step.value,
            content=content,
        )

        if step.value not in project.locked_steps:
            project.locked_steps.append(step.value)
        project.locked_snapshots[step.value] = str(snapshot_path)
        project.updated_at = datetime.now()

        self._storage.save_project(project)
        logger.info("步骤已锁定: project=%s, step=%s", project.id, step.value)
        return project

    def _build_creation_prompt(
        self,
        project: CreationProject,
        skill: Skill,
        step: CreationStep,
        user_prompt: str,
    ) -> str:
        """构建创作提示词.

        注入Skill规则、已锁定步骤内容和用户要求.

        Args:
            project: 创作项目.
            skill: 使用的Skill.
            step: 当前步骤.
            user_prompt: 用户额外提示.

        Returns:
            完整提示词.
        """
        lines: list[str] = [
            f"你是一位专业网文作家，正在创作一部新小说。当前步骤：{step.value}。",
            "",
            "## 创作规则（必须遵守）",
            "",
        ]

        # 注入相关规则
        rules = self._get_relevant_rules(skill, step)
        for rule in rules:
            priority = "【高】" if rule.weight >= 70 else "【中】" if rule.weight >= 40 else "【低】"
            lines.append(f"{priority} [{rule.dimension.value}] {rule.content}")
        lines.append("")

        # 注入已锁定的前置步骤内容
        locked_content = self._get_locked_content(project, step)
        if locked_content:
            lines.append("## 已确定的前置内容（不可修改，必须保持一致）")
            lines.append("")
            lines.append(locked_content)
            lines.append("")

        # 当前步骤要求
        lines.append(f"## 当前任务：{step.value}")
        lines.append("")
        if step == CreationStep.WORLD_BUILDING:
            lines.append("请详细构建小说的世界观设定，包括：")
            lines.append("- 世界背景与时代设定")
            lines.append("- 力量/等级体系")
            lines.append("- 主要势力与地理")
            lines.append("- 核心规则与限制")
        elif step == CreationStep.CHARACTER:
            lines.append("请设计主要人物设定，包括：")
            lines.append("- 主角：姓名、性格、外貌、背景、核心动机")
            lines.append("- 重要配角：与主角的关系、功能定位")
            lines.append("- 人物关系图")
        elif step == CreationStep.FIRST_THREE_CHAPTERS:
            lines.append("请创作小说前三章正文，要求：")
            lines.append("- 第一章：开篇引入，建立期待感，埋下伏笔")
            lines.append("- 第二章：冲突升级，展示世界观，刻画人物")
            lines.append("- 第三章：第一个小高潮，留下钩子")
        lines.append("")

        if user_prompt:
            lines.append("## 额外要求")
            lines.append(user_prompt)
            lines.append("")

        lines.append("请直接输出创作内容，不要输出分析或说明文字。")

        return "\n".join(lines)

    def _get_relevant_rules(self, skill: Skill, step: CreationStep) -> list[SkillRule]:
        """获取与当前步骤相关的规则.

        Args:
            skill: Skill对象.
            step: 当前步骤.

        Returns:
            相关规则列表.
        """
        all_rules = []
        for rules in skill.layers.values():
            all_rules.extend(rules)

        # 根据步骤筛选高相关度规则
        relevant: list[SkillRule] = []
        step_value = step.value

        for rule in all_rules:
            # 避雷规则始终相关
            if rule.dimension.value == "避雷":
                relevant.append(rule)
                continue
            # 世界观步骤：世界观、设定相关规则
            if step_value == "世界观" and rule.dimension.value in ("世界观", "剧情架构"):
                relevant.append(rule)
            # 人设步骤：人设、文笔相关规则
            elif step_value == "人设" and rule.dimension.value in ("人设", "文笔话术"):
                relevant.append(rule)
            # 前三章：节奏、悬念、爽点、文笔、剧情
            elif step_value == "前三章" and rule.dimension.value in (
                "节奏", "悬念", "剧情架构", "文笔话术", "爽点",
            ):
                relevant.append(rule)

        # 如果筛选后太少，补充高权重规则
        if len(relevant) < 5:
            for rule in all_rules:
                if rule not in relevant and rule.weight >= 60:
                    relevant.append(rule)

        # 按权重降序排列
        relevant.sort(key=lambda r: r.weight, reverse=True)
        return relevant[:30]  # 最多30条规则

    def _get_locked_content(self, project: CreationProject, current_step: CreationStep) -> str:
        """获取当前步骤之前已锁定步骤的内容.

        Args:
            project: 创作项目.
            current_step: 当前步骤.

        Returns:
            已锁定内容的拼接文本.
        """
        step_order = ["世界观", "人设", "前三章"]
        current_index = step_order.index(current_step.value)

        parts: list[str] = []
        for i in range(current_index):
            step_name = step_order[i]
            if step_name in project.locked_steps:
                content = self._storage.load_locked_snapshot(project.id, step_name)
                if content:
                    parts.append(f"### {step_name}\n{content}")

        return "\n\n".join(parts)

    @staticmethod
    def _can_enter_step(project: CreationProject, step: CreationStep) -> bool:
        """确认当前步骤前的内容均已锁定。"""
        step_order = [item.value for item in CreationStep]
        current_index = step_order.index(step.value)
        return all(previous in project.locked_steps for previous in step_order[:current_index])

    def _check_pitfall_rule(self, content: str, rule: SkillRule) -> dict[str, Any]:
        """本地检查避雷规则.

        通过关键词匹配进行快速预筛.

        Args:
            content: 待检查内容.
            rule: 避雷规则.

        Returns:
            检查结果字典.
        """
        rule_text = rule.content.lower()
        # 提取规则中的关键禁止词
        # 简单实现：如果规则中包含的负面词汇在内容中出现
        result = {"violated": False, "message": ""}

        # 常见负面模式关键词
        negative_indicators = ["避免", "不要", "切忌", "禁止", "不可", "不能", "请勿"]
        has_negative = any(ind in rule_text for ind in negative_indicators)

        if has_negative:
            # 提取规则中禁止的具体行为（简单截取规则后半部分）
            for ind in negative_indicators:
                if ind in rule.content:
                    forbidden = rule.content.split(ind, 1)[-1].strip()
                    if len(forbidden) > 3 and forbidden in content:
                        result["violated"] = True
                        result["message"] = f"内容可能违反避雷规则: {rule.content}"
                        break

        return result

    def _llm_validate_rule(self, content: str, rule: SkillRule) -> dict[str, Any]:
        """使用LLM校验单条规则.

        Args:
            content: 待校验内容.
            rule: 规则对象.

        Returns:
            校验结果字典.
        """
        prompt = (
            f"请判断以下网文内容是否遵守了这条写作规则。\n\n"
            f"规则: [{rule.dimension.value}] {rule.content}\n\n"
            f"内容片段:\n{content[:2000]}...\n\n"
            "如果内容明显违反该规则，请回复\"VIOLATED: 原因\"。"
            "如果内容基本遵守但有改进空间，请回复\"WARNING: 建议\"。"
            "如果内容完全遵守，请回复\"PASS\"。"
            "只输出这三个格式之一，不要其他内容。"
        )
        request = LLMRequest(prompt=prompt, temperature=0.1, max_tokens=100)
        response = self._llm.chat(request, use_cache=False)

        result = {"violated": False, "warning": False, "message": ""}

        if response.success:
            text = response.content.strip().upper()
            if text.startswith("VIOLATED"):
                result["violated"] = True
                result["message"] = response.content.strip()
            elif text.startswith("WARNING"):
                result["warning"] = True
                result["message"] = response.content.strip()

        return result

    def save_project(self, project: CreationProject) -> None:
        """保存创作项目.

        Args:
            project: 项目对象.
        """
        self._storage.save_project(project)

    def load_project(self, project_id: str) -> CreationProject:
        """加载创作项目.

        Args:
            project_id: 项目ID.

        Returns:
            项目对象.
        """
        return self._storage.load_project(project_id)
