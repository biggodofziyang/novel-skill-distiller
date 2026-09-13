"""LLM客户端.

提供统一的LLM调用接口，支持主备API切换、指数退避重试、
请求缓存和连接测试功能.
"""

from __future__ import annotations

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import requests
import yaml

from core.constants import (
    DEFAULT_API_CONFIG,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_TOP_P,
    RETRY_BASE_DELAY_SECONDS,
)
from core.models import ApiConfig, LLMRequest, LLMResponse, RetryConfig
from utils.logger import get_logger

logger = get_logger(__name__)

API_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "api_config.yaml"
CONNECTION_TEST_TIMEOUT_SECONDS = 12


class LLMClient:
    """LLM统一客户端.

    封装对OpenAI兼容API的调用，支持主备切换和指数退避重试.
    对相同提示词提供内存缓存，减少重复调用.
    """

    def __init__(self, config_path: Path | str | None = None) -> None:
        """初始化LLM客户端.

        Args:
            config_path: API配置文件路径，默认使用项目config目录下的api_config.yaml.
        """
        self._config_path = Path(config_path) if config_path else API_CONFIG_PATH
        self._primary: ApiConfig | None = None
        self._backup: ApiConfig | None = None
        self._parameters: dict[str, Any] = {}
        self._cache: dict[str, LLMResponse] = {}
        self._load_config()

    def _load_config(self) -> None:
        """加载API配置文件."""
        try:
            if self._config_path.exists():
                with open(self._config_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                self._primary = ApiConfig.model_validate(data.get("primary", DEFAULT_API_CONFIG["primary"]))
                self._backup = ApiConfig.model_validate(data.get("backup", DEFAULT_API_CONFIG["backup"]))
                self._parameters = data.get("parameters", {
                    "temperature": DEFAULT_TEMPERATURE,
                    "top_p": DEFAULT_TOP_P,
                })
                logger.info("加载API配置成功")
            else:
                logger.warning("API配置文件不存在，使用默认配置")
                self._primary = ApiConfig.model_validate(DEFAULT_API_CONFIG["primary"])
                self._backup = ApiConfig.model_validate(DEFAULT_API_CONFIG["backup"])
                self._parameters = DEFAULT_API_CONFIG["parameters"]
        except Exception as e:
            logger.error("加载API配置失败: %s", e)
            self._primary = ApiConfig.model_validate(DEFAULT_API_CONFIG["primary"])
            self._backup = ApiConfig.model_validate(DEFAULT_API_CONFIG["backup"])
            self._parameters = DEFAULT_API_CONFIG["parameters"]

    @staticmethod
    def _make_hash(*parts: Any) -> str:
        """生成提示词的哈希值，用于缓存键.

        Args:
            prompt: 提示词内容.

        Returns:
            MD5哈希字符串.
        """
        payload = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.md5(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        """Normalize an OpenAI-compatible base URL to include the API version path."""
        normalized = (base_url or "").strip().rstrip("/")
        if not normalized:
            return normalized
        try:
            from urllib.parse import urlsplit, urlunsplit
            parts = urlsplit(normalized)
            if parts.scheme and parts.netloc and parts.path in {"", "/"}:
                return urlunsplit((parts.scheme, parts.netloc, "/v1", parts.query, parts.fragment)).rstrip("/")
        except ValueError:
            return normalized
        return normalized

    @staticmethod
    def _response_detail(response: Any) -> str:
        """Extract a short, non-secret diagnostic from an API response."""
        try:
            data = response.json()
        except (ValueError, json.JSONDecodeError):
            data = None
        if isinstance(data, dict):
            error = data.get("error")
            if isinstance(error, dict):
                message = error.get("message") or error.get("code")
                if message:
                    return str(message)[:300]
            if error:
                return str(error)[:300]
            if data.get("message"):
                return str(data["message"])[:300]
        raw = getattr(response, "text", "")
        if isinstance(raw, str):
            raw = " ".join(raw.strip().split())
            return raw[:300]
        return ""
    def _call_api(self, config: ApiConfig, request: LLMRequest) -> LLMResponse:
        """执行单次API调用.

        Args:
            config: API配置.
            request: LLM请求对象.

        Returns:
            LLM响应对象.
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.api_key}",
        }
        payload: dict[str, Any] = {
            "model": config.model,
            "messages": [],
            "temperature": request.temperature,
            "top_p": request.top_p,
        }
        if request.system_message:
            payload["messages"].append({"role": "system", "content": request.system_message})
        payload["messages"].append({"role": "user", "content": request.prompt})
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens

        start_time = time.time()
        try:
            response = requests.post(
                f"{self._normalize_base_url(config.base_url)}/chat/completions",
                headers=headers,
                json=payload,
                timeout=config.timeout,
            )
            response.raise_for_status()
            try:
                result = response.json()
            except (ValueError, json.JSONDecodeError):
                detail = self._response_detail(response) or "空响应"
                return LLMResponse(
                    success=False,
                    error_message=(
                        f"接口返回的不是 JSON（HTTP {response.status_code}）：{detail}。"
                        "请检查接口地址是否包含 /v1。"
                    ),
                    latency_ms=int((time.time() - start_time) * 1000),
                )
            latency_ms = int((time.time() - start_time) * 1000)
            if not isinstance(result, dict):
                return LLMResponse(
                    success=False,
                    error_message="接口返回格式不是 JSON 对象，请检查接口类型。",
                    latency_ms=latency_ms,
                )

            content = ""
            choices = result.get("choices")
            if isinstance(choices, list) and choices:
                choice = choices[0]
                message = choice.get("message", {}) if isinstance(choice, dict) else {}
                content = message.get("content", "") if isinstance(message, dict) else ""
                if isinstance(content, list):
                    content = "".join(
                        str(part.get("text", "")) if isinstance(part, dict) else str(part)
                        for part in content
                    )
            if not isinstance(content, str) or not content.strip():
                return LLMResponse(
                    success=False,
                    error_message="接口返回成功但没有可用的 choices 内容，请检查模型名称和接口兼容性。",
                    raw_response=result,
                    latency_ms=latency_ms,
                )

            token_usage = result.get("usage", {})
            if isinstance(token_usage, dict):
                token_usage = {
                    "prompt_tokens": token_usage.get("prompt_tokens", 0),
                    "completion_tokens": token_usage.get("completion_tokens", 0),
                    "total_tokens": token_usage.get("total_tokens", 0),
                }

            logger.info(
                "API调用成功: model=%s, latency=%dms, tokens=%s",
                config.model,
                latency_ms,
                token_usage.get("total_tokens", 0),
            )
            return LLMResponse(
                success=True,
                content=content,
                raw_response=result,
                latency_ms=latency_ms,
                token_usage=token_usage,
            )
        except requests.exceptions.Timeout:
            logger.error("API调用超时: model=%s, timeout=%d", config.model, config.timeout)
            return LLMResponse(
                success=False,
                error_message=f"请求超时({config.timeout}s)",
                latency_ms=int((time.time() - start_time) * 1000),
            )
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else "unknown"
            detail = self._response_detail(e.response) if e.response is not None else ""
            logger.error("API调用HTTP错误: model=%s, status=%s", config.model, status)
            suffix = f" - {detail}" if detail else ""
            return LLMResponse(
                success=False,
                error_message=f"HTTP错误: {status}{suffix}",
                latency_ms=int((time.time() - start_time) * 1000),
            )
        except Exception as e:
            logger.error("API调用异常: model=%s, error=%s", config.model, e)
            return LLMResponse(
                success=False,
                error_message=str(e),
                latency_ms=int((time.time() - start_time) * 1000),
            )

    def _call_with_retry(self, config: ApiConfig, request: LLMRequest) -> LLMResponse:
        """带指数退避重试的API调用.

        重试延迟默认是 1s -> 3s -> 9s（可在配置中覆盖）

        Args:
            config: API配置.
            request: LLM请求对象.

        Returns:
            LLM响应对象.
        """
        max_retries = config.retry.max_retries
        base_delay = config.retry.base_delay
        multiplier = config.retry.backoff_multiplier

        last_error = ""
        for attempt in range(max_retries + 1):
            result = self._call_api(config, request)
            if result.success:
                return result
            last_error = result.error_message
            if attempt < max_retries:
                delay = base_delay * (multiplier ** attempt)
                logger.warning(
                    "API调用失败，第%d次重试，等待%.1f秒: %s",
                    attempt + 1,
                    delay,
                    last_error,
                )
                time.sleep(delay)

        logger.error("API调用最终失败，已重试%d次: %s", max_retries, last_error)
        return LLMResponse(success=False, error_message=last_error)

    def chat(self, request: LLMRequest, use_cache: bool = True) -> LLMResponse:
        """发送聊天请求，自动处理主备切换和缓存.

        Args:
            request: LLM请求对象.
            use_cache: 是否使用缓存.

        Returns:
            LLM响应对象.
        """
        cache_key = self._make_hash(
            request.prompt,
            request.system_message,
            request.temperature,
            request.top_p,
            request.max_tokens,
        )
        if use_cache and cache_key in self._cache:
            logger.debug("命中缓存")
            return self._cache[cache_key]

        # 尝试主API
        if self._primary and self._primary.api_key:
            result = self._call_with_retry(self._primary, request)
            if result.success:
                if use_cache:
                    self._cache[cache_key] = result
                return result
            logger.warning("主API调用失败，尝试备用API")
        else:
            logger.warning("主API未配置，尝试备用API")

        # 尝试备用API
        if self._backup and self._backup.api_key:
            result = self._call_with_retry(self._backup, request)
            if result.success:
                if use_cache:
                    self._cache[cache_key] = result
                return result
            logger.error("备用API调用也失败")
        else:
            logger.error("备用API未配置")

        return LLMResponse(
            success=False,
            error_message="主备API均调用失败，请检查配置和网络连接",
        )

    def _test_provider(self, config: ApiConfig) -> dict[str, Any]:
        """Quickly verify an endpoint, API key, and configured model."""
        timeout = min(config.timeout, CONNECTION_TEST_TIMEOUT_SECONDS)
        started_at = time.time()
        base_result: dict[str, Any] = {
            "connected": False,
            "model": config.model,
            "model_available": False,
            "latency_ms": 0,
            "error": "",
        }

        try:
            response = requests.get(
                f"{self._normalize_base_url(config.base_url)}/models",
                headers={"Authorization": f"Bearer {config.api_key}"},
                timeout=timeout,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
                raise ValueError("模型列表格式不正确")

            model_ids = {
                item["id"]
                for item in payload["data"]
                if isinstance(item, dict)
                and isinstance(item.get("id"), str)
                and item["id"]
            }
            model_available = config.model in model_ids
            base_result.update(
                {
                    "connected": model_available,
                    "model_available": model_available,
                    "model_count": len(model_ids),
                    "error": (
                        ""
                        if model_available
                        else f"接口连接成功，但模型 {config.model} 不在可用模型列表中"
                    ),
                }
            )
        except requests.exceptions.Timeout:
            base_result["error"] = f"连接测试超时（{timeout}秒）"
        except requests.exceptions.HTTPError as exc:
            response = exc.response
            status = response.status_code if response is not None else "未知"
            detail = self._response_detail(response) if response is not None else ""
            suffix = f"：{detail}" if detail else ""
            base_result["error"] = f"接口返回 HTTP {status}{suffix}"
        except (ValueError, json.JSONDecodeError) as exc:
            base_result["error"] = f"接口返回的数据无法识别：{exc}"
        except requests.exceptions.RequestException as exc:
            base_result["error"] = f"连接失败：{exc}"
        except Exception as exc:
            logger.exception("连接测试异常: model=%s", config.model)
            base_result["error"] = f"连接测试异常：{exc}"
        finally:
            base_result["latency_ms"] = int((time.time() - started_at) * 1000)

        return base_result

    def test_connection(self) -> dict[str, Any]:
        """Test both providers without starting a text generation request."""
        result: dict[str, Any] = {"primary": {}, "backup": {}}
        configs = {"primary": self._primary, "backup": self._backup}
        ready: dict[str, ApiConfig] = {}

        for name, config in configs.items():
            if not config or not config.api_key:
                result[name] = {
                    "connected": False,
                    "model": config.model if config else "",
                    "model_available": False,
                    "error": "未配置API Key",
                }
                continue
            ready[name] = config

        if "primary" in ready and "backup" in ready:
            primary_signature = (
                self._normalize_base_url(ready["primary"].base_url),
                ready["primary"].model,
                ready["primary"].api_key,
            )
            backup_signature = (
                self._normalize_base_url(ready["backup"].base_url),
                ready["backup"].model,
                ready["backup"].api_key,
            )
            if primary_signature == backup_signature:
                provider_result = self._test_provider(ready["primary"])
                result["primary"] = provider_result
                result["backup"] = {
                    **provider_result,
                    "reused_primary": True,
                }
                return result

        if ready:
            with ThreadPoolExecutor(max_workers=len(ready)) as executor:
                futures = {
                    executor.submit(self._test_provider, config): name
                    for name, config in ready.items()
                }
                for future in as_completed(futures):
                    name = futures[future]
                    try:
                        result[name] = future.result()
                    except Exception as exc:
                        result[name] = {
                            "connected": False,
                            "model": ready[name].model,
                            "model_available": False,
                            "error": f"连接测试异常：{exc}",
                        }

        return result

    def clear_cache(self) -> None:
        """清空请求缓存."""
        self._cache.clear()
        logger.info("LLM缓存已清空")

    def get_cache_stats(self) -> dict[str, int]:
        """获取缓存统计信息.

        Returns:
            包含缓存条目数的字典.
        """
        return {"cached_entries": len(self._cache)}

