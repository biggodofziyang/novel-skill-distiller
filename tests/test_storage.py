"""Tests for core.storage module."""

import json
from pathlib import Path

import pytest

from core.constants import (
    ANALYSIS_DIR,
    FEEDBACK_DIR,
    MATERIAL_DIR,
    PROJECT_STORAGE_DIR,
    RULE_DIR,
    SKILL_DIR,
)
from core.models import (
    AnalysisDimension,
    AnalysisFile,
    AnalysisRule,
    CreationProject,
    DistillMode,
    FeedbackCategory,
    FeedbackSample,
    FeedbackType,
    NovelMaterial,
    Rule,
    RuleSet,
    Skill,
    SkillStatus,
)
from core.storage import StorageManager


@pytest.fixture
def storage(tmp_path, monkeypatch):
    """Provide a StorageManager with temporary directories."""
    # Override constants to use temp paths
    monkeypatch.setattr("core.storage.MATERIAL_DIR", tmp_path / "materials")
    monkeypatch.setattr("core.storage.ANALYSIS_DIR", tmp_path / "analysis")
    monkeypatch.setattr("core.storage.RULE_DIR", tmp_path / "rules")
    monkeypatch.setattr("core.storage.SKILL_DIR", tmp_path / "skills")
    monkeypatch.setattr("core.storage.PROJECT_STORAGE_DIR", tmp_path / "projects")
    monkeypatch.setattr("core.storage.FEEDBACK_DIR", tmp_path / "feedback")
    monkeypatch.setattr("core.storage.TEMP_DIR", tmp_path / "temp")
    # Also need to patch constants imported directly
    monkeypatch.setattr("core.constants.MATERIAL_DIR", tmp_path / "materials")
    monkeypatch.setattr("core.constants.ANALYSIS_DIR", tmp_path / "analysis")
    monkeypatch.setattr("core.constants.RULE_DIR", tmp_path / "rules")
    monkeypatch.setattr("core.constants.SKILL_DIR", tmp_path / "skills")
    monkeypatch.setattr("core.constants.PROJECT_STORAGE_DIR", tmp_path / "projects")
    monkeypatch.setattr("core.constants.FEEDBACK_DIR", tmp_path / "feedback")
    monkeypatch.setattr("core.constants.TEMP_DIR", tmp_path / "temp")
    monkeypatch.setattr("core.constants.LOG_DIR", tmp_path / "logs")

    sm = StorageManager()
    return sm


class TestStorageManagerInit:
    """Tests for StorageManager initialization."""

    def test_creates_directories(self, tmp_path, monkeypatch):
        monkeypatch.setattr("core.storage.MATERIAL_DIR", tmp_path / "m")
        monkeypatch.setattr("core.storage.ANALYSIS_DIR", tmp_path / "a")
        monkeypatch.setattr("core.storage.RULE_DIR", tmp_path / "r")
        monkeypatch.setattr("core.storage.SKILL_DIR", tmp_path / "s")
        monkeypatch.setattr("core.storage.PROJECT_STORAGE_DIR", tmp_path / "p")
        monkeypatch.setattr("core.storage.FEEDBACK_DIR", tmp_path / "f")
        monkeypatch.setattr("core.storage.TEMP_DIR", tmp_path / "t")
        monkeypatch.setattr("core.constants.LOG_DIR", tmp_path / "l")

        StorageManager()
        assert (tmp_path / "m").exists()
        assert (tmp_path / "a").exists()
        assert (tmp_path / "r").exists()
        assert (tmp_path / "s").exists()
        assert (tmp_path / "p").exists()
        assert (tmp_path / "f").exists()
        assert (tmp_path / "t").exists()


class TestMaterialStorage:
    """Tests for material CRUD operations."""

    def test_save_and_load_material(self, storage):
        material = NovelMaterial(filename="test.txt", raw_text="Hello world", file_size=11)
        path = storage.save_material(material)
        assert path.exists()

        loaded = storage.load_material(material.id)
        assert loaded.id == material.id
        assert loaded.filename == material.filename
        assert loaded.raw_text == material.raw_text

    def test_list_materials(self, storage):
        m1 = NovelMaterial(filename="a.txt", raw_text="A")
        m2 = NovelMaterial(filename="b.txt", raw_text="B")
        storage.save_material(m1)
        storage.save_material(m2)

        materials = storage.list_materials()
        assert len(materials) == 2
        ids = {m.id for m in materials}
        assert m1.id in ids
        assert m2.id in ids

    def test_list_materials_skips_invalid(self, storage, monkeypatch):
        # Save a valid material
        m1 = NovelMaterial(filename="a.txt", raw_text="A")
        storage.save_material(m1)
        # Create an invalid JSON file
        invalid_path = storage.save_material(m1).parent / "invalid.json"
        invalid_path.write_text("not json", encoding="utf-8")

        materials = storage.list_materials()
        assert len(materials) == 1

    def test_delete_material(self, storage):
        m = NovelMaterial(filename="test.txt", raw_text="Hello")
        storage.save_material(m)
        assert storage.delete_material(m.id) is True
        assert storage.delete_material(m.id) is False

    def test_load_material_not_found(self, storage):
        with pytest.raises(Exception):
            storage.load_material("nonexistent-id")


class TestAnalysisStorage:
    """Tests for analysis CRUD operations."""

    def test_save_and_load_analysis(self, storage):
        analysis = AnalysisFile(
            material_id="mid-1",
            dimension=AnalysisDimension.PACING,
            rules=[AnalysisRule(content="Rule 1", weight=70)],
            summary="Summary",
        )
        path = storage.save_analysis(analysis)
        assert path.exists()

        loaded = storage.load_analysis(analysis.id)
        assert loaded.id == analysis.id
        assert loaded.dimension == AnalysisDimension.PACING
        assert len(loaded.rules) == 1

    def test_list_analysis_by_material(self, storage):
        a1 = AnalysisFile(material_id="mid-1", dimension=AnalysisDimension.PACING)
        a2 = AnalysisFile(material_id="mid-1", dimension=AnalysisDimension.SUSPENSE)
        a3 = AnalysisFile(material_id="mid-2", dimension=AnalysisDimension.CHARACTER)
        storage.save_analysis(a1)
        storage.save_analysis(a2)
        storage.save_analysis(a3)

        results = storage.list_analysis_by_material("mid-1")
        assert len(results) == 2
        dimensions = {r.dimension for r in results}
        assert AnalysisDimension.PACING in dimensions
        assert AnalysisDimension.SUSPENSE in dimensions

    def test_delete_analysis(self, storage):
        a = AnalysisFile(material_id="mid", dimension=AnalysisDimension.PACING)
        storage.save_analysis(a)
        assert storage.delete_analysis(a.id) is True
        assert storage.delete_analysis(a.id) is False


class TestRuleSetStorage:
    """Tests for rule set CRUD operations."""

    def test_save_and_load_rule_set(self, storage):
        rule = Rule(dimension=AnalysisDimension.PACING, content="Pacing rule", weight=60)
        rs = RuleSet(
            name="Test Set",
            distill_mode=DistillMode.FULL,
            rules={"节奏": [rule]},
        )
        path = storage.save_rule_set(rs)
        assert path.exists()

        loaded = storage.load_rule_set(rs.id)
        assert loaded.id == rs.id
        assert loaded.name == "Test Set"
        assert "节奏" in loaded.rules

    def test_list_rule_sets(self, storage):
        rs1 = RuleSet(name="Set 1", distill_mode=DistillMode.FULL)
        rs2 = RuleSet(name="Set 2", distill_mode=DistillMode.INCREMENTAL)
        storage.save_rule_set(rs1)
        storage.save_rule_set(rs2)

        sets = storage.list_rule_sets()
        assert len(sets) == 2

    def test_delete_rule_set(self, storage):
        rs = RuleSet(name="Set", distill_mode=DistillMode.FULL)
        storage.save_rule_set(rs)
        assert storage.delete_rule_set(rs.id) is True
        assert storage.delete_rule_set(rs.id) is False


class TestSkillStorage:
    """Tests for skill CRUD operations."""

    def test_save_and_load_skill(self, storage):
        skill = Skill(name="Test Skill", description="A test skill")
        path = storage.save_skill(skill)
        assert path.exists()

        loaded = storage.load_skill(skill.id)
        assert loaded.id == skill.id
        assert loaded.name == "Test Skill"
        assert loaded.status == SkillStatus.DRAFT

    def test_list_skills(self, storage):
        s1 = Skill(name="Skill 1")
        s2 = Skill(name="Skill 2")
        storage.save_skill(s1)
        storage.save_skill(s2)

        skills = storage.list_skills()
        assert len(skills) == 2

    def test_delete_skill(self, storage):
        s = Skill(name="Skill")
        storage.save_skill(s)
        assert storage.delete_skill(s.id) is True
        assert storage.delete_skill(s.id) is False


class TestProjectStorage:
    """Tests for project CRUD operations."""

    def test_save_and_load_project(self, storage):
        project = CreationProject(name="Test Project")
        path = storage.save_project(project)
        assert path.exists()

        loaded = storage.load_project(project.id)
        assert loaded.id == project.id
        assert loaded.name == "Test Project"

    def test_list_projects(self, storage):
        p1 = CreationProject(name="Project 1")
        p2 = CreationProject(name="Project 2")
        storage.save_project(p1)
        storage.save_project(p2)

        projects = storage.list_projects()
        assert len(projects) == 2

    def test_delete_project(self, storage):
        p = CreationProject(name="Project")
        storage.save_project(p)
        assert storage.delete_project(p.id) is True

    def test_delete_project_with_snapshots(self, storage):
        p = CreationProject(name="Project")
        storage.save_project(p)
        storage.save_locked_snapshot(p.id, "世界观", "Snapshot content")
        snapshot_dir = storage.save_locked_snapshot(
            p.id, "世界观", "Snapshot content"
        ).parent
        assert snapshot_dir.exists()

        storage.delete_project(p.id)
        assert not snapshot_dir.exists()

    def test_save_and_load_locked_snapshot(self, storage):
        p = CreationProject(name="Project")
        storage.save_project(p)
        path = storage.save_locked_snapshot(p.id, "世界观", "Content here")
        assert path.exists()

        content = storage.load_locked_snapshot(p.id, "世界观")
        assert content == "Content here"

    def test_load_locked_snapshot_not_found(self, storage):
        content = storage.load_locked_snapshot("nonexistent", "世界观")
        assert content == ""


class TestFeedbackStorage:
    """Tests for feedback CRUD operations."""

    def test_save_and_load_feedback(self, storage):
        fb = FeedbackSample(
            project_id="pid-1",
            feedback_type=FeedbackType.POSITIVE,
            content="Great work",
        )
        path = storage.save_feedback(fb)
        assert path.exists()

        loaded = storage.load_feedback(fb.id)
        assert loaded.id == fb.id
        assert loaded.content == "Great work"

    def test_list_feedback_by_project(self, storage):
        fb1 = FeedbackSample(project_id="pid-1", feedback_type=FeedbackType.POSITIVE, content="Good")
        fb2 = FeedbackSample(project_id="pid-1", feedback_type=FeedbackType.NEGATIVE, content="Bad")
        fb3 = FeedbackSample(project_id="pid-2", feedback_type=FeedbackType.POSITIVE, content="OK")
        storage.save_feedback(fb1)
        storage.save_feedback(fb2)
        storage.save_feedback(fb3)

        results = storage.list_feedback_by_project("pid-1")
        assert len(results) == 2

    def test_delete_feedback(self, storage):
        fb = FeedbackSample(project_id="pid", feedback_type=FeedbackType.POSITIVE, content="Test")
        storage.save_feedback(fb)
        assert storage.delete_feedback(fb.id) is True
        assert storage.delete_feedback(fb.id) is False


class TestDataConversion:
    """Tests for data format conversion methods."""

    def test_to_markdown(self, storage):
        rule = Rule(dimension=AnalysisDimension.PACING, content="Keep pacing fast", weight=80)
        rs = RuleSet(
            name="Pacing Rules",
            distill_mode=DistillMode.FULL,
            rules={"节奏": [rule]},
        )
        md = storage.to_markdown(rs)
        assert "# Pacing Rules" in md
        assert "全量" in md
        assert "Keep pacing fast" in md
        assert "80" in md

    def test_skill_to_markdown(self, storage):
        from core.models import SkillRule
        from core.constants import SkillLayer

        skill = Skill(name="Test Skill", description="A skill")
        skill.layers[SkillLayer.MIDDLE.value].append(
            SkillRule(
                layer=SkillLayer.MIDDLE,
                dimension=AnalysisDimension.PACING,
                content="Fast pacing",
                weight=75,
            )
        )
        md = storage.skill_to_markdown(skill)
        assert "# Skill: Test Skill" in md
        assert "A skill" in md
        assert "Fast pacing" in md
        assert "75" in md


class TestJsonReadWrite:
    """Tests for static JSON read/write methods."""

    def test_write_and_read_json(self, tmp_path):
        path = tmp_path / "test.json"
        data = {"key": "value", "number": 42}
        StorageManager._write_json(path, data)
        assert path.exists()

        result = StorageManager._read_json(path)
        assert result == data

    def test_read_json_invalid(self, tmp_path):
        path = tmp_path / "invalid.json"
        path.write_text("not json", encoding="utf-8")
        with pytest.raises(Exception):
            StorageManager._read_json(path)

    def test_write_markdown_and_read(self, tmp_path):
        path = tmp_path / "test.md"
        content = "# Hello\n\nWorld"
        StorageManager._write_markdown(path, content)
        assert path.exists()

        result = StorageManager._read_markdown(path)
        assert result == content

    def test_read_markdown_not_found(self, tmp_path):
        path = tmp_path / "missing.md"
        with pytest.raises(Exception):
            StorageManager._read_markdown(path)
