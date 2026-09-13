"""API configuration page."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st
import yaml

from core.constants import DEFAULT_API_CONFIG
from services.llm_client import API_CONFIG_PATH, LLMClient


def _load_config(path: Path = API_CONFIG_PATH) -> dict[str, Any]:
    """Load local API configuration."""
    if not path.exists():
        return DEFAULT_API_CONFIG.copy()
    with path.open("r", encoding="utf-8") as config_file:
        return yaml.safe_load(config_file) or DEFAULT_API_CONFIG.copy()


def _save_config(data: dict[str, Any], path: Path = API_CONFIG_PATH) -> None:
    """Save configuration atomically on the local machine."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".yaml.tmp")
    temp_path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    temp_path.replace(path)


def _provider_fields(label: str, key: str, config: dict[str, Any]) -> dict[str, Any]:
    st.subheader(label)
    base_url = st.text_input(
        "接口地址",
        value=str(config.get("base_url", "")),
        key=f"{key}_base_url",
        placeholder="https://api.openai.com/v1",
    )
    model = st.text_input(
        "模型名称",
        value=str(config.get("model", "")),
        key=f"{key}_model",
    )
    api_key = st.text_input(
        "API Key",
        value="",
        type="password",
        key=f"{key}_api_key",
        placeholder="留空则保留当前密钥",
    )
    timeout = st.number_input(
        "超时时间（秒）",
        min_value=10,
        max_value=600,
        value=int(config.get("timeout", 120)),
        key=f"{key}_timeout",
    )
    retry = config.get("retry", {})
    return {
        "provider": str(config.get("provider", "openai")),
        "base_url": base_url.strip().rstrip("/"),
        "model": model.strip(),
        "api_key": api_key.strip() or str(config.get("api_key", "")),
        "timeout": int(timeout),
        "max_retries": int(config.get("max_retries", retry.get("max_retries", 3))),
    }


def render() -> None:
    """Render API settings and connection checks."""
    st.header("API设置")
    st.caption("配置保存在本机，不会显示或上传你的密钥。支持 OpenAI 兼容接口，接口地址通常填写到 /v1，例如 https://api.openai.com/v1。")

    config = _load_config()
    with st.form("api_settings_form"):
        primary = _provider_fields("主接口", "primary", config.get("primary", {}))
        st.divider()
        backup = _provider_fields("备用接口", "backup", config.get("backup", {}))
        saved = st.form_submit_button("保存设置", type="primary")

    if saved:
        if not primary["base_url"] or not primary["model"]:
            st.error("主接口地址和模型名称不能为空。")
        else:
            _save_config({
                "primary": primary,
                "backup": backup,
                "parameters": config.get(
                    "parameters", DEFAULT_API_CONFIG["parameters"]
                ),
            })
            st.success("API 设置已保存。")

    if st.button("测试连接"):
        with st.spinner("正在验证接口和模型，通常几秒内完成..."):
            results = LLMClient().test_connection()
        for key, label in (("primary", "主接口"), ("backup", "备用接口")):
            result = results[key]
            if result.get("connected"):
                reused = "（与主接口相同，已复用检测结果）" if result.get("reused_primary") else ""
                st.success(
                    f"{label}连接成功，模型可用：{result.get('model', '')}"
                    f"，耗时 {result.get('latency_ms', 0)} 毫秒{reused}"
                )
            else:
                st.warning(f"{label}未连接：{result.get('error', '未知错误')}")
