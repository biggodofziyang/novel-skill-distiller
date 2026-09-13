"""Regression tests for workbench storage and local chapter review."""

import pytest

from core.workspace import WorkspaceStore
from services.quality_reviewer import review_chapter


def test_workspace_rejects_escape_path(tmp_path, monkeypatch):
    monkeypatch.setattr("core.workspace.WORKSPACE_ROOT", tmp_path)
    store = WorkspaceStore("safe")
    with pytest.raises(ValueError):
        store.save_text("小说资料", "..\\..\\outside.md", "must stay inside")


def test_chapter_review_returns_actionable_metrics():
    report = review_chapter("第一段。" * 200, "第001章")
    assert report["title"] == "第001章"
    assert "score" in report
    assert "metrics" in report
    assert any(item["code"] == "ending" for item in report["issues"])

