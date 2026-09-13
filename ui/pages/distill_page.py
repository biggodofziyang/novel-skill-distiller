"""规则蒸馏页.

提供素材选择、蒸馏模式选择、结果展示和冲突处理功能.
"""

from __future__ import annotations

import streamlit as st

from core.constants import AnalysisDimension, DistillMode
from core.models import AnalysisFile
from core.storage import StorageManager
from services.distiller import Distiller
from ui.components import conflict_dialog
from ui.state_manager import StateManager
from utils.logger import get_logger

logger = get_logger(__name__)


def render() -> None:
    """渲染规则蒸馏页面."""
    st.header("规则蒸馏")
    st.markdown("选择拆解结果，进行规则去重、冲突检测和蒸馏整合。")

    state = StateManager()
    storage = StorageManager()

    # ==================== 素材/拆解结果选择区 ====================
    st.subheader("1. 选择拆解结果")

    # 获取所有素材和拆解结果
    materials = storage.list_materials()
    if not materials:
        st.warning("暂无素材，请先在「素材拆解」页上传并分析素材")
        return

    # 构建素材-拆解的树状选择
    selected_analysis_files: list[AnalysisFile] = []

    for material in materials:
        analyses = storage.list_analysis_by_material(material.id)
        if not analyses:
            continue

        with st.expander(f"{material.filename} ({len(analyses)}个维度)"):
            st.caption(f"素材ID: {material.id}")
            for analysis in analyses:
                checked = st.checkbox(
                    f"{analysis.dimension.value} — {len(analysis.rules)}条规则",
                    key=f"analysis_{analysis.id}",
                )
                if checked:
                    selected_analysis_files.append(analysis)

    if not selected_analysis_files:
        st.info("请至少选择一个拆解结果")
        return

    st.markdown(f"**已选择:** {len(selected_analysis_files)} 个拆解结果")

    # ==================== 蒸馏模式选择 ====================
    st.subheader("2. 选择蒸馏模式")
    mode_label = st.radio(
        "蒸馏模式",
        options=[m.value for m in DistillMode],
        horizontal=True,
        help="全量=重新整合所有规则；增量=在现有规则集上追加；定向=只处理指定维度",
    )
    mode = DistillMode(mode_label)

    # 定向模式时显示维度选择
    target_dimensions: list[str] | None = None
    if mode == DistillMode.TARGETED:
        target_dimensions = st.multiselect(
            "选择目标维度",
            options=[d.value for d in AnalysisDimension],
            default=[d.value for d in AnalysisDimension],
        )
        if not target_dimensions:
            st.warning("定向模式需要至少选择一个维度")
            return

    # 增量模式时选择现有规则集
    existing_rule_set = None
    if mode == DistillMode.INCREMENTAL:
        rule_sets = storage.list_rule_sets()
        if rule_sets:
            selected = st.selectbox(
                "选择现有规则集",
                options=rule_sets,
                format_func=lambda r: f"{r.name} ({sum(len(v) for v in r.rules.values())}条规则)",
            )
            existing_rule_set = selected
        else:
            st.warning("暂无现有规则集，将按全量模式处理")

    # ==================== 执行蒸馏 ====================
    st.subheader("3. 执行蒸馏")
    rule_set_name = st.text_input("规则集名称", value="新规则集")

    if st.button("开始蒸馏", type="primary", use_container_width=True):
        with st.spinner("正在进行规则蒸馏，请耐心等待..."):
            try:
                distiller = Distiller()
                rule_set = distiller.distill(
                    analysis_files=selected_analysis_files,
                    mode=mode,
                    existing_rule_set=existing_rule_set,
                    target_dimensions=target_dimensions,
                    name=rule_set_name,
                )
                state.set("distill_rule_set", rule_set)
                storage.save_rule_set(rule_set)
                logger.info("规则蒸馏完成: %s, rules=%d", rule_set.name, sum(len(v) for v in rule_set.rules.values()))
                st.rerun()
            except Exception as e:
                st.error(f"蒸馏失败: {e}")
                logger.error("规则蒸馏失败: %s", e)

    # ==================== 结果展示 ====================
    rule_set = state.get("distill_rule_set")
    if rule_set:
        st.divider()
        st.subheader("蒸馏结果")

        col1, col2, col3 = st.columns(3)
        total_rules = sum(len(v) for v in rule_set.rules.values())
        col1.metric("规则总数", total_rules)
        col2.metric("来源素材", len(rule_set.source_material_ids))
        col3.metric("蒸馏模式", rule_set.distill_mode.value)

        # 冲突检测展示
        conflict_report = rule_set.conflict_report
        conflicts = conflict_report.get("conflict_groups", [])
        conflict_dialog(conflicts)

        # 按维度展示规则
        st.markdown("### 规则详情")
        dim_tabs = st.tabs(list(rule_set.rules.keys()))
        for tab, (dimension, rules) in zip(dim_tabs, rule_set.rules.items()):
            with tab:
                st.markdown(f"**{dimension}** 共 {len(rules)} 条规则")
                for rule in rules:
                    with st.container(border=True):
                        st.markdown(f"**{rule.content}**")
                        cols = st.columns([1, 1, 2])
                        cols[0].metric("权重", rule.weight)
                        cols[1].metric("来源数", len(rule.source_material_ids))
                        if rule.conflicting_rule_ids:
                            cols[2].error(f"冲突: {len(rule.conflicting_rule_ids)}条")

        # 导出功能
        st.divider()
        col_md, col_json = st.columns(2)
        with col_md:
            md_content = storage.to_markdown(rule_set)
            st.download_button(
                "下载Markdown",
                data=md_content,
                file_name=f"{rule_set.name}.md",
                mime="text/markdown",
                use_container_width=True,
            )
    else:
        st.info("配置完成后点击「开始蒸馏」按钮")
