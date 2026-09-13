"""Skill管理页.

提供Skill仓库卡片网格、编辑页三层结构标签页、组合页权重滑动条.
"""

from __future__ import annotations

import streamlit as st

from core.constants import SkillLayer, SkillStatus
from core.models import RuleSet, Skill
from core.storage import StorageManager
from services.skill_manager import SkillManager
from ui.components import skill_info_card
from ui.state_manager import StateManager
from utils.logger import get_logger

logger = get_logger(__name__)


def render() -> None:
    """渲染Skill管理页面."""
    st.header("Skill管理")
    st.markdown("管理创作Skill，支持编辑规则权重、组合多个Skill、版本回滚。")

    state = StateManager()
    storage = StorageManager()
    skill_mgr = SkillManager(storage)

    # ==================== 页面切换标签 ====================
    tab_list = ["Skill仓库", "创建Skill", "组合Skill"]
    tabs = st.tabs(tab_list)

    # ==================== Skill仓库标签 ====================
    with tabs[0]:
        _render_skill_repo(skill_mgr, state)

    # ==================== 创建Skill标签 ====================
    with tabs[1]:
        _render_create_skill(skill_mgr, storage)

    # ==================== 组合Skill标签 ====================
    with tabs[2]:
        _render_combine_skills(skill_mgr)


def _render_skill_repo(skill_mgr: SkillManager, state: StateManager) -> None:
    """渲染Skill仓库.

    Args:
        skill_mgr: Skill管理器.
        state: 状态管理器.
    """
    skills = skill_mgr.list_skills()
    if not skills:
        st.info("暂无Skill，请先在「创建Skill」标签页创建")
        return

    # 卡片网格
    cols = st.columns(3)
    for i, skill in enumerate(skills):
        with cols[i % 3]:
            skill_info_card(skill)
            if st.button("编辑", key=f"edit_{skill.id}", use_container_width=True):
                state.set("editing_skill_id", skill.id)
                st.rerun()

    # 编辑模式
    editing_id = state.get("editing_skill_id")
    if editing_id:
        try:
            skill = skill_mgr.load_skill(editing_id)
            _render_skill_editor(skill_mgr, skill, state)
        except Exception as e:
            st.error(f"加载Skill失败: {e}")
            state.delete("editing_skill_id")


def _render_skill_editor(skill_mgr: SkillManager, skill: Skill, state: StateManager) -> None:
    """渲染Skill编辑器.

    Args:
        skill_mgr: Skill管理器.
        skill: 正在编辑的Skill.
        state: 状态管理器.
    """
    st.divider()
    st.subheader(f"编辑Skill: {skill.name}")

    # 基本信息
    new_name = st.text_input("Skill名称", value=skill.name, key=f"skill_name_{skill.id}")
    new_desc = st.text_area("描述", value=skill.description, key=f"skill_desc_{skill.id}")

    if st.button("更新基本信息", key=f"update_basic_{skill.id}"):
        skill.name = new_name
        skill.description = new_desc
        skill_mgr.save_skill(skill)
        st.success("基本信息已更新")
        st.rerun()

    # 三层结构标签页
    layer_tabs = st.tabs([SkillLayer.BASE.value, SkillLayer.MIDDLE.value, SkillLayer.DYNAMIC.value])
    layer_enums = [SkillLayer.BASE, SkillLayer.MIDDLE, SkillLayer.DYNAMIC]

    for tab, layer in zip(layer_tabs, layer_enums):
        with tab:
            rules = skill.layers.get(layer.value, [])
            st.markdown(f"**{layer.value}** 共 {len(rules)} 条规则")

            for rule in rules:
                with st.container(border=True):
                    cols = st.columns([3, 1, 1])
                    cols[0].markdown(f"[{rule.dimension.value}] {rule.content}")

                    new_weight = cols[1].number_input(
                        "权重",
                        min_value=0,
                        max_value=100,
                        value=rule.weight,
                        key=f"weight_{skill.id}_{rule.id}",
                        label_visibility="collapsed",
                    )
                    if new_weight != rule.weight:
                        rule.weight = new_weight
                        skill_mgr.save_skill(skill)
                        st.toast(f"权重已更新: {new_weight}")

                    if cols[2].button("删除", key=f"del_{skill.id}_{rule.id}"):
                        skill.layers[layer.value] = [r for r in rules if r.id != rule.id]
                        skill_mgr.save_skill(skill)
                        st.rerun()

    # 版本管理
    st.divider()
    st.subheader("版本管理")
    if skill.versions:
        version_options = [v.version for v in skill.versions]
        selected_version = st.selectbox("版本历史", version_options)
        selected = next((v for v in skill.versions if v.version == selected_version), None)
        if selected:
            st.caption(f"变更: {selected.changelog}")
            st.caption(f"创建时间: {selected.created_at}")

        if st.button("回滚到选中版本"):
            try:
                skill_mgr.rollback_version(skill, selected_version)
                skill_mgr.save_skill(skill)
                st.success(f"已回滚到版本 {selected_version}")
                st.rerun()
            except Exception as e:
                st.error(f"回滚失败: {e}")

    # 升级版本
    changelog = st.text_input("版本变更说明", placeholder="描述本次修改内容")
    if st.button("升级版本"):
        skill_mgr.bump_version(skill, changelog)
        skill_mgr.save_skill(skill)
        st.success(f"已升级至版本 {skill.current_version}")
        st.rerun()

    if st.button("关闭编辑"):
        state.delete("editing_skill_id")
        st.rerun()


def _render_create_skill(skill_mgr: SkillManager, storage: StorageManager) -> None:
    """渲染创建Skill页面.

    Args:
        skill_mgr: Skill管理器.
        storage: 存储管理器.
    """
    st.subheader("从规则集创建Skill")

    rule_sets = storage.list_rule_sets()
    if not rule_sets:
        st.warning("暂无规则集，请先在「规则蒸馏」页生成规则集")
        return

    selected = st.selectbox(
        "选择规则集",
        options=rule_sets,
        format_func=lambda r: f"{r.name} ({sum(len(v) for v in r.rules.values())}条规则)",
    )

    skill_name = st.text_input("Skill名称", value=f"{selected.name}_Skill")
    skill_desc = st.text_area("Skill描述", placeholder="描述这个Skill的适用场景和特点")

    if st.button("创建Skill", type="primary"):
        try:
            skill = skill_mgr.create_skill(
                rule_set=selected,
                name=skill_name,
                description=skill_desc,
            )
            skill_mgr.save_skill(skill)
            st.success(f"Skill创建成功: {skill.name}")
            logger.info("通过UI创建Skill: %s", skill.name)
        except Exception as e:
            st.error(f"创建失败: {e}")
            logger.error("Skill创建失败: %s", e)


def _render_combine_skills(skill_mgr: SkillManager) -> None:
    """渲染组合Skill页面.

    Args:
        skill_mgr: Skill管理器.
    """
    st.subheader("组合多个Skill")

    skills = skill_mgr.list_skills()
    if len(skills) < 2:
        st.warning("需要至少2个Skill才能进行组合")
        return

    st.markdown("选择要组合的Skill并设置权重")

    selected_skills: list[Skill] = []
    weights: list[float] = []

    for skill in skills:
        col1, col2 = st.columns([3, 1])
        with col1:
            checked = st.checkbox(f"{skill.name} (v{skill.current_version})", key=f"combine_{skill.id}")
        with col2:
            weight = st.slider(
                "权重",
                min_value=0.0,
                max_value=1.0,
                value=0.5,
                step=0.05,
                key=f"weight_{skill.id}",
                label_visibility="collapsed",
            )
        if checked:
            selected_skills.append(skill)
            weights.append(weight)

    if len(selected_skills) >= 2:
        # 归一化权重
        total = sum(weights)
        if total > 0:
            normalized = [w / total for w in weights]
        else:
            normalized = [1.0 / len(weights)] * len(weights)

        st.markdown("**归一化权重:**")
        for skill, w in zip(selected_skills, normalized):
            st.markdown(f"- {skill.name}: {w:.2%}")

        combined_name = st.text_input("组合后Skill名称", value="组合Skill")
        combined_desc = st.text_area("组合描述")

        if st.button("执行组合", type="primary"):
            try:
                combined = skill_mgr.combine_skills(
                    skills=selected_skills,
                    weights=normalized,
                    name=combined_name,
                    description=combined_desc,
                )
                skill_mgr.save_skill(combined)
                st.success(f"组合Skill创建成功: {combined.name}")
                logger.info("组合Skill创建: %s", combined.name)
            except Exception as e:
                st.error(f"组合失败: {e}")
                logger.error("Skill组合失败: %s", e)
    else:
        st.info("请至少选择2个Skill")
