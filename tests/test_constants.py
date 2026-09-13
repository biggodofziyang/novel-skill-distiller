"""Tests for core.constants module."""

from pathlib import Path

import pytest

from core.constants import (
    AD_PATTERNS,
    ALLOWED_UPLOAD_EXTENSIONS,
    ANALYSIS_DIR,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    CONFLICT_DETECTION_THRESHOLD,
    DATA_DIR,
    DEFAULT_API_CONFIG,
    DEFAULT_MAX_RETRIES,
    DEFAULT_SETTINGS,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_TOP_P,
    FEEDBACK_DIR,
    GARBAGE_PATTERN,
    LOG_DIR,
    MATERIAL_DIR,
    MAX_SKILL_VERSIONS,
    MAX_UPLOAD_SIZE_MB,
    MAX_WORKERS,
    MICRO_ITERATION_WEIGHT_DELTA,
    NAV_LABELS,
    PAGE_ICON,
    PAGE_TITLE,
    PROJECT_ROOT,
    PROJECT_STORAGE_DIR,
    RETRY_BASE_DELAY_SECONDS,
    RULE_DIR,
    RULE_SIMILARITY_THRESHOLD,
    SKILL_DIR,
    STORAGE_DIR,
    TEMP_DIR,
    VERSION,
    AnalysisDimension,
    CreationStep,
    DistillMode,
    FeedbackCategory,
    FeedbackType,
    LogLevel,
    SkillLayer,
    SkillStatus,
)


class TestPathConstants:
    """Tests for path constants."""

    def test_project_root_is_path(self):
        assert isinstance(PROJECT_ROOT, Path)
        assert PROJECT_ROOT.exists()

    def test_data_dir_is_subdirectory(self):
        assert DATA_DIR == PROJECT_ROOT / "data"

    def test_log_dir_is_under_data(self):
        assert LOG_DIR == DATA_DIR / "logs"

    def test_storage_dir_is_under_data(self):
        assert STORAGE_DIR == DATA_DIR / "storage"

    def test_material_dir_is_under_storage(self):
        assert MATERIAL_DIR == STORAGE_DIR / "materials"

    def test_analysis_dir_is_under_storage(self):
        assert ANALYSIS_DIR == STORAGE_DIR / "analysis"

    def test_rule_dir_is_under_storage(self):
        assert RULE_DIR == STORAGE_DIR / "rules"

    def test_skill_dir_is_under_storage(self):
        assert SKILL_DIR == STORAGE_DIR / "skills"

    def test_project_storage_dir_is_under_storage(self):
        assert PROJECT_STORAGE_DIR == STORAGE_DIR / "projects"

    def test_feedback_dir_is_under_storage(self):
        assert FEEDBACK_DIR == STORAGE_DIR / "feedback"

    def test_temp_dir_is_under_data(self):
        assert TEMP_DIR == DATA_DIR / "temp"


class TestFileExtensionConstants:
    """Tests for file extension constants."""

    def test_allowed_extensions(self):
        assert ALLOWED_UPLOAD_EXTENSIONS == frozenset({".txt", ".docx", ".md", ".json"})

    def test_max_upload_size(self):
        assert MAX_UPLOAD_SIZE_MB == 50
        assert isinstance(MAX_UPLOAD_SIZE_MB, int)


class TestTextProcessingConstants:
    """Tests for text processing constants."""

    def test_chunk_size(self):
        assert CHUNK_SIZE == 8000
        assert isinstance(CHUNK_SIZE, int)

    def test_chunk_overlap(self):
        assert CHUNK_OVERLAP == 500
        assert isinstance(CHUNK_OVERLAP, int)

    def test_max_workers(self):
        assert MAX_WORKERS == 4
        assert isinstance(MAX_WORKERS, int)


class TestLlmConstants:
    """Tests for LLM constants."""

    def test_default_timeout(self):
        assert DEFAULT_TIMEOUT_SECONDS == 120

    def test_default_max_retries(self):
        assert DEFAULT_MAX_RETRIES == 3

    def test_default_temperature(self):
        assert DEFAULT_TEMPERATURE == 0.7

    def test_default_top_p(self):
        assert DEFAULT_TOP_P == 0.9

    def test_retry_base_delay(self):
        assert RETRY_BASE_DELAY_SECONDS == 1


class TestDistillConstants:
    """Tests for distill constants."""

    def test_rule_similarity_threshold(self):
        assert RULE_SIMILARITY_THRESHOLD == 0.85

    def test_conflict_detection_threshold(self):
        assert CONFLICT_DETECTION_THRESHOLD == 0.75

    def test_micro_iteration_weight_delta(self):
        assert MICRO_ITERATION_WEIGHT_DELTA == 5

    def test_max_skill_versions(self):
        assert MAX_SKILL_VERSIONS == 10


class TestEnums:
    """Tests for enumeration classes."""

    def test_analysis_dimension_values(self):
        assert AnalysisDimension.PACING.value == "节奏"
        assert AnalysisDimension.SUSPENSE.value == "悬念"
        assert AnalysisDimension.CHARACTER.value == "人设"
        assert AnalysisDimension.WORLD_BUILDING.value == "世界观"
        assert AnalysisDimension.PLOT_STRUCTURE.value == "剧情架构"
        assert AnalysisDimension.PROSE_STYLE.value == "文笔话术"
        assert AnalysisDimension.SATISFACTION.value == "爽点"
        assert AnalysisDimension.PITFALL.value == "避雷"

    def test_analysis_dimension_count(self):
        assert len(AnalysisDimension) == 8

    def test_distill_mode_values(self):
        assert DistillMode.FULL.value == "全量"
        assert DistillMode.INCREMENTAL.value == "增量"
        assert DistillMode.TARGETED.value == "定向"

    def test_skill_layer_values(self):
        assert SkillLayer.BASE.value == "基层"
        assert SkillLayer.MIDDLE.value == "中间层"
        assert SkillLayer.DYNAMIC.value == "动态层"

    def test_skill_status_values(self):
        assert SkillStatus.DRAFT.value == "草稿"
        assert SkillStatus.ACTIVE.value == "生效"
        assert SkillStatus.ARCHIVED.value == "归档"

    def test_creation_step_values(self):
        assert CreationStep.WORLD_BUILDING.value == "世界观"
        assert CreationStep.CHARACTER.value == "人设"
        assert CreationStep.FIRST_THREE_CHAPTERS.value == "前三章"

    def test_feedback_type_values(self):
        assert FeedbackType.POSITIVE.value == "正样本"
        assert FeedbackType.NEGATIVE.value == "负样本"

    def test_feedback_category_values(self):
        assert FeedbackCategory.PACING.value == "节奏"
        assert FeedbackCategory.CHARACTER.value == "人设"
        assert FeedbackCategory.PLOT.value == "剧情"
        assert FeedbackCategory.PROSE.value == "文笔"
        assert FeedbackCategory.OTHER.value == "其他"

    def test_log_level_values(self):
        assert LogLevel.DEBUG.value == "DEBUG"
        assert LogLevel.INFO.value == "INFO"
        assert LogLevel.WARNING.value == "WARNING"
        assert LogLevel.ERROR.value == "ERROR"
        assert LogLevel.CRITICAL.value == "CRITICAL"

    def test_enum_membership(self):
        assert "节奏" in [d.value for d in AnalysisDimension]
        assert "全量" in [m.value for m in DistillMode]


class TestPageConstants:
    """Tests for page configuration constants."""

    def test_page_title(self):
        assert PAGE_TITLE == "网文创作Skill蒸馏系统"

    def test_page_icon(self):
        assert PAGE_ICON == ""

    def test_layout(self):
        from core.constants import LAYOUT
        assert LAYOUT == "wide"

    def test_version(self):
        assert VERSION == "1.0.0"

    def test_nav_labels(self):
        assert NAV_LABELS == {
            "material": "素材拆解",
            "distill": "规则蒸馏",
            "skill": "Skill管理",
            "creation": "分步创作",
            "feedback": "迭代引擎",
            "settings": "API设置",
        }


class TestRegexConstants:
    """Tests for regex pattern constants."""

    def test_ad_patterns_is_list(self):
        assert isinstance(AD_PATTERNS, list)
        assert len(AD_PATTERNS) > 0

    def test_ad_patterns_are_valid_regex(self):
        import re
        for pattern in AD_PATTERNS:
            compiled = re.compile(pattern)
            assert compiled is not None

    def test_garbage_pattern_is_valid_regex(self):
        import re
        compiled = re.compile(GARBAGE_PATTERN)
        assert compiled is not None


class TestDefaultConfigs:
    """Tests for default configuration dictionaries."""

    def test_default_settings_structure(self):
        assert "system" in DEFAULT_SETTINGS
        assert "analysis" in DEFAULT_SETTINGS
        assert "distill" in DEFAULT_SETTINGS
        assert "creation" in DEFAULT_SETTINGS

    def test_default_settings_system(self):
        system = DEFAULT_SETTINGS["system"]
        assert system["name"] == "网文创作Skill蒸馏系统"
        assert system["version"] == "1.0.0"
        assert system["log_level"] == "INFO"
        assert system["max_upload_size_mb"] == 50

    def test_default_settings_analysis(self):
        analysis = DEFAULT_SETTINGS["analysis"]
        assert analysis["chunk_size"] == CHUNK_SIZE
        assert analysis["chunk_overlap"] == CHUNK_OVERLAP
        assert analysis["max_workers"] == MAX_WORKERS
        assert set(analysis["dimensions"]) == set(d.value for d in AnalysisDimension)

    def test_default_settings_distill(self):
        distill = DEFAULT_SETTINGS["distill"]
        assert distill["similarity_threshold"] == RULE_SIMILARITY_THRESHOLD
        assert distill["conflict_threshold"] == CONFLICT_DETECTION_THRESHOLD
        assert distill["micro_weight_delta"] == MICRO_ITERATION_WEIGHT_DELTA
        assert distill["max_versions"] == MAX_SKILL_VERSIONS

    def test_default_settings_creation(self):
        creation = DEFAULT_SETTINGS["creation"]
        assert creation["steps"] == [s.value for s in CreationStep]
        assert creation["auto_validate"] is True

    def test_default_api_config_structure(self):
        assert "primary" in DEFAULT_API_CONFIG
        assert "backup" in DEFAULT_API_CONFIG
        assert "parameters" in DEFAULT_API_CONFIG

    def test_default_api_config_primary(self):
        primary = DEFAULT_API_CONFIG["primary"]
        assert primary["provider"] == "openai"
        assert primary["model"] == "gpt-4o"
        assert primary["timeout"] == DEFAULT_TIMEOUT_SECONDS
        assert primary["max_retries"] == DEFAULT_MAX_RETRIES

    def test_default_api_config_backup(self):
        backup = DEFAULT_API_CONFIG["backup"]
        assert backup["provider"] == "openai"
        assert backup["model"] == "gpt-4o-mini"

    def test_default_api_config_parameters(self):
        params = DEFAULT_API_CONFIG["parameters"]
        assert params["temperature"] == DEFAULT_TEMPERATURE
        assert params["top_p"] == DEFAULT_TOP_P
