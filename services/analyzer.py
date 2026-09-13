"""网文拆解引擎.

提供八维度并发拆解功能，支持文本分块和多线程处理.
"""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from core.constants import (
    AnalysisDimension,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    MAX_WORKERS,
)
from core.models import AnalysisFile, AnalysisRule, CleanedText, LLMRequest
from services.llm_client import LLMClient
from services.text_cleaner import TextCleaner
from utils.logger import get_logger

logger = get_logger(__name__)

PROMPT_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "config" / "prompt_templates"


class Analyzer:
    """网文拆解分析器.

    对清洗后的网文素材进行八维度并发拆解，每维度独立调用LLM分析.
    支持文本自动分块和LLM输出结果的鲁棒解析.
    """

    def __init__(self, llm_client: LLMClient | None = None, skill_context: str = "") -> None:
        """初始化拆解分析器.

        Args:
            llm_client: LLM客户端实例，未提供时创建新实例.
        """
        self._llm = llm_client or LLMClient()
        self._text_cleaner = TextCleaner()
        self._prompt_cache: dict[str, str] = {}
        self._skill_context = skill_context.strip()

    def _load_prompt_template(self, dimension: AnalysisDimension) -> str:
        """加载指定维度的提示词模板.

        Args:
            dimension: 分析维度.

        Returns:
            提示词模板字符串.
        """
        cache_key = dimension.value
        if cache_key in self._prompt_cache:
            return self._prompt_cache[cache_key]

        template_path = PROMPT_TEMPLATE_DIR / f"analyze_{dimension.value}.txt"
        try:
            if template_path.exists():
                template = template_path.read_text(encoding="utf-8")
            else:
                # 使用默认模板
                template = self._default_prompt_template(dimension)
                logger.warning("模板文件不存在，使用默认模板: %s", template_path)
        except Exception as e:
            logger.error("加载模板失败: %s, 错误: %s", template_path, e)
            template = self._default_prompt_template(dimension)

        self._prompt_cache[cache_key] = template
        return template

    @staticmethod
    def _default_prompt_template(dimension: AnalysisDimension) -> str:
        """生成默认提示词模板.

        Args:
            dimension: 分析维度.

        Returns:
            默认提示词模板.
        """
        return (
            f"你是一位专业的网文分析专家。请对以下网文内容进行'{dimension.value}'维度的深度分析。\n\n"
            "要求:\n"
            f"1. 提取该文本在'{dimension.value}'方面的具体手法、规律和技巧\n"
            "2. 每条规则需包含: 内容描述、重要性权重(1-100)、解释说明、原文示例\n"
            "3. 输出格式为JSON数组，每个元素包含content, weight, explanation, examples字段\n"
            "4. 只输出JSON，不要其他解释文字\n\n"
            "文本内容:\n{text}\n\n"
            "请输出JSON格式的分析结果:"
        )

    def _build_prompt(self, dimension: AnalysisDimension, text: str) -> str:
        """构建完整的提示词.

        Args:
            dimension: 分析维度.
            text: 待分析的文本内容.

        Returns:
            完整提示词.
        """
        template = self._load_prompt_template(dimension)
        prompt = template.replace("{text}", text)
        if self._skill_context:
            prompt = f"{self._skill_context}\\n\\n{prompt}"
        return prompt

    def _analyze_dimension(self, dimension: AnalysisDimension, text_chunks: list[str]) -> AnalysisFile:
        """分析单个维度.

        将所有文本块合并后发送给LLM进行分析，解析返回的规则列表.

        Args:
            dimension: 分析维度.
            text_chunks: 文本分块列表.

        Returns:
            该维度的拆解结果.
        """
        # 合并文本块（带块分隔标记）
        combined_text = "\n\n".join(
            f"[第{i+1}段]\n{chunk}" for i, chunk in enumerate(text_chunks)
        )

        # 如果合并后太长，截断到合理长度
        max_prompt_chars = 12000
        if len(combined_text) > max_prompt_chars:
            combined_text = combined_text[:max_prompt_chars] + "\n...（内容截断）"
            logger.warning("文本过长已截断: dimension=%s", dimension.value)

        prompt = self._build_prompt(dimension, combined_text)
        request = LLMRequest(prompt=prompt, temperature=0.5, max_tokens=4000)

        logger.info("开始拆解维度: %s", dimension.value)
        response = self._llm.chat(request, use_cache=False)

        if not response.success:
            logger.error("拆解失败: dimension=%s, error=%s", dimension.value, response.error_message)
            return AnalysisFile(
                material_id="",
                dimension=dimension,
                rules=[],
                summary=f"分析失败: {response.error_message}",
            )

        rules, summary = self._parse_llm_output(response.content)
        logger.info("拆解完成: dimension=%s, rules=%d", dimension.value, len(rules))

        return AnalysisFile(
            material_id="",
            dimension=dimension,
            rules=rules,
            summary=summary,
        )

    def _parse_llm_output(self, content: str) -> tuple[list[AnalysisRule], str]:
        """鲁棒解析LLM输出，提取规则列表.

        解析策略:
        1. 尝试提取JSON代码块并解析
        2. 尝试直接解析整个输出为JSON
        3. 使用正则提取条目作为fallback

        Args:
            content: LLM原始输出内容.

        Returns:
            (规则列表, 总结文本).
        """
        rules: list[AnalysisRule] = []
        summary = ""

        if not content or not content.strip():
            logger.warning("LLM输出为空")
            return rules, summary

        cleaned = content.strip()

        # 策略1: 提取markdown代码块中的JSON
        code_block_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
        if code_block_match:
            cleaned = code_block_match.group(1).strip()

        # 策略2: 尝试解析JSON数组
        try:
            data = json.loads(cleaned)
            if isinstance(data, list):
                rules = self._parse_rule_list(data)
                summary = f"成功解析{len(rules)}条规则"
                return rules, summary
            if isinstance(data, dict):
                # 可能是 {rules: [...], summary: "..."} 格式
                rule_list = data.get("rules", [])
                if isinstance(rule_list, list):
                    rules = self._parse_rule_list(rule_list)
                summary = data.get("summary", "") or f"成功解析{len(rules)}条规则"
                return rules, summary
        except json.JSONDecodeError:
            logger.debug("JSON解析失败，尝试正则提取")

        # 策略3: 使用正则提取编号条目作为fallback
        rules = self._extract_rules_by_regex(content)
        summary = f"通过正则提取{len(rules)}条规则"
        return rules, summary

    def _parse_rule_list(self, data: list[Any]) -> list[AnalysisRule]:
        """将JSON数组解析为规则列表.

        Args:
            data: JSON数组数据.

        Returns:
            解析后的规则列表.
        """
        rules: list[AnalysisRule] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            try:
                content = str(item.get("content", item.get("rule", ""))).strip()
                if not content:
                    continue
                weight = item.get("weight", item.get("importance", 50))
                try:
                    weight = int(weight)
                except (TypeError, ValueError):
                    weight = 50
                weight = max(0, min(100, weight))

                explanation = str(item.get("explanation", item.get("desc", "")))
                examples = item.get("examples", item.get("example", []))
                if isinstance(examples, str):
                    examples = [examples] if examples else []
                elif not isinstance(examples, list):
                    examples = []

                rules.append(
                    AnalysisRule(
                        content=content,
                        weight=weight,
                        explanation=explanation,
                        examples=[str(e) for e in examples if e],
                    )
                )
            except Exception as e:
                logger.warning("解析单条规则失败: %s", e)
                continue
        return rules

    def _extract_rules_by_regex(self, text: str) -> list[AnalysisRule]:
        """使用正则表达式从非结构化文本中提取规则.

        匹配模式如: "1. 规则内容..." 或 "- 规则内容..."

        Args:
            text: 原始文本.

        Returns:
            提取的规则列表.
        """
        rules: list[AnalysisRule] = []

        # 匹配编号列表项
        pattern = re.compile(r"(?:^|\n)\s*(?:\d+[\.、]|[-*])\s*(.+?)(?=\n\s*(?:\d+[\.、]|[-*])|$)", re.DOTALL)
        matches = pattern.findall(text)

        for match in matches:
            content = match.strip().replace("\n", " ")
            # 截断过长内容
            if len(content) > 500:
                content = content[:500] + "..."
            if content and len(content) > 5:
                rules.append(AnalysisRule(content=content, weight=50))

        return rules

    def analyze(self, cleaned_text: CleanedText) -> list[AnalysisFile]:
        """执行八维度并发拆解.

        使用ThreadPoolExecutor并发处理8个维度，每个维度独立调用LLM.

        Args:
            cleaned_text: 清洗后的文本对象.

        Returns:
            8个维度的拆解结果列表.
        """
        # 文本分块
        chunks = self._text_cleaner.chunk_text(
            cleaned_text.cleaned_text,
            chunk_size=CHUNK_SIZE,
            overlap=CHUNK_OVERLAP,
        )
        cleaned_text.chunks = chunks
        logger.info("开始八维度拆解: material_id=%s, chunks=%d", cleaned_text.material_id, len(chunks))

        dimensions = list(AnalysisDimension)
        results: list[AnalysisFile] = []

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_dimension = {
                executor.submit(self._analyze_dimension, dim, chunks): dim
                for dim in dimensions
            }

            for future in as_completed(future_to_dimension):
                dimension = future_to_dimension[future]
                try:
                    analysis = future.result()
                    analysis.material_id = cleaned_text.material_id
                    results.append(analysis)
                except Exception as e:
                    logger.error("维度拆解异常: dimension=%s, error=%s", dimension.value, e)
                    results.append(
                        AnalysisFile(
                            material_id=cleaned_text.material_id,
                            dimension=dimension,
                            rules=[],
                            summary=f"拆解异常: {str(e)}",
                        )
                    )

        # 按维度顺序排序
        dim_order = {d: i for i, d in enumerate(AnalysisDimension)}
        results.sort(key=lambda a: dim_order.get(a.dimension, 999))

        logger.info("八维度拆解全部完成: material_id=%s, total_rules=%d", cleaned_text.material_id, sum(len(r.rules) for r in results))
        return results

