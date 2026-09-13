"""迭代引擎页.

提供正负样本打标、迭代触发、版本升级功能.
"""

from __future__ import annotations

import streamlit as st

from core.constants import FeedbackCategory, FeedbackType
from core.models import CreationProject
from core.storage import StorageManager
from services.feedback_engine import FeedbackEngine
from services.skill_manager import SkillManager
from ui.state_manager import StateManager
from utils.logger import get_logger

logger = get_logger(__name__)


def render() -> None:
    """渲染迭代引擎页面."""
    st.header("迭代引擎")
    st.markdown("收集创作反馈，触发微迭代或版本迭代，持续优化Skill。")

    state = StateManager()
    storage = StorageManager()
    feedback_engine = FeedbackEngine(storage=storage)
    skill_mgr = SkillManager(storage)

    # ==================== 项目选择 ====================
    st.subheader("选择项目")
    projects = storage.list_projects()
    if not projects:
        st.warning("暂无项目，请先在「分步创作」页创建项目")
        return

    selected_project = st.selectbox(
        "项目",
        options=projects,
        format_func=lambda p: p.name,
    )

    if not selected_project:
        return

    st.markdown(f"**项目:** {selected_project.name}")

    # ==================== 添加反馈样本 ====================
    st.divider()
    st.subheader("添加反馈样本")

    with st.form("feedback_form"):
        col1, col2 = st.columns(2)
        with col1:
            feedback_type = st.selectbox(
                "反馈类型",
                options=[t.value for t in FeedbackType],
            )
        with col2:
            category = st.selectbox(
                "问题分类",
                options=[c.value for c in FeedbackCategory],
            )

        content = st.text_area(
            "反馈内容",
            placeholder="描述这个创作内容的优点或问题...",
            height=100,
        )

        related_rules = st.text_input(
            "关联规则ID（可选，多个用逗号分隔）",
            placeholder="rule_id_1, rule_id_2",
        )

        weight_delta = st.slider(
            "建议权重调整",
            min_value=-20,
            max_value=20,
            value=0,
            help="正样本建议增加权重，负样本建议减少权重",
        )

        submitted = st.form_submit_button("添加反馈", type="primary")
        if submitted:
            if not content.strip():
                st.error("反馈内容不能为空")
            else:
                try:
                    rule_ids = [r.strip() for r in related_rules.split(",") if r.strip()]
                    sample = feedback_engine.add_sample(
                        project_id=selected_project.id,
                        feedback_type=FeedbackType(feedback_type),
                        category=category,
                        content=content,
                        related_rule_ids=rule_ids,
                        suggested_weight_delta=weight_delta,
                    )
                    st.success("反馈已添加")
                    logger.info("添加反馈: project=%s, sample=%s", selected_project.id, sample.id)
                    st.rerun()
                except Exception as e:
                    st.error(f"添加失败: {e}")

    # ==================== 反馈列表 ====================
    st.divider()
    st.subheader("反馈样本列表")

    samples = feedback_engine.list_feedback(selected_project.id)
    if not samples:
        st.info("暂无反馈样本")
    else:
        positive = [s for s in samples if s.feedback_type == FeedbackType.POSITIVE]
        negative = [s for s in samples if s.feedback_type == FeedbackType.NEGATIVE]

        col1, col2 = st.columns(2)
        col1.metric("正样本", len(positive))
        col2.metric("负样本", len(negative))

        for sample in samples:
            icon = "+" if sample.feedback_type == FeedbackType.POSITIVE else "-"
            color = "success" if sample.feedback_type == FeedbackType.POSITIVE else "error"
            with st.expander(f"{icon} [{sample.category}] {sample.content[:50]}..."):
                st.markdown(f"**类型:** {sample.feedback_type.value}")
                st.markdown(f"**分类:** {sample.category}")
                st.markdown(f"**内容:** {sample.content}")
                if sample.related_rule_ids:
                    st.markdown(f"**关联规则:** {', '.join(sample.related_rule_ids)}")
                if sample.suggested_weight_delta != 0:
                    st.markdown(f"**建议调整:** {sample.suggested_weight_delta:+.0f}")
                st.caption(f"时间: {sample.timestamp}")

    # ==================== 迭代操作 ====================
    st.divider()
    st.subheader("迭代操作")

    if not samples:
        st.info("请先添加反馈样本")
        return

    # 选择Skill
    skills = skill_mgr.list_skills()
    if not skills:
        st.warning("暂无Skill，请先在「Skill管理」页创建")
        return

    selected_skill = st.selectbox(
        "选择要优化的Skill",
        options=skills,
        format_func=lambda s: f"{s.name} (v{s.current_version})",
    )

    if not selected_project.skill_id or selected_project.skill_id != selected_skill.id:
        st.info("提示: 当前项目未关联此Skill，迭代仍可执行但建议关联以获得更好效果")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**微迭代**")
        st.caption("根据反馈自动调整关联规则权重（+/-5）")
        if st.button("触发微迭代", type="primary", use_container_width=True):
            with st.spinner("正在执行微迭代..."):
                try:
                    updated_skill = feedback_engine.trigger_micro_iteration(selected_skill, samples)
                    skill_mgr.save_skill(updated_skill)
                    st.success("微迭代完成！规则权重已调整")
                    logger.info("微迭代完成: skill=%s", updated_skill.name)
                    st.rerun()
                except Exception as e:
                    st.error(f"微迭代失败: {e}")

    with col2:
        st.markdown("**版本迭代**")
        st.caption("基于反馈生成规则修订草案，可能新增/删除/修改规则")
        if st.button("触发版本迭代", type="primary", use_container_width=True):
            with st.spinner("正在生成修订草案..."):
                try:
                    result = feedback_engine.trigger_version_iteration(selected_skill, samples)
                    if result["success"]:
                        state.set("iteration_draft", result)
                        st.success("修订草案生成成功！")
                        logger.info("版本迭代草案生成: skill=%s", selected_skill.name)
                        st.rerun()
                    else:
                        st.error(f"生成失败: {result.get('error', '未知错误')}")
                except Exception as e:
                    st.error(f"版本迭代失败: {e}")

    # 显示迭代草案
    draft = state.get("iteration_draft")
    if draft:
        st.divider()
        st.subheader("修订草案")

        summary = draft.get("feedback_summary", {})
        st.markdown(
            f"基于 **{summary.get('positive', 0)}** 个正样本和 "
            f"**{summary.get('negative', 0)}** 个负样本生成"
        )

        with st.expander("查看完整草案"):
            st.markdown(draft.get("draft", ""))

        suggestions = draft.get("suggestions", [])
        if suggestions:
            st.markdown(f"**结构化建议 ({len(suggestions)}条)**")
            for s in suggestions:
                with st.container(border=True):
                    st.markdown(f"**操作:** {s.get('action', '未知')}")
                    st.markdown(f"**维度:** {s.get('dimension', '未知')}")
                    st.markdown(f"**内容:** {s.get('content', '')}")
                    st.markdown(f"**权重:** {s.get('weight', 50)}")

        changelog = st.text_input("版本变更说明", placeholder="描述本次迭代的主要内容")
        if st.button("应用修订并升级版本", type="primary"):
            with st.spinner("正在应用修订..."):
                try:
                    updated_skill = feedback_engine.apply_iteration_draft(
                        selected_skill,
                        suggestions,
                        changelog,
                    )
                    st.success(f"修订已应用！新版本: {updated_skill.current_version}")
                    state.delete("iteration_draft")
                    logger.info("应用迭代修订: skill=%s, version=%s", updated_skill.name, updated_skill.current_version)
                    st.rerun()
                except Exception as e:
                    st.error(f"应用修订失败: {e}")

        if st.button("丢弃草案"):
            state.delete("iteration_draft")
            st.rerun()
