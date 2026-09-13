"""分步创作页.

提供三步Wizard（世界观->人设->前三章），锁稿机制和校验报告面板.
"""

from __future__ import annotations

import streamlit as st

from core.constants import CreationStep
from core.models import CreationProject, Skill
from core.storage import StorageManager
from services.creation_engine import CreationEngine
from services.skill_manager import SkillManager
from ui.components import validation_report
from ui.state_manager import StateManager
from utils.logger import get_logger

logger = get_logger(__name__)

# 步骤定义
STEPS = [CreationStep.WORLD_BUILDING, CreationStep.CHARACTER, CreationStep.FIRST_THREE_CHAPTERS]
STEP_NAMES = [s.value for s in STEPS]
WIZARD_KEY = "creation_wizard"


def render() -> None:
    """渲染分步创作页面."""
    st.header("分步创作")
    st.markdown("按照三步流程进行创作：世界观 -> 人设 -> 前三章。每步完成后可锁稿。")

    state = StateManager()
    storage = StorageManager()
    engine = CreationEngine()
    skill_mgr = SkillManager(storage)

    # ==================== 项目选择/创建 ====================
    st.subheader("项目")
    projects = storage.list_projects()

    col1, col2 = st.columns([3, 1])
    with col1:
        project_options = ["-- 新建项目 --"] + projects
        selected = st.selectbox(
            "选择项目",
            options=project_options,
            format_func=lambda p: p.name if isinstance(p, CreationProject) else p,
        )

    with col2:
        if st.button("刷新", use_container_width=True):
            st.rerun()

    if selected == "-- 新建项目 --":
        with st.form("new_project"):
            project_name = st.text_input("项目名称")
            skills = skill_mgr.list_skills()
            skill_options = ["-- 不关联Skill --"] + skills
            selected_skill = st.selectbox(
                "选择Skill",
                options=skill_options,
                format_func=lambda s: s.name if isinstance(s, Skill) else s,
            )

            submitted = st.form_submit_button("创建项目", type="primary")
            if submitted and project_name:
                skill_id = ""
                if isinstance(selected_skill, Skill):
                    skill_id = selected_skill.id
                try:
                    project = engine.create_project(project_name, skill_id)
                    state.set("current_project", project)
                    st.success(f"项目创建成功: {project_name}")
                    st.rerun()
                except Exception as e:
                    st.error(f"创建失败: {e}")
    else:
        state.set("current_project", selected)

    project = state.get("current_project")
    if project is None:
        st.info("请创建或选择一个项目")
        return

    # 确保project是对象而非字符串
    if isinstance(project, str):
        try:
            project = engine.load_project(project)
            state.set("current_project", project)
        except Exception:
            st.error("加载项目失败")
            return

    st.markdown(f"**当前项目:** {project.name}")
    if project.skill_id:
        try:
            skill = skill_mgr.load_skill(project.skill_id)
            st.caption(f"关联Skill: {skill.name}")
        except Exception:
            st.caption("关联Skill未找到")

    # ==================== 三步Wizard ====================
    st.divider()
    current_step_idx = state.get_wizard_step(WIZARD_KEY)
    current_step = STEPS[current_step_idx]

    # 步骤指示器
    cols = st.columns(len(STEPS))
    for i, (col, step_name) in enumerate(zip(cols, STEP_NAMES)):
        with col:
            if i < current_step_idx:
                st.success(f"{i+1}. {step_name} ")
            elif i == current_step_idx:
                st.info(f"{i+1}. {step_name} ")
            else:
                st.markdown(f"{i+1}. {step_name}")

    st.progress((current_step_idx + 1) / len(STEPS))

    # 步骤内容区
    st.subheader(f"当前步骤: {current_step.value}")

    # 检查是否已锁定
    is_locked = current_step.value in project.locked_steps
    if is_locked:
        st.success(f"**{current_step.value} 已锁定**")
        locked_content = engine._storage.load_locked_snapshot(project.id, current_step.value)
        st.text_area(
            "locked_content",
            value=locked_content,
            height=400,
            disabled=True,
            label_visibility="collapsed",
        )
    else:
        # 生成/编辑内容
        user_prompt = st.text_area(
            "补充要求（可选）",
            placeholder="输入对当前步骤的特殊要求...",
            height=80,
        )

        if st.button("生成内容", type="primary"):
            if not project.skill_id:
                st.warning("当前项目未关联Skill，生成质量可能受限")

            with st.spinner("正在生成内容..."):
                try:
                    skill = skill_mgr.load_skill(project.skill_id) if project.skill_id else None
                    if skill is None:
                        skill = Skill(name="默认Skill", description="")

                    content = engine.generate_step(project, skill, current_step, user_prompt)
                    st.rerun()
                except Exception as e:
                    st.error(f"生成失败: {e}")
                    logger.error("内容生成失败: %s", e)

        # 显示/编辑当前内容
        current_content = project.step_contents.get(current_step.value, "")
        edited_content = st.text_area(
            "内容编辑",
            value=current_content,
            height=400,
            placeholder="点击「生成内容」自动生成，或在此手动输入...",
        )

        if edited_content != current_content:
            project.step_contents[current_step.value] = edited_content
            storage.save_project(project)

        # 校验按钮
        if current_content:
            if st.button("校验内容"):
                with st.spinner("正在校验..."):
                    try:
                        skill = skill_mgr.load_skill(project.skill_id) if project.skill_id else None
                        if skill is None:
                            skill = Skill(name="默认Skill", description="")

                        report = engine.validate_content(current_content, skill, current_step)
                        project.validation_reports[current_step.value] = report
                        storage.save_project(project)
                        st.rerun()
                    except Exception as e:
                        st.error(f"校验失败: {e}")

        # 显示校验报告
        report = project.validation_reports.get(current_step.value)
        if report:
            st.divider()
            st.subheader("校验报告")
            validation_report(report)

        # 锁稿按钮
        st.divider()
        if st.button("锁定本步骤", type="primary"):
            try:
                engine.lock_step(project, current_step)
                state.set("current_project", project)
                st.success(f"{current_step.value} 已锁定！")
                st.rerun()
            except Exception as e:
                st.error(f"锁稿失败: {e}")

    # 导航按钮
    st.divider()
    nav_cols = st.columns(3)
    with nav_cols[0]:
        if current_step_idx > 0:
            if st.button("上一步", use_container_width=True):
                state.prev_wizard_step(WIZARD_KEY)
                st.rerun()
    with nav_cols[1]:
        if st.button("重置Wizard", use_container_width=True):
            state.reset_wizard(WIZARD_KEY)
            st.rerun()
    with nav_cols[2]:
        if current_step_idx < len(STEPS) - 1:
            if st.button("下一步", use_container_width=True):
                if current_step.value not in project.locked_steps:
                    st.warning("请先锁定当前步骤，再进入下一步。")
                else:
                    state.next_wizard_step(WIZARD_KEY, len(STEPS) - 1)
                    st.rerun()
        elif current_step_idx == len(STEPS) - 1:
            st.button("已完成", disabled=True, use_container_width=True)
