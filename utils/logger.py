"""日志配置模块.

提供统一的日志记录器，包含API Key脱敏过滤器和日志轮转功能.
"""

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from core.constants import LOG_DIR, LogLevel


class ApiKeyFilter(logging.Filter):
    """API Key脱敏过滤器.

    在日志输出前，将常见的API Key格式替换为***进行脱敏.
    """

    # 匹配类似 sk-xxx, api_key=xxx, "api_key": "xxx" 等格式
    _API_KEY_PATTERNS: list[re.Pattern] = [
        re.compile(r"(sk-[a-zA-Z0-9]{20,})", re.IGNORECASE),
        re.compile(r'(api[_-]?key[\s"\']*[:=][\s"\']*)([a-zA-Z0-9_\-]{8,})', re.IGNORECASE),
        re.compile(r'(authorization[\s"\']*[:=][\s"\']*(?:bearer\s+)?)([a-zA-Z0-9_\-\.]{8,})', re.IGNORECASE),
        re.compile(r'("api_key"\s*:\s*")([^"]{8,})(")', re.IGNORECASE),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """对日志消息进行API Key脱敏处理.

        Args:
            record: 日志记录对象.

        Returns:
            True表示记录通过过滤器.
        """
        if isinstance(record.msg, str):
            record.msg = self._desensitize(record.msg)
        # 对args中的字符串参数也进行脱敏
        if record.args:
            record.args = self._desensitize_args(record.args)
        return True

    def _desensitize(self, text: str) -> str:
        """对文本中的API Key进行脱敏替换.

        Args:
            text: 原始文本.

        Returns:
            脱敏后的文本.
        """
        for pattern in self._API_KEY_PATTERNS:
            text = pattern.sub(self._replace_key, text)
        return text

    def _desensitize_args(self, args: Any) -> Any:
        """对日志参数进行脱敏.

        Args:
            args: 日志参数，可能是tuple或dict.

        Returns:
            脱敏后的参数.
        """
        if isinstance(args, tuple):
            return tuple(self._desensitize(str(arg)) if isinstance(arg, str) else arg for arg in args)
        if isinstance(args, dict):
            return {k: self._desensitize(str(v)) if isinstance(v, str) else v for k, v in args.items()}
        return args

    @staticmethod
    def _replace_key(match: re.Match) -> str:
        """替换匹配到的API Key为脱敏形式.

        Args:
            match: 正则匹配对象.

        Returns:
            脱敏后的替换字符串.
        """
        groups = match.groups()
        if len(groups) == 1:
            # 整个匹配都是key
            return "***"
        if len(groups) == 2:
            # prefix + key
            return groups[0] + "***"
        if len(groups) == 3:
            # prefix + key + suffix
            return groups[0] + "***" + groups[2]
        return "***"


def get_logger(name: str, level: str | None = None) -> logging.Logger:
    """获取配置好的日志记录器.

    日志同时输出到控制台和轮转文件(data/logs/app.log).
    文件大小达到10MB时自动轮转，最多保留5个备份.

    Args:
        name: 日志记录器名称，通常使用__name__.
        level: 日志级别，默认从配置读取，未配置则为INFO.

    Returns:
        配置好的日志记录器.
    """
    logger = logging.getLogger(name)

    # 避免重复添加handler
    if logger.handlers:
        return logger

    log_level = getattr(logging, (level or LogLevel.INFO.value).upper(), logging.INFO)
    logger.setLevel(log_level)

    # 创建日志目录
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / "app.log"

    # 文件处理器 - 轮转
    file_handler = RotatingFileHandler(
        filename=log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )
    console_handler.setFormatter(console_formatter)

    # API Key脱敏过滤器
    api_key_filter = ApiKeyFilter()
    file_handler.addFilter(api_key_filter)
    console_handler.addFilter(api_key_filter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
