"""Tests for core.models module."""

import json
import uuid
from datetime import datetime

import pytest
from pydantic import ValidationError

from core.constants import (
    AnalysisDimension,
    CreationStep,
    DistillMode,
    FeedbackCategory,
    FeedbackType,
    SkillLayer,
    SkillStatus,
)
from core.models import (
    AnalysisFile,
    AnalysisRule,
    ApiConfig,
    CleanedText,
    CreationProject,
    FeedbackSample,
    LLMRequest,
    LLMResponse,
    NovelMaterial,
    RetryConfig,
    Rule,
    RuleSet,
    Skill,
    SkillRule,
    SkillVersion,
    TimestampMixin,
)


class TestTimestampMixin:
    """Tests for TimestampMixin."""

    def test_default_timestamps(self):
        obj = TimestampMixin()
        assert isinstance(obj.created_at, datetime)
        assert isinstance(obj.updated_at, datetime)


class TestNovelMaterial:
    """Tests for NovelMaterial model."""

    def test_create_minimal(self):
        material = NovelMaterial(filename="test.txt", raw_text="Hello world")
        assert material.filename == "test.txt"
        assert material.raw_text == "Hello world"
        assert material.file_size == 0
        assert isinstance(material.id, str)
        assert uuid.UUID(material.id)
        assert isinstance(material.uploaded_at, datetime)

    def test_create_full(self):
        now = datetime.now()
        material = NovelMaterial(
            id="custom-id",
            filename="test.md",
            raw_text="Content",
            file_size=1024,
            uploaded_at=now,
        )
        assert material.id == "custom-id"
        assert material.file_size == 1024

    def test_filename_cannot_be_empty(self):
        with pytest.raises(ValidationError):
            NovelMaterial(filename="", raw_text="text")

    def test_filename_cannot_be_whitespace(self):
        with pytest.raises(ValidationError):
            NovelMaterial(filename="   ", raw_text="text")

    def test_filename_strips_whitespace(self):
        material = NovelMaterial(filename="  test.txt  ", raw_text="text")
        assert material.filename == "test.txt"

    def test_file_size_must_be_non_negative(self):
        with pytest.raises(ValidationError):
            NovelMaterial(filename="test.txt", raw_text="text", file_size=-1)

    def test_serialization(self):
        material = NovelMaterial(filename="test.txt", raw_text="Hello")
        data = material.model_dump(mode="json")
        assert data["filename"] == "test.txt"
        assert data["raw_text"] == "Hello"
        assert "id" in data
        assert "uploaded_at" in data

    def test_deserialization(self):
        data = {
            "id": "test-id",
            "filename": "test.txt",
            "raw_text": "Hello",
            "file_size": 100,
            "uploaded_at": datetime.now().isoformat(),
        }
        material = NovelMaterial.model_validate(data)
        assert material.id == "test-id"
        assert material.filename == "test.txt"


class TestCleanedText:
    """Tests for CleanedText model."""

    def test_create_minimal(self):
        ct = CleanedText(material_id="mid-1", cleaned_text="clean")
        assert ct.material_id == "mid-1"
        assert ct.cleaned_text == "clean"
        assert ct.removed_chars_count == 0
        assert ct.removed_paragraphs_count == 0
        assert ct.chunks == []

    def test_create_full(self):
        ct = CleanedText(
            material_id="mid-1",
            cleaned_text="clean",
            removed_chars_count=10,
            removed_paragraphs_count=2,
            chunks=["chunk1", "chunk2"],
        )
        assert ct.removed_chars_count == 10
        assert ct.removed_paragraphs_count == 2
        assert ct.chunks == ["chunk1", "chunk2"]

    def test_removed_counts_must_be_non_negative(self):
        with pytest.raises(ValidationError):
            CleanedText(material_id="mid", cleaned_text="text", removed_chars_count=-1)
        with pytest.raises(ValidationError):
            CleanedText(material_id="mid", cleaned_text="text", removed_paragraphs_count=-1)


class TestAnalysisRule:
    """Tests for AnalysisRule model."""

    def test_create_minimal(self):
        rule = AnalysisRule(content="Rule content")
        assert rule.content == "Rule content"
        assert rule.weight == 50
        assert rule.source_chunk_index == 0
        assert rule.line_range is None
        assert rule.explanation == ""
        assert rule.examples == []

    def test_create_full(self):
        rule = AnalysisRule(
            content="Content",
            weight=80,
            source_chunk_index=1,
            line_range=(10, 20),
            explanation="Explanation",
            examples=["ex1", "ex2"],
        )
        assert rule.weight == 80
        assert rule.line_range == (10, 20)
        assert rule.examples == ["ex1", "ex2"]

    def test_content_cannot_be_empty(self):
        with pytest.raises(ValidationError):
            AnalysisRule(content="")

    def test_content_cannot_be_whitespace(self):
        with pytest.raises(ValidationError):
            AnalysisRule(content="   ")

    def test_content_strips_whitespace(self):
        rule = AnalysisRule(content="  content  ")
        assert rule.content == "content"

    def test_weight_bounds(self):
        with pytest.raises(ValidationError):
            AnalysisRule(content="test", weight=-1)
        with pytest.raises(ValidationError):
            AnalysisRule(content="test", weight=101)

    def test_source_chunk_index_must_be_non_negative(self):
        with pytest.raises(ValidationError):
            AnalysisRule(content="test", source_chunk_index=-1)


class TestAnalysisFile:
    """Tests for AnalysisFile model."""

    def test_create_minimal(self):
        af = AnalysisFile(material_id="mid", dimension=AnalysisDimension.PACING)
        assert af.material_id == "mid"
        assert af.dimension == AnalysisDimension.PACING
        assert af.rules == []
        assert af.summary == ""
        assert isinstance(af.id, str)

    def test_create_with_rules(self):
        rule = AnalysisRule(content="Test rule", weight=70)
        af = AnalysisFile(
            material_id="mid",
            dimension=AnalysisDimension.CHARACTER,
            rules=[rule],
            summary="Summary text",
        )
        assert len(af.rules) == 1
        assert af.rules[0].content == "Test rule"
        assert af.summary == "Summary text"


class TestRule:
    """Tests for Rule model."""

    def test_create_minimal(self):
        rule = Rule(dimension=AnalysisDimension.SUSPENSE, content="Suspense rule")
        assert rule.dimension == AnalysisDimension.SUSPENSE
        assert rule.content == "Suspense rule"
        assert rule.weight == 50
        assert rule.source_material_ids == []
        assert rule.conflicting_rule_ids == []
        assert rule.is_empty is False

    def test_content_cannot_be_empty(self):
        with pytest.raises(ValidationError):
            Rule(dimension=AnalysisDimension.PACING, content="")

    def test_weight_bounds(self):
        with pytest.raises(ValidationError):
            Rule(dimension=AnalysisDimension.PACING, content="test", weight=101)
        with pytest.raises(ValidationError):
            Rule(dimension=AnalysisDimension.PACING, content="test", weight=-1)


class TestRuleSet:
    """Tests for RuleSet model."""

    def test_create_minimal(self):
        rs = RuleSet(name="Test set", distill_mode=DistillMode.FULL)
        assert rs.name == "Test set"
        assert rs.distill_mode == DistillMode.FULL
        assert rs.source_material_ids == []
        assert rs.rules == {}
        assert rs.conflict_report == {}
        assert isinstance(rs.id, str)

    def test_name_cannot_be_empty(self):
        with pytest.raises(ValidationError):
            RuleSet(name="", distill_mode=DistillMode.FULL)

    def test_name_strips_whitespace(self):
        rs = RuleSet(name="  name  ", distill_mode=DistillMode.FULL)
        assert rs.name == "name"

    def test_create_with_rules(self):
        rule = Rule(dimension=AnalysisDimension.PACING, content="Pacing rule", weight=60)
        rs = RuleSet(
            name="Set",
            distill_mode=DistillMode.INCREMENTAL,
            source_material_ids=["m1", "m2"],
            rules={"节奏": [rule]},
            conflict_report={"conflicts": []},
        )
        assert rs.source_material_ids == ["m1", "m2"]
        assert "节奏" in rs.rules
        assert len(rs.rules["节奏"]) == 1


class TestSkillRule:
    """Tests for SkillRule model."""

    def test_create_minimal(self):
        sr = SkillRule(
            layer=SkillLayer.MIDDLE,
            dimension=AnalysisDimension.PACING,
            content="Pacing",
        )
        assert sr.layer == SkillLayer.MIDDLE
        assert sr.dimension == AnalysisDimension.PACING
        assert sr.weight == 50
        assert sr.source_rule_ids == []

    def test_content_cannot_be_empty(self):
        with pytest.raises(ValidationError):
            SkillRule(
                layer=SkillLayer.BASE,
                dimension=AnalysisDimension.WORLD_BUILDING,
                content="",
            )

    def test_weight_bounds(self):
        with pytest.raises(ValidationError):
            SkillRule(
                layer=SkillLayer.BASE,
                dimension=AnalysisDimension.WORLD_BUILDING,
                content="test",
                weight=150,
            )


class TestSkillVersion:
    """Tests for SkillVersion model."""

    def test_create_minimal(self):
        sv = SkillVersion(version="1.0.0")
        assert sv.version == "1.0.0"
        assert sv.rules_snapshot == {}
        assert sv.changelog == ""
        assert isinstance(sv.created_at, datetime)

    def test_version_cannot_be_empty(self):
        with pytest.raises(ValidationError):
            SkillVersion(version="")

    def test_version_strips_whitespace(self):
        sv = SkillVersion(version="  1.0.0  ")
        assert sv.version == "1.0.0"


class TestSkill:
    """Tests for Skill model."""

    def test_create_minimal(self):
        skill = Skill(name="Test Skill")
        assert skill.name == "Test Skill"
        assert skill.description == ""
        assert skill.versions == []
        assert skill.status == SkillStatus.DRAFT
        assert skill.current_version == "0.0.1"
        assert isinstance(skill.id, str)
        assert set(skill.layers.keys()) == {
            SkillLayer.BASE.value,
            SkillLayer.MIDDLE.value,
            SkillLayer.DYNAMIC.value,
        }

    def test_name_cannot_be_empty(self):
        with pytest.raises(ValidationError):
            Skill(name="")

    def test_name_strips_whitespace(self):
        skill = Skill(name="  Skill Name  ")
        assert skill.name == "Skill Name"

    def test_default_layers_are_empty_lists(self):
        skill = Skill(name="Test")
        assert skill.layers[SkillLayer.BASE.value] == []
        assert skill.layers[SkillLayer.MIDDLE.value] == []
        assert skill.layers[SkillLayer.MIDDLE.value] == []


class TestCreationProject:
    """Tests for CreationProject model."""

    def test_create_minimal(self):
        project = CreationProject(name="Test Project")
        assert project.name == "Test Project"
        assert project.skill_id == ""
        assert project.current_step == CreationStep.WORLD_BUILDING
        assert project.locked_steps == []
        assert project.step_contents == {}
        assert project.locked_snapshots == {}
        assert project.validation_reports == {}
        assert isinstance(project.id, str)

    def test_name_cannot_be_empty(self):
        with pytest.raises(ValidationError):
            CreationProject(name="")

    def test_name_strips_whitespace(self):
        project = CreationProject(name="  Project  ")
        assert project.name == "Project"


class TestFeedbackSample:
    """Tests for FeedbackSample model."""

    def test_create_minimal(self):
        fb = FeedbackSample(
            project_id="pid-1",
            feedback_type=FeedbackType.POSITIVE,
            content="Good work",
        )
        assert fb.project_id == "pid-1"
        assert fb.feedback_type == FeedbackType.POSITIVE
        assert fb.category == FeedbackCategory.OTHER
        assert fb.content == "Good work"
        assert fb.related_rule_ids == []
        assert fb.suggested_weight_delta == 0

    def test_create_full(self):
        fb = FeedbackSample(
            project_id="pid-1",
            feedback_type=FeedbackType.NEGATIVE,
            category=FeedbackCategory.PACING,
            content="Too slow",
            related_rule_ids=["r1", "r2"],
            suggested_weight_delta=-10,
        )
        assert fb.category == FeedbackCategory.PACING
        assert fb.suggested_weight_delta == -10

    def test_content_cannot_be_empty(self):
        with pytest.raises(ValidationError):
            FeedbackSample(
                project_id="pid",
                feedback_type=FeedbackType.POSITIVE,
                content="",
            )


class TestRetryConfig:
    """Tests for RetryConfig model."""

    def test_defaults(self):
        rc = RetryConfig()
        assert rc.max_retries == 3
        assert rc.base_delay == 1.0
        assert rc.backoff_multiplier == 3.0

    def test_max_retries_bounds(self):
        with pytest.raises(ValidationError):
            RetryConfig(max_retries=-1)
        with pytest.raises(ValidationError):
            RetryConfig(max_retries=11)

    def test_base_delay_must_be_non_negative(self):
        with pytest.raises(ValidationError):
            RetryConfig(base_delay=-1.0)

    def test_backoff_multiplier_must_be_at_least_one(self):
        with pytest.raises(ValidationError):
            RetryConfig(backoff_multiplier=0.5)


class TestApiConfig:
    """Tests for ApiConfig model."""

    def test_defaults(self):
        config = ApiConfig()
        assert config.provider == "openai"
        assert config.base_url == "https://api.openai.com/v1"
        assert config.api_key == ""
        assert config.model == "gpt-4o"
        assert config.timeout == 120
        assert isinstance(config.retry, RetryConfig)

    def test_timeout_must_be_positive(self):
        with pytest.raises(ValidationError):
            ApiConfig(timeout=0)


class TestLLMRequest:
    """Tests for LLMRequest model."""

    def test_create_minimal(self):
        req = LLMRequest(prompt="Hello")
        assert req.prompt == "Hello"
        assert req.system_message == ""
        assert req.temperature == 0.7
        assert req.top_p == 0.9
        assert req.max_tokens is None

    def test_prompt_cannot_be_empty(self):
        with pytest.raises(ValidationError):
            LLMRequest(prompt="")

    def test_prompt_strips_whitespace(self):
        req = LLMRequest(prompt="  Hello  ")
        assert req.prompt == "Hello"

    def test_temperature_bounds(self):
        with pytest.raises(ValidationError):
            LLMRequest(prompt="test", temperature=-0.1)
        with pytest.raises(ValidationError):
            LLMRequest(prompt="test", temperature=2.1)

    def test_top_p_bounds(self):
        with pytest.raises(ValidationError):
            LLMRequest(prompt="test", top_p=-0.1)
        with pytest.raises(ValidationError):
            LLMRequest(prompt="test", top_p=1.1)

    def test_max_tokens_must_be_positive(self):
        with pytest.raises(ValidationError):
            LLMRequest(prompt="test", max_tokens=0)


class TestLLMResponse:
    """Tests for LLMResponse model."""

    def test_defaults(self):
        resp = LLMResponse()
        assert resp.success is True
        assert resp.content == ""
        assert resp.raw_response == {}
        assert resp.latency_ms == 0
        assert resp.token_usage == {}
        assert resp.error_message == ""

    def test_create_full(self):
        resp = LLMResponse(
            success=False,
            content="Error",
            raw_response={"error": "test"},
            latency_ms=100,
            token_usage={"total": 10},
            error_message="Test error",
        )
        assert resp.success is False
        assert resp.latency_ms == 100


class TestModelRoundTrip:
    """Tests for serialization and deserialization round-trips."""

    def test_novel_material_round_trip(self):
        original = NovelMaterial(filename="test.txt", raw_text="Hello")
        data = original.model_dump(mode="json")
        restored = NovelMaterial.model_validate(data)
        assert restored.filename == original.filename
        assert restored.raw_text == original.raw_text
        assert restored.id == original.id

    def test_skill_round_trip(self):
        original = Skill(name="Test Skill", description="Desc")
        data = original.model_dump(mode="json")
        restored = Skill.model_validate(data)
        assert restored.name == original.name
        assert restored.description == original.description
        assert restored.current_version == original.current_version

    def test_rule_set_round_trip(self):
        rule = Rule(dimension=AnalysisDimension.PACING, content="Rule", weight=60)
        original = RuleSet(
            name="Set",
            distill_mode=DistillMode.FULL,
            rules={"节奏": [rule]},
        )
        data = original.model_dump(mode="json")
        restored = RuleSet.model_validate(data)
        assert restored.name == original.name
        assert "节奏" in restored.rules
        assert len(restored.rules["节奏"]) == 1
        assert restored.rules["节奏"][0].content == "Rule"

    def test_feedback_sample_round_trip(self):
        original = FeedbackSample(
            project_id="pid",
            feedback_type=FeedbackType.POSITIVE,
            content="Good",
        )
        data = original.model_dump(mode="json")
        restored = FeedbackSample.model_validate(data)
        assert restored.content == original.content
        assert restored.feedback_type == original.feedback_type
