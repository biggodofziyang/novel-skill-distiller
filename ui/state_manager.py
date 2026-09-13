"""Streamlit Session State统一封装.

提供类型安全的session_state读写接口，支持Wizard状态管理.
"""

from typing import Any

import streamlit as st


class StateManager:
    """状态管理器.

    统一封装Streamlit的session_state，提供安全的读写操作.
    """

    # 默认初始化键值
    DEFAULT_STATE: dict[str, Any] = {
        "current_page": "material",
        "uploaded_material": None,
        "cleaned_text": None,
        "analysis_results": [],
        "current_skill": None,
        "current_project": None,
        "creation_step_index": 0,
        "distill_rule_set": None,
        "feedback_samples": [],
    }

    def init_session_state(self) -> None:
        """初始化session_state默认值（幂等）."""
        for key, value in self.DEFAULT_STATE.items():
            if key not in st.session_state:
                st.session_state[key] = value

    @staticmethod
    def get(key: str, default: Any = None) -> Any:
        """获取状态值.

        Args:
            key: 状态键名.
            default: 默认值.

        Returns:
            状态值或默认值.
        """
        return st.session_state.get(key, default)

    @staticmethod
    def set(key: str, value: Any) -> None:
        """设置状态值.

        Args:
            key: 状态键名.
            value: 状态值.
        """
        st.session_state[key] = value

    @staticmethod
    def delete(key: str) -> None:
        """删除状态键.

        Args:
            key: 状态键名.
        """
        if key in st.session_state:
            del st.session_state[key]

    @staticmethod
    def has(key: str) -> bool:
        """检查状态键是否存在.

        Args:
            key: 状态键名.

        Returns:
            是否存在.
        """
        return key in st.session_state

    # ============================ Wizard状态管理 ============================

    @classmethod
    def get_wizard_step(cls, wizard_key: str) -> int:
        """获取Wizard当前步骤索引.

        Args:
            wizard_key: Wizard标识键.

        Returns:
            当前步骤索引.
        """
        return cls.get(f"{wizard_key}_step", 0)

    @classmethod
    def set_wizard_step(cls, wizard_key: str, step: int) -> None:
        """设置Wizard当前步骤索引.

        Args:
            wizard_key: Wizard标识键.
            step: 步骤索引.
        """
        cls.set(f"{wizard_key}_step", step)

    @classmethod
    def next_wizard_step(cls, wizard_key: str, max_step: int) -> None:
        """Wizard前进一步.

        Args:
            wizard_key: Wizard标识键.
            max_step: 最大步骤索引.
        """
        current = cls.get_wizard_step(wizard_key)
        if current < max_step:
            cls.set_wizard_step(wizard_key, current + 1)

    @classmethod
    def prev_wizard_step(cls, wizard_key: str) -> None:
        """Wizard后退一步.

        Args:
            wizard_key: Wizard标识键.
        """
        current = cls.get_wizard_step(wizard_key)
        if current > 0:
            cls.set_wizard_step(wizard_key, current - 1)

    @classmethod
    def reset_wizard(cls, wizard_key: str) -> None:
        """重置Wizard到第一步.

        Args:
            wizard_key: Wizard标识键.
        """
        cls.set_wizard_step(wizard_key, 0)
