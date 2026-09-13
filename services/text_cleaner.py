"""文本清洗服务.

提供网文素材的清洗功能，包括广告删除、乱码清理、空行去除和重复段落去重.
"""

from __future__ import annotations

import hashlib
import re

from core.constants import AD_PATTERNS, GARBAGE_PATTERN
from core.models import CleanedText, NovelMaterial
from utils.logger import get_logger

logger = get_logger(__name__)


class TextCleaner:
    """文本清洗器.

    对上传的网文素材执行多阶段清洗，输出结构化清洗结果.
    """

    def __init__(self) -> None:
        """初始化文本清洗器，编译正则表达式."""
        self._ad_patterns = [re.compile(p, re.IGNORECASE) for p in AD_PATTERNS]
        self._garbage_pattern = re.compile(GARBAGE_PATTERN)
        self._empty_line_pattern = re.compile(r"\n\s*\n+")
        self._whitespace_pattern = re.compile(r"[ \t]+")

    def clean(self, material: NovelMaterial) -> CleanedText:
        """执行完整文本清洗流程.

        清洗流程:
        1. 移除广告/推广文本
        2. 移除乱码字符
        3. 规范化空白字符
        4. 移除空行
        5. 哈希去重重复段落

        Args:
            material: 原始素材对象.

        Returns:
            清洗结果对象.
        """
        text = material.raw_text
        original_length = len(text)
        removed_chars = 0
        removed_paragraphs = 0

        # 阶段1: 移除广告
        text, ad_removed = self._remove_ads(text)
        removed_chars += ad_removed
        logger.debug("广告移除: %d字符", ad_removed)

        # 阶段2: 移除乱码
        text, garbage_removed = self._remove_garbage(text)
        removed_chars += garbage_removed
        logger.debug("乱码移除: %d字符", garbage_removed)

        # 阶段3: 规范化空白
        text = self._normalize_whitespace(text)

        # 阶段4: 移除空行
        text = self._remove_empty_lines(text)

        # 阶段5: 重复段落去重
        text, dup_removed = self._remove_duplicate_paragraphs(text)
        removed_paragraphs += dup_removed
        logger.debug("重复段落移除: %d段", dup_removed)

        final_length = len(text)
        removed_chars = original_length - final_length

        logger.info(
            "文本清洗完成: 原始%d字符 -> 清洗后%d字符, 移除%d字符, %d重复段落",
            original_length,
            final_length,
            removed_chars,
            removed_paragraphs,
        )

        return CleanedText(
            material_id=material.id,
            cleaned_text=text,
            removed_chars_count=removed_chars,
            removed_paragraphs_count=removed_paragraphs,
        )

    def _remove_ads(self, text: str) -> tuple[str, int]:
        """移除广告和推广文本.

        Args:
            text: 原始文本.

        Returns:
            (清洗后文本, 移除字符数).
        """
        original_length = len(text)
        kept_lines: list[str] = []
        for line in text.splitlines(keepends=True):
            if any(pattern.search(line) for pattern in self._ad_patterns):
                continue
            kept_lines.append(line)
        text = "".join(kept_lines)
        removed = original_length - len(text)
        return text, removed

    def _remove_garbage(self, text: str) -> tuple[str, int]:
        """移除乱码和不可见字符.

        Args:
            text: 原始文本.

        Returns:
            (清洗后文本, 移除字符数).
        """
        original_length = len(text)
        text = self._garbage_pattern.sub("", text)
        removed = original_length - len(text)
        return text, removed

    def _normalize_whitespace(self, text: str) -> str:
        """规范化空白字符（制表符转空格，连续空格合并）.

        Args:
            text: 原始文本.

        Returns:
            规范化后的文本.
        """
        text = self._whitespace_pattern.sub(" ", text)
        return text

    def _remove_empty_lines(self, text: str) -> str:
        """移除连续空行，保留单行换行.

        Args:
            text: 原始文本.

        Returns:
            清理后的文本.
        """
        text = self._empty_line_pattern.sub("\n\n", text)
        # 移除首尾空白行
        text = text.strip("\n")
        return text

    def _remove_duplicate_paragraphs(self, text: str, min_length: int = 4) -> tuple[str, int]:
        """使用哈希去重移除重复段落.

        仅对长度超过min_length的段落进行去重，避免误删短句.

        Args:
            text: 原始文本.
            min_length: 参与去重的最小段落长度.

        Returns:
            (去重后文本, 移除段落数).
        """
        paragraphs = text.split("\n")
        seen_hashes: set[str] = set()
        unique_paragraphs: list[str] = []
        removed_count = 0

        for para in paragraphs:
            stripped = para.strip()
            if len(stripped) >= min_length:
                para_hash = hashlib.md5(stripped.encode("utf-8")).hexdigest()
                if para_hash in seen_hashes:
                    removed_count += 1
                    continue
                seen_hashes.add(para_hash)
            unique_paragraphs.append(para)

        return "\n".join(unique_paragraphs), removed_count

    def chunk_text(self, text: str, chunk_size: int = 8000, overlap: int = 500) -> list[str]:
        """将长文本分块，支持重叠.

        Args:
            text: 待分块的文本.
            chunk_size: 每块最大字符数.
            overlap: 块间重叠字符数.

        Returns:
            文本块列表.
        """
        if len(text) <= chunk_size:
            return [text]

        chunks: list[str] = []
        start = 0
        text_length = len(text)

        while start < text_length:
            end = start + chunk_size
            if end >= text_length:
                chunks.append(text[start:])
                break

            # 尝试在句子或段落边界处截断
            # 优先找换行，其次找句号
            break_pos = text.rfind("\n", start, end)
            if break_pos <= start:
                break_pos = text.rfind("。", start, end)
            if break_pos <= start:
                break_pos = text.rfind(" ", start, end)
            if break_pos <= start:
                break_pos = end

            chunks.append(text[start:break_pos])
            start = break_pos - overlap
            if start <= 0:
                start = break_pos

        logger.debug("文本分块完成: %d块, 总长度%d", len(chunks), text_length)
        return chunks
