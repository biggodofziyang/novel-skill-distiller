"""素材拆解页.

提供文件上传、文本清洗、八维度拆解的完整流程UI.
"""

from __future__ import annotations

import io

import streamlit as st
from docx import Document

from core.constants import ALLOWED_UPLOAD_EXTENSIONS, MAX_UPLOAD_SIZE_MB
from core.models import NovelMaterial
from core.storage import StorageManager
from services.analyzer import Analyzer
from services.text_cleaner import TextCleaner
from ui.components import progress_panel
from ui.state_manager import StateManager
from utils.logger import get_logger
from utils.validators import validate_file_extension, validate_file_size

logger = get_logger(__name__)


def _read_uploaded_file(uploaded_file: Any) -> str:
    """读取上传文件内容为文本.

    Args:
        uploaded_file: Streamlit上传文件对象.

    Returns:
        文件文本内容.
    """
    ext = validate_file_extension(uploaded_file.name)

    if ext == ".docx":
        doc = Document(io.BytesIO(uploaded_file.read()))
        return "\n".join([p.text for p in doc.paragraphs])
    else:
        return uploaded_file.read().decode("utf-8", errors="ignore")


def render() -> None:
    """渲染素材拆解页面."""
    st.header("素材拆解")
    st.markdown("上传网文素材，自动清洗并进行八维度拆解分析。")

    state = StateManager()
    storage = StorageManager()

    # ==================== 文件上传区 ====================
    st.subheader("1. 上传素材")
    uploaded_file = st.file_uploader(
        "选择文件（支持 txt, docx, md）",
        type=[ext.lstrip(".") for ext in ALLOWED_UPLOAD_EXTENSIONS],
        help=f"最大文件大小: {MAX_UPLOAD_SIZE_MB}MB",
    )

    if uploaded_file is not None:
        try:
            validate_file_size(uploaded_file.size)
            file_text = _read_uploaded_file(uploaded_file)

            material = NovelMaterial(
                filename=uploaded_file.name,
                raw_text=file_text,
                file_size=uploaded_file.size,
            )
            state.set("uploaded_material", material)
            st.success(f"文件上传成功: {uploaded_file.name} ({len(file_text)} 字符)")
        except Exception as e:
            st.error(f"文件读取失败: {e}")
            logger.error("文件读取失败: %s", e)
            return

    material = state.get("uploaded_material")
    if material is None:
        st.info("请先上传网文素材文件")
        return

    # ==================== 文本清洗区 ====================
    st.subheader("2. 文本清洗")
    cleaned = state.get("cleaned_text")

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("执行清洗", type="primary", use_container_width=True):
            with st.spinner("正在清洗文本..."):
                try:
                    cleaner = TextCleaner()
                    cleaned = cleaner.clean(material)
                    state.set("cleaned_text", cleaned)
                    logger.info("文本清洗完成: material_id=%s", material.id)
                    st.rerun()
                except Exception as e:
                    st.error(f"清洗失败: {e}")
                    logger.error("文本清洗失败: %s", e)

    if cleaned:
        with col2:
            st.metric("清洗后长度", f"{len(cleaned.cleaned_text)} 字符")
        with st.expander("查看清洗详情"):
            c1, c2, c3 = st.columns(3)
            c1.metric("移除字符", cleaned.removed_chars_count)
            c2.metric("移除重复段落", cleaned.removed_paragraphs_count)
            c3.metric("分块数", len(cleaned.chunks))
            st.markdown("**清洗后文本预览（前2000字）**")
            st.text_area(
                "cleaned_preview",
                value=cleaned.cleaned_text[:2000],
                height=200,
                label_visibility="collapsed",
                disabled=True,
            )
    else:
        with col2:
            st.info("点击左侧按钮执行清洗")
        return

    # ==================== 拆解分析区 ====================
    st.subheader("3. 八维度拆解")
    analysis_results = state.get("analysis_results", [])

    if st.button("开始拆解", type="primary", use_container_width=True):
        with st.spinner("正在进行八维度拆解分析，请耐心等待..."):
            try:
                analyzer = Analyzer()
                results = analyzer.analyze(cleaned)
                state.set("analysis_results", results)

                # 保存到存储
                for analysis in results:
                    storage.save_analysis(analysis)
                storage.save_material(material)

                logger.info("拆解分析完成: material_id=%s, dimensions=%d", material.id, len(results))
                st.rerun()
            except Exception as e:
                st.error(f"拆解失败: {e}")
                logger.error("拆解分析失败: %s", e)

    if analysis_results:
        st.success(f"拆解完成！共分析 {len(analysis_results)} 个维度")

        # 统计总规则数
        total_rules = sum(len(r.rules) for r in analysis_results)
        st.metric("提取规则总数", total_rules)

        # 按维度展示标签页
        tabs = st.tabs([r.dimension.value for r in analysis_results])
        for tab, analysis in zip(tabs, analysis_results):
            with tab:
                st.markdown(f"**总结:** {analysis.summary}")
                st.markdown(f"**规则数量:** {len(analysis.rules)}")

                if analysis.rules:
                    for i, rule in enumerate(analysis.rules, 1):
                        with st.container(border=True):
                            st.markdown(f"{i}. **{rule.content}**")
                            cols = st.columns([1, 1, 2])
                            cols[0].metric("权重", rule.weight)
                            if rule.source_chunk_index is not None:
                                cols[1].metric("来源块", rule.source_chunk_index + 1)
                            if rule.explanation:
                                cols[2].markdown(f"*{rule.explanation}*")
                            if rule.examples:
                                with st.expander("示例"):
                                    for ex in rule.examples:
                                        st.markdown(f"> {ex}")
                else:
                    st.info("该维度未提取到规则")
    else:
        st.info("点击上方按钮开始八维度拆解")
