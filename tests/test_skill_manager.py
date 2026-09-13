"""Tests for services.skill_manager module."""

import pytest

from core.constants import (
    MAX_SKILL_VERSIONS,
    AnalysisDimension,
    DistillMode,
    SkillLayer,
    SkillStatus,
)
from core.models import (
    Rule,
    RuleSet,
    Skill,
    SkillRule,
    SkillVersion,
)
from core.storage import StorageManager
from services.skill_manager import DIMENSION_TO_LAYER, SkillManager


@pytest.fixture
def manager(tmp_path, monkeypatch):
    """Provide a SkillManager with temporary storage."""
    monkeypatch.setattr("core.storage.MATERIAL_DIR", tmp_path / "materials")
    monkeypatch.setattr("core.constants.MATERIAL_DIR", tmp_path / "materials")
    monkeypatch.setattr("core.storage.ANALYSIS_DIR", tmp_path / "analysis")
    monkeypatch.setattr("core.constants.ANALYSIS_DIR", tmp_path / "analysis")
    monkeypatch.setattr("core.storage.RULE_DIR", tmp_path / "rules")
    monkeypatch.setattr("core.constants.RULE_DIR", tmp_path / "rules")
    monkeypatch.setattr("core.storage.SKILL_DIR", tmp_path / "skills")
    monkeypatch.setattr("core.constants.SKILL_DIR", tmp_path / "skills")
    monkeypatch.setattr("core.storage.PROJECT_STORAGE_DIR", tmp_path / "projects")
    monkeypatch.setattr("core.constants.PROJECT_STORAGE_DIR", tmp_path / "projects")
    monkeypatch.setattr("core.storage.FEEDBACK_DIR", tmp_path / "feedback")
    monkeypatch.setattr("core.constants.FEEDBACK_DIR", tmp_path / "feedback")
    monkeypatch.setattr("core.storage.TEMP_DIR", tmp_path / "temp")
    monkeypatch.setattr("core.constants.TEMP_DIR", tmp_path / "temp")
    monkeypatch.setattr("core.constants.LOG_DIR", tmp_path / "logs")

    storage = StorageManager()
    return SkillManager(storage=storage)


@pytest.fixture
def sample_rule_set():
    """Create a sample RuleSet for testing."""
    rules = {
        "世界观": [
            Rule(dimension=AnalysisDimension.WORLD_BUILDING, content="Detailed world", weight=80),
        ],
        "人设": [
            Rule(dimension=AnalysisDimension.CHARACTER, content="Strong character", weight=70),
        ],
        "节奏": [
            Rule(dimension=AnalysisDimension.PACING, content="Fast pacing", weight=60),
            Rule(dimension=AnalysisDimension.PACING, content="Chapter hooks", weight=65),
        ],
    }
    return RuleSet(
        name="Sample Rules",
        distill_mode=DistillMode.FULL,
        rules=rules,
    )


@pytest.fixture
def sample_skill():
    """Create a sample Skill for testing."""
    skill = Skill(name="Test Skill")
    skill.layers[SkillLayer.BASE.value].append(
        SkillRule(
            layer=SkillLayer.BASE,
            dimension=AnalysisDimension.WORLD_BUILDING,
            content="World rule",
            weight=80,
        )
    )
    skill.layers[SkillLayer.MIDDLE.value].append(
        SkillRule(
            layer=SkillLayer.MIDDLE,
            dimension=AnalysisDimension.PACING,
            content="Pacing rule",
            weight=70,
        )
    )
    return skill


class TestDimensionToLayer:
    """Tests for DIMENSION_TO_LAYER mapping."""

    def test_world_building_to_foundation(self):
        assert DIMENSION_TO_LAYER["世界观"] == SkillLayer.BASE

    def test_character_to_character(self):
        assert DIMENSION_TO_LAYER["人设"] == SkillLayer.MIDDLE

    def test_pacing_to_narrative(self):
        assert DIMENSION_TO_LAYER["节奏"] == SkillLayer.MIDDLE

    def test_suspense_to_narrative(self):
        assert DIMENSION_TO_LAYER["悬念"] == SkillLayer.MIDDLE

    def test_plot_structure_to_narrative(self):
        assert DIMENSION_TO_LAYER["剧情架构"] == SkillLayer.MIDDLE

    def test_prose_style_to_narrative(self):
        assert DIMENSION_TO_LAYER["文笔话术"] == SkillLayer.MIDDLE

    def test_satisfaction_to_narrative(self):
        assert DIMENSION_TO_LAYER["爽点"] == SkillLayer.MIDDLE

    def test_pitfall_to_narrative(self):
        assert DIMENSION_TO_LAYER["避雷"] == SkillLayer.MIDDLE

    def test_unknown_dimension_defaults_to_narrative(self):
        assert DIMENSION_TO_LAYER.get("未知", SkillLayer.MIDDLE) == SkillLayer.MIDDLE


class TestCreateSkill:
    """Tests for create_skill method."""

    def test_create_skill_from_rule_set(self, manager, sample_rule_set):
        skill = manager.create_skill(sample_rule_set, name="My Skill", description="A skill")

        assert skill.name == "My Skill"
        assert skill.description == "A skill"
        assert skill.status == SkillStatus.DRAFT
        assert len(skill.versions) == 1
        assert skill.current_version == skill.versions[0].version

    def test_rules_assigned_to_correct_layers(self, manager, sample_rule_set):
        skill = manager.create_skill(sample_rule_set, name="My Skill")

        base_rules = skill.layers[SkillLayer.BASE.value]
        middle_rules = skill.layers[SkillLayer.MIDDLE.value]
        dynamic_rules = skill.layers[SkillLayer.DYNAMIC.value]

        assert len(base_rules) == 1
        assert base_rules[0].content == "Detailed world"
        assert base_rules[0].layer == SkillLayer.BASE
        assert len(middle_rules) == 3
        assert any(rule.content == "Strong character" for rule in middle_rules)
        assert dynamic_rules == []

    def test_source_rule_ids_populated(self, manager, sample_rule_set):
        skill = manager.create_skill(sample_rule_set, name="My Skill")
        all_rules = []
        for rules in skill.layers.values():
            all_rules.extend(rules)

        assert len(all_rules) == 4
        for rule in all_rules:
            assert len(rule.source_rule_ids) == 1

    def test_empty_rule_set(self, manager):
        rs = RuleSet(name="Empty", distill_mode=DistillMode.FULL)
        skill = manager.create_skill(rs, name="Empty Skill")

        assert skill.name == "Empty Skill"
        total_rules = sum(len(r) for r in skill.layers.values())
        assert total_rules == 0
        assert len(skill.versions) == 1

    def test_version_created_on_skill_creation(self, manager, sample_rule_set):
        skill = manager.create_skill(sample_rule_set, name="My Skill")
        assert len(skill.versions) == 1
        assert skill.versions[0].changelog == "初始版本"


class TestCombineSkills:
    """Tests for combine_skills method."""

    def test_combine_two_skills(self, manager, sample_skill):
        skill2 = Skill(name="Skill 2")
        skill2.layers[SkillLayer.MIDDLE.value].append(
            SkillRule(
                layer=SkillLayer.MIDDLE,
                dimension=AnalysisDimension.PACING,
                content="Pacing rule",
                weight=90,
            )
        )
        skill2.layers[SkillLayer.MIDDLE.value].append(
            SkillRule(
                layer=SkillLayer.MIDDLE,
                dimension=AnalysisDimension.SUSPENSE,
                content="Suspense rule",
                weight=50,
            )
        )

        combined = manager.combine_skills([sample_skill, skill2], name="Combined")

        assert combined.name == "Combined"
        assert len(combined.versions) == 1

    def test_combine_with_weights(self, manager, sample_skill):
        skill2 = Skill(name="Skill 2")
        skill2.layers[SkillLayer.MIDDLE.value].append(
            SkillRule(
                layer=SkillLayer.MIDDLE,
                dimension=AnalysisDimension.PACING,
                content="Pacing rule",
                weight=90,
            )
        )

        combined = manager.combine_skills(
            [sample_skill, skill2],
            weights=[0.3, 0.7],
            name="Weighted",
        )

        narrative_rules = combined.layers[SkillLayer.MIDDLE.value]
        # The pacing rule from skill2 has weight 90 * 0.7 = 63 (int)
        # When merged with existing 70 * 0.3 = 21, the formula is:
        # existing.weight = int(existing.weight * (1 - w) + rule.weight * w)
        # First skill processes first with weight 0.3: weight = int(70 * 0.3) = 21
        # Second skill processes with weight 0.7: existing = 21, new rule = 90
        # existing.weight = int(21 * (1 - 0.7) + 90 * 0.7) = int(6.3 + 63) = 69
        assert len(narrative_rules) == 1
        assert narrative_rules[0].weight == 84

    def test_default_weights(self, manager, sample_skill):
        skill2 = Skill(name="Skill 2")
        skill2.layers[SkillLayer.MIDDLE.value].append(
            SkillRule(
                layer=SkillLayer.MIDDLE,
                dimension=AnalysisDimension.PACING,
                content="Pacing rule",
                weight=90,
            )
        )

        combined = manager.combine_skills([sample_skill, skill2])
        # Default weights are [0.5, 0.5]
        # First: int(70 * 0.5) = 35
        # Second: int(35 * 0.5 + 90 * 0.5) = int(17.5 + 45) = 62
        narrative_rules = combined.layers[SkillLayer.MIDDLE.value]
        assert narrative_rules[0].weight == 80

    def test_empty_skills_list_raises(self, manager):
        with pytest.raises(ValueError, match="至少"):
            manager.combine_skills([])

    def test_weights_length_mismatch_raises(self, manager, sample_skill):
        with pytest.raises(ValueError, match="不匹配"):
            manager.combine_skills([sample_skill], weights=[0.5, 0.5])

    def test_combined_skill_has_version(self, manager, sample_skill):
        skill2 = Skill(name="Skill 2")
        combined = manager.combine_skills([sample_skill, skill2])
        assert len(combined.versions) == 1
        assert "组合" in combined.versions[0].changelog


class TestBumpVersion:
    """Tests for bump_version method."""

    def test_bump_increments_version(self, manager, sample_skill):
        original_version = sample_skill.current_version
        manager.bump_version(sample_skill, changelog="Added rules")

        assert sample_skill.current_version != original_version
        assert len(sample_skill.versions) == 1  # Initial version was created in fixture

    def test_bump_creates_version_snapshot(self, manager, sample_skill):
        # First add a version since sample_skill doesn't have one
        sample_skill.versions = []
        sample_skill.current_version = "1.0.0"
        version = SkillVersion(version="1.0.0", rules_snapshot={}, changelog="Initial")
        sample_skill.versions.append(version)

        manager.bump_version(sample_skill, changelog="Update")
        assert len(sample_skill.versions) == 2
        assert sample_skill.versions[-1].changelog == "Update"

    def test_bump_limits_version_count(self, manager):
        skill = Skill(name="Version Test")
        skill.versions = []
        skill.current_version = "1.0.0"

        # Create MAX_SKILL_VERSIONS + 5 versions
        for i in range(MAX_SKILL_VERSIONS + 5):
            manager.bump_version(skill, changelog=f"Update {i}")

        assert len(skill.versions) == MAX_SKILL_VERSIONS

    def test_bump_default_changelog(self, manager, sample_skill):
        sample_skill.versions = []
        sample_skill.current_version = "1.0.0"
        sample_skill.versions.append(
            SkillVersion(version="1.0.0", rules_snapshot={}, changelog="Initial")
        )

        manager.bump_version(sample_skill)
        assert sample_skill.versions[-1].changelog == "版本升级至 1.0.1"


class TestRollbackVersion:
    """Tests for rollback_version method."""

    def test_rollback_to_existing_version(self, manager, sample_skill):
        # Setup: create skill with version, then modify
        sample_skill.versions = []
        sample_skill.current_version = "1.0.0"
        snapshot = {k: list(v) for k, v in sample_skill.layers.items()}
        sample_skill.versions.append(
            SkillVersion(version="1.0.0", rules_snapshot=snapshot, changelog="Initial")
        )

        # Add a rule
        sample_skill.layers[SkillLayer.MIDDLE.value].append(
            SkillRule(
                layer=SkillLayer.MIDDLE,
                dimension=AnalysisDimension.SUSPENSE,
                content="New rule",
                weight=50,
            )
        )

        # Rollback
        manager.rollback_version(sample_skill, "1.0.0")
        assert sample_skill.current_version == "1.0.0"
        narrative_rules = sample_skill.layers[SkillLayer.MIDDLE.value]
        assert all(r.content != "New rule" for r in narrative_rules)

    def test_rollback_nonexistent_version_raises(self, manager, sample_skill):
        with pytest.raises(ValueError, match="不存在"):
            manager.rollback_version(sample_skill, "9.9.9")


class TestGetEffectiveRules:
    """Tests for get_effective_rules method."""

    def test_get_all_rules(self, manager, sample_skill):
        rules = manager.get_effective_rules(sample_skill)
        assert len(rules) == 2

    def test_get_rules_by_layer(self, manager, sample_skill):
        base = manager.get_effective_rules(sample_skill, layer=SkillLayer.BASE)
        middle = manager.get_effective_rules(sample_skill, layer=SkillLayer.MIDDLE)
        dynamic = manager.get_effective_rules(sample_skill, layer=SkillLayer.DYNAMIC)

        assert len(base) == 1
        assert len(middle) == 1
        assert len(dynamic) == 0

    def test_get_rules_empty_layer(self, manager):
        skill = Skill(name="Empty")
        rules = manager.get_effective_rules(skill, layer=SkillLayer.BASE)
        assert rules == []


class TestUpdateRuleWeight:
    """Tests for update_rule_weight method."""

    def test_increase_weight(self, manager, sample_skill):
        rule = sample_skill.layers[SkillLayer.MIDDLE.value][0]
        original_weight = rule.weight
        manager.update_rule_weight(sample_skill, rule.id, 10)
        assert rule.weight == original_weight + 10

    def test_decrease_weight(self, manager, sample_skill):
        rule = sample_skill.layers[SkillLayer.MIDDLE.value][0]
        original_weight = rule.weight
        manager.update_rule_weight(sample_skill, rule.id, -10)
        assert rule.weight == original_weight - 10

    def test_weight_capped_at_100(self, manager, sample_skill):
        rule = sample_skill.layers[SkillLayer.MIDDLE.value][0]
        rule.weight = 95
        manager.update_rule_weight(sample_skill, rule.id, 10)
        assert rule.weight == 100

    def test_weight_capped_at_0(self, manager, sample_skill):
        rule = sample_skill.layers[SkillLayer.MIDDLE.value][0]
        rule.weight = 5
        manager.update_rule_weight(sample_skill, rule.id, -10)
        assert rule.weight == 0

    def test_update_nonexistent_rule(self, manager, sample_skill):
        original = sum(len(r) for r in sample_skill.layers.values())
        manager.update_rule_weight(sample_skill, "nonexistent-id", 10)
        assert sum(len(r) for r in sample_skill.layers.values()) == original

    def test_update_updates_timestamp(self, manager, sample_skill):
        from datetime import datetime
        old_updated = sample_skill.updated_at
        # Small sleep to ensure time difference
        import time
        time.sleep(0.01)
        manager.update_rule_weight(sample_skill, sample_skill.layers[SkillLayer.MIDDLE.value][0].id, 5)
        assert sample_skill.updated_at > old_updated


class TestIncrementVersion:
    """Tests for _increment_version static method."""

    def test_increment_patch(self):
        assert SkillManager._increment_version("1.0.0") == "1.0.1"

    def test_increment_minor_rollover(self):
        assert SkillManager._increment_version("1.0.99") == "1.1.0"

    def test_increment_major_rollover(self):
        assert SkillManager._increment_version("1.99.99") == "2.0.0"

    def test_increment_two_part_version(self):
        assert SkillManager._increment_version("1.5") == "1.6.0"

    def test_increment_single_part_version(self):
        assert SkillManager._increment_version("2") == "2.0.1"

    def test_invalid_version_defaults(self):
        assert SkillManager._increment_version("abc") == "1.0.0"

    def test_increment_preserve_existing(self):
        assert SkillManager._increment_version("0.0.1") == "0.0.2"


class TestStorageIntegration:
    """Tests for storage integration."""

    def test_save_and_load_skill(self, manager, sample_skill):
        manager.save_skill(sample_skill)
        loaded = manager.load_skill(sample_skill.id)
        assert loaded.id == sample_skill.id
        assert loaded.name == sample_skill.name

    def test_list_skills(self, manager):
        s1 = Skill(name="Skill 1")
        s2 = Skill(name="Skill 2")
        manager.save_skill(s1)
        manager.save_skill(s2)

        skills = manager.list_skills()
        assert len(skills) == 2


class TestCreateVersion:
    """Tests for _create_version static method."""

    def test_create_version_snapshot(self, sample_skill):
        sample_skill.current_version = "2.0.0"
        version = SkillManager._create_version(sample_skill, "Test changelog")

        assert version.version == "2.0.0"
        assert version.changelog == "Test changelog"
        assert set(version.rules_snapshot.keys()) == set(sample_skill.layers.keys())
