"""规则蒸馏引擎.

提供全量/增量/定向三种蒸馏模式，支持规则去重、冲突检测和空话过滤.
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path
from typing import Any

from core.constants import (
    CONFLICT_DETECTION_THRESHOLD,
    DistillMode,
    RULE_SIMILARITY_THRESHOLD,
)
from core.models import (
    AnalysisFile,
    AnalysisRule,
    LLMRequest,
    Rule,
    RuleSet,
)
from services.llm_client import LLMClient
from utils.logger import get_logger

logger = get_logger(__name__)

PROMPT_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "config" / "prompt_templates"

# 空话/无效规则关键词模式
EMPTY_RULE_PATTERNS = [
    r"^[^\u4e00-\u9fa5a-zA-Z0-9]*$",  # 无实质内容
    r"^(很好|不错|可以|应该|需要|注意).{0,5}$",  # 过于笼统
    r"^[认真努力仔细尽量]*.{0,3}[地得].{0,5}$",  # 副词开头过短
]


class Distiller:
    """规则蒸馏器.

    将拆解结果（AnalysisFile）蒸馏为结构化的规则集（RuleSet），
    支持去重、冲突检测和无效规则过滤.
    """

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        """初始化蒸馏器.

        Args:
            llm_client: LLM客户端实例.
        """
        self._llm = llm_client or LLMClient()
        self._empty_patterns = [re.compile(p) for p in EMPTY_RULE_PATTERNS]

    def distill(
        self,
        analysis_files: list[AnalysisFile],
        mode: DistillMode = DistillMode.FULL,
        existing_rule_set: RuleSet | None = None,
        target_dimensions: list[str] | None = None,
        name: str = "规则集",
    ) -> RuleSet:
        """执行规则蒸馏.

        Args:
            analysis_files: 拆解结果列表.
            mode: 蒸馏模式（全量/增量/定向）.
            existing_rule_set: 增量模式时的现有规则集.
            target_dimensions: 定向模式时目标维度列表.
            name: 产出规则集名称.

        Returns:
            蒸馏后的规则集.
        """
        logger.info("开始规则蒸馏: mode=%s, files=%d", mode.value, len(analysis_files))

        # 阶段1: 提取原始规则
        raw_rules = self._extract_raw_rules(analysis_files, target_dimensions)
        logger.info("提取原始规则: %d条", len(raw_rules))

        # 阶段2: 过滤空话/无效规则
        filtered_rules = self._filter_empty_rules(raw_rules)
        logger.info("过滤后规则: %d条", len(filtered_rules))

        # 阶段3: 去重合并
        merged_rules = self._merge_rules(filtered_rules)
        logger.info("去重后规则: %d条", len(merged_rules))

        # 阶段4: 冲突检测
        conflict_report = self.detect_conflicts(merged_rules)
        logger.info("冲突检测完成: 冲突组=%d", len(conflict_report.get("conflict_groups", [])))

        # 阶段5: 根据模式处理
        if mode == DistillMode.INCREMENTAL and existing_rule_set:
            final_rules = self._merge_with_existing(merged_rules, existing_rule_set)
            source_ids = list(set(existing_rule_set.source_material_ids + [
                af.material_id for af in analysis_files
            ]))
        else:
            final_rules = merged_rules
            source_ids = list(set(af.material_id for af in analysis_files))

        # 按维度分组
        rules_by_dimension: dict[str, list[Rule]] = {}
        for rule in final_rules:
            dim = rule.dimension.value
            if dim not in rules_by_dimension:
                rules_by_dimension[dim] = []
            rules_by_dimension[dim].append(rule)

        rule_set = RuleSet(
            name=name,
            distill_mode=mode,
            source_material_ids=source_ids,
            rules=rules_by_dimension,
            conflict_report=conflict_report,
        )

        logger.info("规则蒸馏完成: name=%s, total_rules=%d", name, len(final_rules))
        return rule_set

    def _extract_raw_rules(
        self,
        analysis_files: list[AnalysisFile],
        target_dimensions: list[str] | None,
    ) -> list[Rule]:
        """从拆解结果中提取原始规则.

        Args:
            analysis_files: 拆解结果列表.
            target_dimensions: 定向维度过滤.

        Returns:
            规则列表.
        """
        rules: list[Rule] = []
        target_set = set(target_dimensions) if target_dimensions else None

        for af in analysis_files:
            if target_set and af.dimension.value not in target_set:
                continue
            for ar in af.rules:
                rules.append(
                    Rule(
                        dimension=af.dimension,
                        content=ar.content,
                        weight=ar.weight,
                        source_material_ids=[af.material_id] if af.material_id else [],
                    )
                )
        return rules

    def _filter_empty_rules(self, rules: list[Rule]) -> list[Rule]:
        """过滤空话和无效规则.

        Args:
            rules: 原始规则列表.

        Returns:
            过滤后的规则列表.
        """
        valid_rules: list[Rule] = []
        for rule in rules:
            content = rule.content.strip()
            # 长度检查
            if len(content) < 8:
                rule.is_empty = True
                continue
            # 正则模式检查
            is_empty = False
            for pattern in self._empty_patterns:
                if pattern.match(content):
                    is_empty = True
                    break
            if is_empty:
                rule.is_empty = True
                continue
            valid_rules.append(rule)
        return valid_rules

    def _merge_rules(self, rules: list[Rule]) -> list[Rule]:
        """合并重复规则.

        使用文本相似度进行去重，相似度超过阈值的规则合并为一条，
        权重取平均值，来源合并.

        Args:
            rules: 规则列表.

        Returns:
            去重后的规则列表.
        """
        if not rules:
            return []

        merged: list[Rule] = []
        for rule in rules:
            found_duplicate = False
            for existing in merged:
                similarity = self._calculate_similarity(rule.content, existing.content)
                if similarity >= RULE_SIMILARITY_THRESHOLD:
                    # 合并规则
                    existing.weight = int((existing.weight + rule.weight) / 2)
                    existing.source_material_ids = list(set(
                        existing.source_material_ids + rule.source_material_ids
                    ))
                    found_duplicate = True
                    break
            if not found_duplicate:
                merged.append(rule)
        return merged

    @staticmethod
    def _calculate_similarity(a: str, b: str) -> float:
        """计算两段文本的相似度.

        使用difflib.SequenceMatcher计算相似度比率.

        Args:
            a: 文本A.
            b: 文本B.

        Returns:
            相似度(0.0-1.0).
        """
        return difflib.SequenceMatcher(None, a, b).ratio()

    def detect_conflicts(self, rules: list[Rule]) -> dict[str, Any]:
        """检测规则冲突.

        两阶段检测：
        1. 本地预筛：同维度相似度超过阈值的规则对
        2. LLM语义判断：对预筛出的规则对进行语义冲突判断

        Args:
            rules: 规则列表.

        Returns:
            冲突检测报告.
        """
        # 阶段1: 本地预筛
        candidate_pairs: list[tuple[Rule, Rule]] = []
        for i in range(len(rules)):
            for j in range(i + 1, len(rules)):
                if rules[i].dimension != rules[j].dimension:
                    continue
                similarity = self._calculate_similarity(rules[i].content, rules[j].content)
                if similarity >= CONFLICT_DETECTION_THRESHOLD:
                    candidate_pairs.append((rules[i], rules[j]))

        logger.debug("冲突预筛候选对: %d", len(candidate_pairs))

        # 阶段2: LLM语义判断
        conflict_groups: list[dict[str, Any]] = []
        for r1, r2 in candidate_pairs:
            is_conflict = self._llm_conflict_check(r1, r2)
            if is_conflict:
                r1.conflicting_rule_ids.append(r2.id)
                r2.conflicting_rule_ids.append(r1.id)
                conflict_groups.append({
                    "rule_a": {"id": r1.id, "content": r1.content},
                    "rule_b": {"id": r2.id, "content": r2.content},
                    "dimension": r1.dimension.value,
                })

        return {
            "total_candidates": len(candidate_pairs),
            "conflict_count": len(conflict_groups),
            "conflict_groups": conflict_groups,
        }

    def _llm_conflict_check(self, rule_a: Rule, rule_b: Rule) -> bool:
        """使用LLM判断两条规则是否语义冲突.

        Args:
            rule_a: 规则A.
            rule_b: 规则B.

        Returns:
            是否冲突.
        """
        prompt = (
            "请判断以下两条写作规则是否存在语义冲突（即同时遵守两者会导致矛盾或不可行）。\n\n"
            f"规则1: {rule_a.content}\n"
            f"规则2: {rule_b.content}\n\n"
            "如果存在冲突，请回复\"CONFLICT\", 如果不冲突，请回复\"OK\"。只输出这两个词之一，不要其他内容。"
        )
        request = LLMRequest(prompt=prompt, temperature=0.1, max_tokens=10)
        response = self._llm.chat(request, use_cache=False)

        if response.success:
            result = response.content.strip().upper()
            return "CONFLICT" in result
        return False

    def _merge_with_existing(self, new_rules: list[Rule], existing: RuleSet) -> list[Rule]:
        """将新规则与现有规则集合并（增量模式）.

        Args:
            new_rules: 新规则列表.
            existing: 现有规则集.

        Returns:
            合并后的规则列表.
        """
        existing_rules: list[Rule] = []
        for dim_rules in existing.rules.values():
            existing_rules.extend(dim_rules)

        all_rules = existing_rules + new_rules
        return self._merge_rules(all_rules)

    def targeted_distill(
        self,
        analysis_files: list[AnalysisFile],
        dimensions: list[str],
        name: str = "定向规则集",
    ) -> RuleSet:
        """定向蒸馏指定维度.

        Args:
            analysis_files: 拆解结果列表.
            dimensions: 目标维度名称列表.
            name: 规则集名称.

        Returns:
            定向蒸馏后的规则集.
        """
        return self.distill(
            analysis_files=analysis_files,
            mode=DistillMode.TARGETED,
            target_dimensions=dimensions,
            name=name,
        )
