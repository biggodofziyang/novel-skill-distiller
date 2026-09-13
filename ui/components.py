"""可复用UI组件.

提供规则卡片、进度面板、冲突对话框、校验报告等Streamlit组件.
"""

from typing import Any

import streamlit as st

from core.models import SkillRule


def rule_card(
    rule: SkillRule,
    editable: bool = False,
    on_weight_change: Any = None,
    key_prefix: str = "rule",
) -> None:
    """渲染规则卡片.

    Args:
        rule: 规则对象.
        editable: 是否可编辑权重.
        on_weight_change: 权重变化回调函数.
        key_prefix: 组件key前缀.
    """
    with st.container(border=True):
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"**[{rule.dimension.value}]** {rule.content}")
            if rule.explanation:
                st.caption(rule.explanation)
        with col2:
            if editable and on_weight_change:
                new_weight = st.slider(
                    "权重",
                    min_value=0,
                    max_value=100,
                    value=rule.weight,
                    key=f"{key_prefix}_{rule.id}",
                    label_visibility="collapsed",
                )
                if new_weight != rule.weight:
                    on_weight_change(rule.id, new_weight)
            else:
                st.metric("权重", rule.weight)


def progress_panel(
    current: int,
    total: int,
    label: str = "进度",
    items: list[str] | None = None,
) -> None:
    """渲染进度面板.

    Args:
        current: 当前完成数量.
        total: 总数量.
        label: 进度条标签.
        items: 已完成项目列表（可选）.
    """
    progress = current / total if total > 0 else 0.0
    st.progress(progress, text=f"{label}: {current}/{total}")
    if items:
        with st.expander(f"已完成项目 ({len(items)})"):
            for item in items:
                st.markdown(f"- {item}")


def conflict_dialog(conflicts: list[dict[str, Any]]) -> None:
    """渲染冲突对话框.

    Args:
        conflicts: 冲突列表，每项包含rule_a, rule_b, dimension.
    """
    if not conflicts:
        st.success("未检测到规则冲突")
        return

    st.warning(f"检测到 **{len(conflicts)}** 组规则冲突")
    for i, conflict in enumerate(conflicts, 1):
        with st.expander(f"冲突 #{i} — {conflict.get('dimension', '未知维度')}"):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**规则A**")
                rule_a = conflict.get("rule_a", {})
                st.info(rule_a.get("content", "N/A"))
            with col2:
                st.markdown("**规则B**")
                rule_b = conflict.get("rule_b", {})
                st.info(rule_b.get("content", "N/A"))


def validation_report(report: dict[str, Any]) -> None:
    """渲染校验报告面板.

    Args:
        report: 校验报告字典，包含score, violations, warnings, passed.
    """
    score = report.get("score", 0)
    passed = report.get("passed", False)
    violations = report.get("violations", [])
    warnings = report.get("warnings", [])

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("校验得分", f"{score}/100")
    with col2:
        st.metric("违规项", len(violations))
    with col3:
        st.metric("警告项", len(warnings))

    if passed:
        st.success("校验通过")
    else:
        st.error("校验未通过")

    if violations:
        with st.expander(f"违规详情 ({len(violations)})", expanded=True):
            for v in violations:
                st.error(
                    f"**[{v.get('dimension', '未知')}]** {v.get('content', '')}\n\n"
                    f"{v.get('message', '')}"
                )

    if warnings:
        with st.expander(f"警告详情 ({len(warnings)})"):
            for w in warnings:
                st.warning(
                    f"**[{w.get('dimension', '未知')}]** {w.get('content', '')}\n\n"
                    f"{w.get('message', '')}"
                )


def skill_info_card(skill: Any) -> None:
    """渲染Skill信息卡片.

    Args:
        skill: Skill对象.
    """
    with st.container(border=True):
        st.subheader(skill.name)
        st.caption(f"状态: {skill.status.value} | 版本: {skill.current_version}")
        if skill.description:
            st.markdown(skill.description)

        # 统计各层级规则数
        total_rules = 0
        for layer_name, rules in skill.layers.items():
            total_rules += len(rules)
        st.markdown(f"**规则总数:** {total_rules}")


def dimension_badge(dimension: str) -> str:
    """获取维度的颜色标签.

    Args:
        dimension: 维度名称.

    Returns:
        Markdown格式的彩色标签.
    """
    color_map = {
        "节奏": "blue",
        "悬念": "violet",
        "人设": "green",
        "世界观": "orange",
        "剧情架构": "red",
        "文笔话术": "gray",
        "爽点": "yellow",
        "避雷": "red",
    }
    color = color_map.get(dimension, "blue")
    return f":{color}-badge[{dimension}]"
