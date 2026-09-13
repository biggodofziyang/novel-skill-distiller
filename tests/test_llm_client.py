"""Tests for services.llm_client module."""

import time
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests
import yaml

from core.models import ApiConfig, LLMRequest, LLMResponse
from services.llm_client import LLMClient


@pytest.fixture
def mock_config_path(tmp_path):
    """Create a temporary API config file."""
    config = {
        "primary": {
            "provider": "openai",
            "base_url": "https://api.test.com/v1",
            "api_key": "sk-test-primary",
            "model": "gpt-4o",
            "timeout": 30,
            "max_retries": 2,
        },
        "backup": {
            "provider": "openai",
            "base_url": "https://api.backup.com/v1",
            "api_key": "sk-test-backup",
            "model": "gpt-4o-mini",
            "timeout": 30,
            "max_retries": 2,
        },
        "parameters": {
            "temperature": 0.7,
            "top_p": 0.9,
        },
    }
    path = tmp_path / "api_config.yaml"
    path.write_text(yaml.dump(config), encoding="utf-8")
    return path


@pytest.fixture
def client_with_config(mock_config_path):
    return LLMClient(config_path=mock_config_path)


class TestInit:
    """Tests for LLMClient initialization."""

    def test_init_with_config_path(self, mock_config_path):
        client = LLMClient(config_path=mock_config_path)
        assert client._primary is not None
        assert client._primary.api_key == "sk-test-primary"
        assert client._backup is not None
        assert client._backup.api_key == "sk-test-backup"

    def test_init_without_config_uses_default(self, tmp_path, monkeypatch):
        # Patch the default config path to a non-existent file
        monkeypatch.setattr(
            "services.llm_client.API_CONFIG_PATH",
            tmp_path / "nonexistent.yaml",
        )
        client = LLMClient()
        assert client._primary is not None
        assert client._primary.model == "gpt-4o"
        assert client._backup is not None
        assert client._backup.model == "gpt-4o-mini"

    def test_init_creates_empty_cache(self, mock_config_path):
        client = LLMClient(config_path=mock_config_path)
        assert client._cache == {}


class TestMakeHash:
    """Tests for prompt hashing."""

    def test_same_prompt_same_hash(self, client_with_config):
        h1 = client_with_config._make_hash("test prompt")
        h2 = client_with_config._make_hash("test prompt")
        assert h1 == h2

    def test_different_prompt_different_hash(self, client_with_config):
        h1 = client_with_config._make_hash("prompt one")
        h2 = client_with_config._make_hash("prompt two")
        assert h1 != h2

    def test_hash_is_md5_format(self, client_with_config):
        h = client_with_config._make_hash("test")
        assert len(h) == 32
        assert all(c in "0123456789abcdef" for c in h)


class TestCallApi:
    """Tests for _call_api method."""

    def test_successful_call(self, client_with_config):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        mock_response.raise_for_status.return_value = None

        with patch("services.llm_client.requests.post", return_value=mock_response):
            request = LLMRequest(prompt="Hi", system_message="Be helpful")
            result = client_with_config._call_api(client_with_config._primary, request)

        assert result.success is True
        assert result.content == "Hello"
        assert result.token_usage["total_tokens"] == 15
        assert result.latency_ms >= 0

    def test_successful_call_without_system_message(self, client_with_config):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Response"}}],
            "usage": {},
        }
        mock_response.raise_for_status.return_value = None

        with patch("services.llm_client.requests.post", return_value=mock_response):
            request = LLMRequest(prompt="Hi")
            result = client_with_config._call_api(client_with_config._primary, request)

        assert result.success is True
        assert result.content == "Response"

    def test_timeout_error(self, client_with_config):
        with patch(
            "services.llm_client.requests.post",
            side_effect=requests.exceptions.Timeout(),
        ):
            request = LLMRequest(prompt="Hi")
            result = client_with_config._call_api(client_with_config._primary, request)

        assert result.success is False
        assert "超时" in result.error_message or "timeout" in result.error_message.lower()

    def test_http_error(self, client_with_config):
        mock_response = MagicMock()
        mock_response.status_code = 429
        http_error = requests.exceptions.HTTPError("Rate limited")
        http_error.response = mock_response

        with patch(
            "services.llm_client.requests.post",
            side_effect=http_error,
        ):
            request = LLMRequest(prompt="Hi")
            result = client_with_config._call_api(client_with_config._primary, request)

        assert result.success is False
        assert "HTTP" in result.error_message or "429" in result.error_message

    def test_generic_exception(self, client_with_config):
        with patch(
            "services.llm_client.requests.post",
            side_effect=Exception("Network error"),
        ):
            request = LLMRequest(prompt="Hi")
            result = client_with_config._call_api(client_with_config._primary, request)

        assert result.success is False
        assert "Network error" in result.error_message

    def test_empty_choices(self, client_with_config):
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [], "usage": {}}
        mock_response.raise_for_status.return_value = None

        with patch("services.llm_client.requests.post", return_value=mock_response):
            request = LLMRequest(prompt="Hi")
            result = client_with_config._call_api(client_with_config._primary, request)

        assert result.success is False
        assert "没有可用的 choices" in result.error_message

    def test_max_tokens_in_payload(self, client_with_config):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "OK"}}],
            "usage": {},
        }
        mock_response.raise_for_status.return_value = None

        with patch("services.llm_client.requests.post", return_value=mock_response) as mock_post:
            request = LLMRequest(prompt="Hi", max_tokens=100)
            client_with_config._call_api(client_with_config._primary, request)

        call_args = mock_post.call_args
        payload = call_args.kwargs["json"]
        assert payload["max_tokens"] == 100


    def test_non_json_response_has_actionable_error(self, client_with_config):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("not json")
        mock_response.text = "<html>gateway error</html>"
        mock_response.raise_for_status.return_value = None

        with patch("services.llm_client.requests.post", return_value=mock_response):
            result = client_with_config._call_api(client_with_config._primary, LLMRequest(prompt="Hi"))

        assert result.success is False
        assert "不是 JSON" in result.error_message
        assert "gateway error" in result.error_message

    def test_root_base_url_uses_v1_chat_endpoint(self, client_with_config):
        client_with_config._primary.base_url = "https://api.example.com"
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "OK"}}], "usage": {}}
        mock_response.raise_for_status.return_value = None

        with patch("services.llm_client.requests.post", return_value=mock_response) as mock_post:
            client_with_config._call_api(client_with_config._primary, LLMRequest(prompt="Hi"))

        assert mock_post.call_args.args[0] == "https://api.example.com/v1/chat/completions"

    def test_normalize_base_url_preserves_existing_path(self):
        assert LLMClient._normalize_base_url("https://api.example.com/v1/") == "https://api.example.com/v1"
        assert LLMClient._normalize_base_url("https://api.example.com") == "https://api.example.com/v1"

class TestCallWithRetry:
    """Tests for _call_with_retry method."""

    def test_success_on_first_attempt(self, client_with_config):
        with patch.object(
            client_with_config,
            "_call_api",
            return_value=LLMResponse(success=True, content="Success"),
        ):
            request = LLMRequest(prompt="Hi")
            result = client_with_config._call_with_retry(client_with_config._primary, request)

        assert result.success is True
        assert result.content == "Success"

    def test_retry_then_success(self, client_with_config):
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return LLMResponse(success=False, error_message="Temporary error")
            return LLMResponse(success=True, content="Success")

        with patch.object(client_with_config, "_call_api", side_effect=side_effect):
            with patch("services.llm_client.time.sleep") as mock_sleep:
                request = LLMRequest(prompt="Hi")
                result = client_with_config._call_with_retry(
                    client_with_config._primary, request
                )

        assert result.success is True
        assert call_count == 3
        assert mock_sleep.call_count == 2  # Retries after 1st and 2nd failure

    def test_all_retries_exhausted(self, client_with_config):
        with patch.object(
            client_with_config,
            "_call_api",
            return_value=LLMResponse(success=False, error_message="Persistent error"),
        ):
            with patch("services.llm_client.time.sleep"):
                request = LLMRequest(prompt="Hi")
                result = client_with_config._call_with_retry(
                    client_with_config._primary, request
                )

        assert result.success is False
        assert "Persistent error" in result.error_message

    def test_retry_backoff_delays(self, client_with_config):
        delays = []

        def capture_delay(d):
            delays.append(d)

        with patch.object(
            client_with_config,
            "_call_api",
            return_value=LLMResponse(success=False, error_message="Error"),
        ):
            with patch("services.llm_client.time.sleep", side_effect=capture_delay):
                request = LLMRequest(prompt="Hi")
                client_with_config._call_with_retry(client_with_config._primary, request)

        # Primary config has max_retries=2, so attempts = 3, sleeps = 2
        # base_delay=1, multiplier=3: delays = 1*3^0=1, 1*3^1=3
        assert len(delays) == 2
        assert delays[0] == 1.0
        assert delays[1] == 3.0


class TestChat:
    """Tests for chat method with caching and failover."""

    def test_primary_success_no_cache(self, client_with_config):
        with patch.object(
            client_with_config,
            "_call_with_retry",
            return_value=LLMResponse(success=True, content="Primary"),
        ) as mock_call:
            request = LLMRequest(prompt="Test")
            result = client_with_config.chat(request, use_cache=True)

        assert result.success is True
        assert result.content == "Primary"
        mock_call.assert_called_once()

    def test_cache_hit(self, client_with_config):
        request = LLMRequest(prompt="Cached prompt")
        cached = LLMResponse(success=True, content="Cached")
        cache_key = client_with_config._make_hash(request.prompt, request.system_message, request.temperature, request.top_p, request.max_tokens)
        client_with_config._cache[cache_key] = cached

        with patch.object(client_with_config, "_call_with_retry") as mock_call:
            result = client_with_config.chat(request, use_cache=True)

        assert result.content == "Cached"
        mock_call.assert_not_called()

    def test_cache_disabled(self, client_with_config):
        request = LLMRequest(prompt="No cache")
        cache_key = client_with_config._make_hash(request.prompt, request.system_message, request.temperature, request.top_p, request.max_tokens)
        client_with_config._cache[cache_key] = LLMResponse(success=True, content="Cached")

        with patch.object(
            client_with_config,
            "_call_with_retry",
            return_value=LLMResponse(success=True, content="Fresh"),
        ):
            result = client_with_config.chat(request, use_cache=False)

        assert result.content == "Fresh"

    def test_primary_fails_backup_succeeds(self, client_with_config):
        def side_effect(config, request):
            if config.api_key == "sk-test-primary":
                return LLMResponse(success=False, error_message="Primary down")
            return LLMResponse(success=True, content="Backup")

        with patch.object(client_with_config, "_call_with_retry", side_effect=side_effect):
            request = LLMRequest(prompt="Test")
            result = client_with_config.chat(request)

        assert result.success is True
        assert result.content == "Backup"

    def test_both_apis_fail(self, client_with_config):
        with patch.object(
            client_with_config,
            "_call_with_retry",
            return_value=LLMResponse(success=False, error_message="Down"),
        ):
            request = LLMRequest(prompt="Test")
            result = client_with_config.chat(request)

        assert result.success is False
        assert "主备API均调用失败" in result.error_message

    def test_primary_no_api_key(self, client_with_config):
        client_with_config._primary.api_key = ""

        with patch.object(
            client_with_config,
            "_call_with_retry",
            return_value=LLMResponse(success=True, content="Backup only"),
        ) as mock_call:
            request = LLMRequest(prompt="Test")
            result = client_with_config.chat(request)

        assert result.success is True
        # Should skip primary and try backup
        assert mock_call.call_count == 1

    def test_caches_successful_result(self, client_with_config):
        with patch.object(
            client_with_config,
            "_call_with_retry",
            return_value=LLMResponse(success=True, content="Result"),
        ):
            request = LLMRequest(prompt="Cache me")
            client_with_config.chat(request, use_cache=True)

        cache_key = client_with_config._make_hash(request.prompt, request.system_message, request.temperature, request.top_p, request.max_tokens)
        assert cache_key in client_with_config._cache
        assert client_with_config._cache[cache_key].content == "Result"


class TestTestConnection:
    """Tests for test_connection method."""

    def test_primary_connected(self, client_with_config):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "data": [{"id": "gpt-4o"}, {"id": "gpt-4o-mini"}]
        }
        response.raise_for_status.return_value = None

        with patch("services.llm_client.requests.get", return_value=response):
            result = client_with_config.test_connection()

        assert result["primary"]["connected"] is True
        assert result["primary"]["model_available"] is True

    def test_primary_disconnected(self, client_with_config):
        with patch(
            "services.llm_client.requests.get",
            side_effect=requests.exceptions.ConnectionError("offline"),
        ):
            result = client_with_config.test_connection()

        assert result["primary"]["connected"] is False
        assert "offline" in result["primary"]["error"]

    def test_no_api_key(self, client_with_config):
        client_with_config._primary.api_key = ""
        client_with_config._backup.api_key = ""

        result = client_with_config.test_connection()
        assert result["primary"]["connected"] is False
        assert "未配置API Key" in result["primary"]["error"]
        assert result["backup"]["connected"] is False
        assert "未配置API Key" in result["backup"]["error"]

    def test_connection_uses_short_timeout(self, client_with_config):
        seen_timeouts = []

        def capture(url, **kwargs):
            seen_timeouts.append(kwargs["timeout"])
            response = MagicMock()
            response.status_code = 200
            response.json.return_value = {
                "data": [{"id": "gpt-4o"}, {"id": "gpt-4o-mini"}]
            }
            response.raise_for_status.return_value = None
            return response

        with patch("services.llm_client.requests.get", side_effect=capture):
            client_with_config.test_connection()

        assert seen_timeouts == [12, 12]

    def test_primary_and_backup_are_tested_in_parallel(self, client_with_config):
        barrier = threading.Barrier(2)

        def meet(url, **kwargs):
            barrier.wait(timeout=1)
            response = MagicMock()
            response.status_code = 200
            response.json.return_value = {
                "data": [{"id": "gpt-4o"}, {"id": "gpt-4o-mini"}]
            }
            response.raise_for_status.return_value = None
            return response

        with patch("services.llm_client.requests.get", side_effect=meet):
            result = client_with_config.test_connection()

        assert result["primary"]["connected"] is True
        assert result["backup"]["connected"] is True

    def test_identical_backup_reuses_primary_result(self, client_with_config):
        client_with_config._backup = client_with_config._primary.model_copy(deep=True)
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"data": [{"id": "gpt-4o"}]}
        response.raise_for_status.return_value = None

        with patch(
            "services.llm_client.requests.get",
            return_value=response,
        ) as mock_call:
            result = client_with_config.test_connection()

        assert mock_call.call_count == 1
        assert result["backup"]["connected"] is True
        assert result["backup"]["reused_primary"] is True

    def test_connection_reports_missing_model(self, client_with_config):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"data": [{"id": "another-model"}]}
        response.raise_for_status.return_value = None

        with patch("services.llm_client.requests.get", return_value=response):
            result = client_with_config.test_connection()

        assert result["primary"]["connected"] is False
        assert result["primary"]["model_available"] is False
        assert "模型" in result["primary"]["error"]


class TestCacheManagement:
    """Tests for cache management methods."""

    def test_clear_cache(self, client_with_config):
        client_with_config._cache["key1"] = LLMResponse(success=True)
        client_with_config._cache["key2"] = LLMResponse(success=True)

        client_with_config.clear_cache()
        assert client_with_config._cache == {}

    def test_get_cache_stats_empty(self, client_with_config):
        stats = client_with_config.get_cache_stats()
        assert stats["cached_entries"] == 0

    def test_get_cache_stats_with_entries(self, client_with_config):
        client_with_config._cache["k1"] = LLMResponse(success=True)
        stats = client_with_config.get_cache_stats()
        assert stats["cached_entries"] == 1


class TestLoadConfigEdgeCases:
    """Tests for configuration loading edge cases."""

    def test_malformed_yaml_uses_defaults(self, tmp_path, monkeypatch):
        path = tmp_path / "bad.yaml"
        path.write_text("{ malformed", encoding="utf-8")
        monkeypatch.setattr(
            "services.llm_client.API_CONFIG_PATH",
            tmp_path / "nonexistent.yaml",
        )

        client = LLMClient(config_path=path)
        assert client._primary is not None
        assert client._primary.model == "gpt-4o"

    def test_empty_yaml_uses_defaults(self, tmp_path, monkeypatch):
        path = tmp_path / "empty.yaml"
        path.write_text("", encoding="utf-8")
        monkeypatch.setattr(
            "services.llm_client.API_CONFIG_PATH",
            tmp_path / "nonexistent.yaml",
        )

        client = LLMClient(config_path=path)
        assert client._primary is not None
        assert client._backup is not None


