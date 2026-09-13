"""常量定义与枚举类.

包含全部分析维度、蒸馏模式、Skill层级、创作步骤等枚举类型，
以及系统默认路径、数值阈值等常量.
"""

from enum import Enum, auto
from pathlib import Path
from typing import Final

# ============================ 项目路径常量 ============================

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
DATA_DIR: Final[Path] = PROJECT_ROOT / "data"
LOG_DIR: Final[Path] = DATA_DIR / "logs"
STORAGE_DIR: Final[Path] = DATA_DIR / "storage"
MATERIAL_DIR: Final[Path] = STORAGE_DIR / "materials"
ANALYSIS_DIR: Final[Path] = STORAGE_DIR / "analysis"
RULE_DIR: Final[Path] = STORAGE_DIR / "rules"
SKILL_DIR: Final[Path] = STORAGE_DIR / "skills"
PROJECT_STORAGE_DIR: Final[Path] = STORAGE_DIR / "projects"
FEEDBACK_DIR: Final[Path] = STORAGE_DIR / "feedback"
TEMP_DIR: Final[Path] = DATA_DIR / "temp"

# ============================ 文件扩展名常量 ============================

ALLOWED_UPLOAD_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {".txt", ".docx", ".md", ".json"}
)
MAX_UPLOAD_SIZE_MB: Final[int] = 50

# ============================ 文本处理常量 ============================

CHUNK_SIZE: Final[int] = 8000  # 文本分块字数上限
CHUNK_OVERLAP: Final[int] = 500  # 分块重叠字数
MAX_WORKERS: Final[int] = 4  # ThreadPoolExecutor并发数

# ============================ LLM调用常量 ============================

DEFAULT_TIMEOUT_SECONDS: Final[int] = 120
DEFAULT_MAX_RETRIES: Final[int] = 3
DEFAULT_TEMPERATURE: Final[float] = 0.7
DEFAULT_TOP_P: Final[float] = 0.9
RETRY_BASE_DELAY_SECONDS: Final[int] = 1  # 重试间隔: 1s -> 3s -> 9s

# ============================ 蒸馏常量 ============================

RULE_SIMILARITY_THRESHOLD: Final[float] = 0.85  # 规则去重相似度阈值
CONFLICT_DETECTION_THRESHOLD: Final[float] = 0.75  # 冲突检测语义阈值
MICRO_ITERATION_WEIGHT_DELTA: Final[int] = 5  # 微迭代权重调整幅度
MAX_SKILL_VERSIONS: Final[int] = 10  # 最大保留版本数

# ============================ 枚举类 ============================


class AnalysisDimension(str, Enum):
    """网文拆解八维度枚举."""

    PACING = "节奏"
    SUSPENSE = "悬念"
    CHARACTER = "人设"
    WORLD_BUILDING = "世界观"
    PLOT_STRUCTURE = "剧情架构"
    PROSE_STYLE = "文笔话术"
    SATISFACTION = "爽点"
    PITFALL = "避雷"


class DistillMode(str, Enum):
    """规则蒸馏模式枚举."""

    FULL = "全量"
    INCREMENTAL = "增量"
    TARGETED = "定向"


class SkillLayer(str, Enum):
    """Skill三层结构枚举."""

    BASE = "基层"  # 元规则与长期不可轻易覆盖的设定
    MIDDLE = "中间层"  # 可组合、可加权的创作规则
    DYNAMIC = "动态层"  # 仅在单个创作项目中生效的临时规则


class SkillStatus(str, Enum):
    """Skill状态枚举."""

    DRAFT = "草稿"
    ACTIVE = "生效"
    ARCHIVED = "归档"


class CreationStep(str, Enum):
    """分步创作步骤枚举."""

    WORLD_BUILDING = "世界观"
    CHARACTER = "人设"
    FIRST_THREE_CHAPTERS = "前三章"


class FeedbackType(str, Enum):
    """反馈样本类型枚举."""

    POSITIVE = "正样本"
    NEGATIVE = "负样本"


class FeedbackCategory(str, Enum):
    """反馈问题分类枚举."""

    PACING = "节奏"
    CHARACTER = "人设"
    PLOT = "剧情"
    PROSE = "文笔"
    OTHER = "其他"


class LogLevel(str, Enum):
    """日志级别枚举."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# ============================ 页面配置常量 ============================

PAGE_TITLE: Final[str] = "网文创作Skill蒸馏系统"
PAGE_ICON: Final[str] = ""
LAYOUT: Final[str] = "wide"
VERSION: Final[str] = "1.0.0"

# 侧边栏导航标签
NAV_LABELS: Final[dict[str, str]] = {
    "material": "素材拆解",
    "distill": "规则蒸馏",
    "skill": "Skill管理",
    "creation": "分步创作",
    "feedback": "迭代引擎",
    "settings": "API设置",
}

# ============================ 正则常量 ============================

# 常见广告/推广关键词模式
AD_PATTERNS: Final[list[str]] = [
    r"关注[微信公]*众号",
    r"扫码[关注]*",
    r"加入书友群",
    r"(?:QQ)?群[：:]?\d+",
    r"微信[：:]?[a-zA-Z0-9_]+",
    r"推荐票",
    r"月票",
    r"打赏",
    r"本章说",
    r"书荒[救]*援",
    r"求收藏",
    r"求推荐",
    r"求订阅",
]

# 乱码检测模式
GARBAGE_PATTERN: Final[str] = r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]{3,}"

# ============================ YAML配置常量 ============================

DEFAULT_SETTINGS: Final[dict] = {
    "system": {
        "name": "网文创作Skill蒸馏系统",
        "version": "1.0.0",
        "log_level": "INFO",
        "max_upload_size_mb": MAX_UPLOAD_SIZE_MB,
    },
    "analysis": {
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "max_workers": MAX_WORKERS,
        "dimensions": [d.value for d in AnalysisDimension],
    },
    "distill": {
        "similarity_threshold": RULE_SIMILARITY_THRESHOLD,
        "conflict_threshold": CONFLICT_DETECTION_THRESHOLD,
        "micro_weight_delta": MICRO_ITERATION_WEIGHT_DELTA,
        "max_versions": MAX_SKILL_VERSIONS,
    },
    "creation": {
        "steps": [s.value for s in CreationStep],
        "auto_validate": True,
    },
}

DEFAULT_API_CONFIG: Final[dict] = {
    "primary": {
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "model": "gpt-4o",
        "timeout": DEFAULT_TIMEOUT_SECONDS,
        "max_retries": DEFAULT_MAX_RETRIES,
    },
    "backup": {
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "model": "gpt-4o-mini",
        "timeout": DEFAULT_TIMEOUT_SECONDS,
        "max_retries": DEFAULT_MAX_RETRIES,
    },
    "parameters": {
        "temperature": DEFAULT_TEMPERATURE,
        "top_p": DEFAULT_TOP_P,
    },
}
