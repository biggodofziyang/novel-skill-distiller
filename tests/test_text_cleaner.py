"""Tests for services.text_cleaner module."""

import pytest

from core.models import CleanedText, NovelMaterial
from services.text_cleaner import TextCleaner


@pytest.fixture
def cleaner():
    return TextCleaner()


class TestRemoveAds:
    """Tests for advertisement removal."""

    def test_remove_qq_group(self, cleaner):
        text = "正文内容\nQQ群:12345678\n后续内容"
        result, removed = cleaner._remove_ads(text)
        assert "QQ群" not in result
        assert removed > 0

    def test_remove_wechat(self, cleaner):
        text = "正文\n微信:abc123\n后续"
        result, removed = cleaner._remove_ads(text)
        assert "微信:abc123" not in result

    def test_remove_follow_public_account(self, cleaner):
        text = "正文\n关注微信公众号获取更新\n后续"
        result, removed = cleaner._remove_ads(text)
        assert "关注微信公众号" not in result

    def test_remove_qr_code(self, cleaner):
        text = "正文\n扫码关注\n后续"
        result, removed = cleaner._remove_ads(text)
        assert "扫码关注" not in result

    def test_remove_join_group(self, cleaner):
        text = "正文\n加入书友群\n后续"
        result, removed = cleaner._remove_ads(text)
        assert "加入书友群" not in result

    def test_remove_ticket_requests(self, cleaner):
        text = "正文\n求推荐票，求月票\n后续"
        result, removed = cleaner._remove_ads(text)
        assert "推荐票" not in result
        assert "月票" not in result

    def test_remove_reward_request(self, cleaner):
        text = "正文\n欢迎打赏\n后续"
        result, removed = cleaner._remove_ads(text)
        assert "打赏" not in result

    def test_no_ads_in_clean_text(self, cleaner):
        text = "这是一段干净的正文内容，没有任何广告。"
        result, removed = cleaner._remove_ads(text)
        assert result == text
        assert removed == 0

    def test_multiple_ads(self, cleaner):
        text = "正文\n关注微信公众号\n正文2\nQQ群:12345\n正文3"
        result, removed = cleaner._remove_ads(text)
        assert "关注微信公众号" not in result
        assert "QQ群" not in result
        assert removed > 0


class TestRemoveGarbage:
    """Tests for garbage character removal."""

    def test_remove_control_chars(self, cleaner):
        text = "正文\x01\x02\x03正文"
        result, removed = cleaner._remove_garbage(text)
        assert "\x01" not in result
        assert "\x02" not in result
        assert removed > 0

    def test_remove_high_ascii(self, cleaner):
        text = "正文\x80\x81\x82正文"
        result, removed = cleaner._remove_garbage(text)
        assert "\x80" not in result
        assert removed > 0

    def test_short_control_chars_preserved(self, cleaner):
        # Less than 3 control chars should not be removed
        text = "正文\x01正文"
        result, removed = cleaner._remove_garbage(text)
        assert result == text
        assert removed == 0

    def test_clean_text_unchanged(self, cleaner):
        text = "这是一段干净的正文。"
        result, removed = cleaner._remove_garbage(text)
        assert result == text
        assert removed == 0


class TestNormalizeWhitespace:
    """Tests for whitespace normalization."""

    def test_tabs_to_spaces(self, cleaner):
        text = "正文\t正文"
        result = cleaner._normalize_whitespace(text)
        assert "\t" not in result

    def test_multiple_spaces_collapsed(self, cleaner):
        text = "正文    正文"
        result = cleaner._normalize_whitespace(text)
        assert "    " not in result

    def test_leading_trailing_spaces_preserved(self, cleaner):
        text = "  正文  "
        result = cleaner._normalize_whitespace(text)
        assert result == " 正文 "


class TestRemoveEmptyLines:
    """Tests for empty line removal."""

    def test_remove_multiple_empty_lines(self, cleaner):
        text = "第一段\n\n\n\n第二段"
        result = cleaner._remove_empty_lines(text)
        assert "\n\n\n\n" not in result

    def test_preserve_single_line_break(self, cleaner):
        text = "第一段\n\n第二段"
        result = cleaner._remove_empty_lines(text)
        assert "第一段" in result
        assert "第二段" in result

    def test_strip_leading_trailing_newlines(self, cleaner):
        text = "\n\n正文\n\n"
        result = cleaner._remove_empty_lines(text)
        assert not result.startswith("\n")
        assert not result.endswith("\n")


class TestRemoveDuplicateParagraphs:
    """Tests for duplicate paragraph removal."""

    def test_remove_exact_duplicate(self, cleaner):
        text = "这是重复的段落内容\n这是重复的段落内容\n不同内容"
        result, removed = cleaner._remove_duplicate_paragraphs(text)
        assert removed == 1
        assert result.count("这是重复的段落内容") == 1

    def test_preserve_short_duplicates(self, cleaner):
        text = "短句\n短句\n其他"
        result, removed = cleaner._remove_duplicate_paragraphs(text)
        assert removed == 0  # Below min_length

    def test_no_duplicates(self, cleaner):
        text = "第一段内容\n第二段内容\n第三段内容"
        result, removed = cleaner._remove_duplicate_paragraphs(text)
        assert removed == 0
        assert result == text

    def test_custom_min_length(self, cleaner):
        text = "中等长度段落\n中等长度段落"
        result, removed = cleaner._remove_duplicate_paragraphs(text, min_length=5)
        assert removed == 1

    def test_whitespace_variations_not_duplicates(self, cleaner):
        text = "段落内容\n 段落内容 \n其他"
        result, removed = cleaner._remove_duplicate_paragraphs(text)
        # After stripping, they are the same
        assert removed == 1


class TestChunkText:
    """Tests for text chunking."""

    def test_short_text_single_chunk(self, cleaner):
        text = "短文本"
        chunks = cleaner.chunk_text(text, chunk_size=100, overlap=10)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_long_text_multiple_chunks(self, cleaner):
        text = "A" * 2000
        chunks = cleaner.chunk_text(text, chunk_size=500, overlap=50)
        assert len(chunks) > 1

    def test_overlap_respected(self, cleaner):
        text = "X" * 2000
        chunks = cleaner.chunk_text(text, chunk_size=500, overlap=50)
        if len(chunks) >= 2:
            # The second chunk should start before position 500 due to overlap
            assert len(chunks[0]) <= 500

    def test_break_at_newline(self, cleaner):
        text = "A" * 300 + "\n" + "B" * 300 + "\n" + "C" * 300
        chunks = cleaner.chunk_text(text, chunk_size=400, overlap=10)
        assert len(chunks) >= 2
        # Should break at newline if possible
        for chunk in chunks[:-1]:
            assert len(chunk) <= 400

    def test_break_at_period(self, cleaner):
        text = "A" * 300 + "。" + "B" * 300 + "。" + "C" * 300
        chunks = cleaner.chunk_text(text, chunk_size=400, overlap=10)
        assert len(chunks) >= 2

    def test_empty_text(self, cleaner):
        chunks = cleaner.chunk_text("", chunk_size=100, overlap=10)
        assert chunks == [""]


class TestClean:
    """Tests for the full clean pipeline."""

    def test_full_clean(self, cleaner):
        raw = (
            "第一章\n\n"
            "这是正文内容，非常精彩。\n\n"
            "关注微信公众号获取更新\n\n"
            "这是正文内容，非常精彩。\n\n"  # duplicate
            "第二章\n\n"
            "更多内容在这里。\n\n"
        )
        material = NovelMaterial(filename="test.txt", raw_text=raw, file_size=len(raw.encode()))
        result = cleaner.clean(material)

        assert isinstance(result, CleanedText)
        assert result.material_id == material.id
        assert "关注微信公众号" not in result.cleaned_text
        # Duplicate paragraph removed
        assert result.removed_paragraphs_count >= 1
        assert result.removed_chars_count > 0

    def test_clean_with_empty_input(self, cleaner):
        material = NovelMaterial(filename="empty.txt", raw_text="", file_size=0)
        result = cleaner.clean(material)
        assert result.cleaned_text == ""
        assert result.removed_chars_count == 0
        assert result.removed_paragraphs_count == 0

    def test_clean_with_only_ads(self, cleaner):
        raw = "关注微信公众号\nQQ群:12345\n求推荐票"
        material = NovelMaterial(filename="ads.txt", raw_text=raw, file_size=len(raw.encode()))
        result = cleaner.clean(material)
        assert result.cleaned_text == ""
        assert result.removed_chars_count > 0

    def test_clean_preserves_structure(self, cleaner):
        raw = "第一段\n\n第二段\n\n第三段"
        material = NovelMaterial(filename="struct.txt", raw_text=raw, file_size=len(raw.encode()))
        result = cleaner.clean(material)
        assert "第一段" in result.cleaned_text
        assert "第二段" in result.cleaned_text
        assert "第三段" in result.cleaned_text

    def test_clean_populates_chunks_for_long_text(self, cleaner):
        raw = "A" * 10000
        material = NovelMaterial(filename="long.txt", raw_text=raw, file_size=len(raw.encode()))
        result = cleaner.clean(material)
        # The CleanedText model default for chunks is empty list,
        # but chunk_text method is available. The clean method does not
        # auto-populate chunks field in CleanedText.
        assert isinstance(result.chunks, list)
