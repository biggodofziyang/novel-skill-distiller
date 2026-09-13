"""TDD coverage for the user's main workbench journeys."""

import threading
import time
import zipfile
from io import BytesIO

import pytest
from streamlit.testing.v1 import AppTest

from core.job_manager import JobManager
from core.skill_library import list_packages, package_context
from core.workspace import WorkspaceStore
from services.quality_reviewer import review_chapter
from services.skill_evaluator import compare_skills


def _store(tmp_path, monkeypatch) -> WorkspaceStore:
    monkeypatch.setattr("core.workspace.WORKSPACE_ROOT", tmp_path)
    return WorkspaceStore("journey")


def test_workspace_round_trip_and_custom_folder(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    folder = store.create_folder("草稿")
    path = store.save_text(folder.name, "scene.md", "一段正文")
    assert store.read_file("草稿/scene.md") == "一段正文"
    assert any(item["name"] == "草稿" and not item["system"] for item in store.list_tree())
    store.delete_folder("草稿")
    assert not path.exists()


def test_workspace_creates_and_deletes_editable_markdown_file(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    store.create_folder("草稿")

    path = store.create_file("草稿", "第一章")

    assert path.name == "第一章.md"
    assert store.read_file("草稿/第一章.md") == ""
    with pytest.raises(FileExistsError):
        store.create_file("草稿", "第一章.md")

    store.delete_file("草稿/第一章.md")
    assert not path.exists()


def test_workspace_file_creation_requires_existing_folder(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)

    with pytest.raises(FileNotFoundError):
        store.create_file("不存在", "草稿")


def test_skill_library_contains_openai_docs():
    packages = list_packages()
    package = next(item for item in packages if item.package_id == "openai-docs")
    assert package.file_count > 0
    assert "feedback" in package.modules
    assert "OpenAI Docs" in package_context([package.package_id])


def test_job_manager_completes_and_supports_cancel(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    manager = JobManager(store)
    finished = threading.Event()

    def processor(control, job):
        for _ in range(20):
            if not control.checkpoint():
                return ""
            time.sleep(0.005)
        finished.set()
        return "任务记录/result.json"

    job = manager.start("review", "测试任务", [], processor)
    assert manager.active_job("review").job_id == job.job_id
    manager.pause(job.job_id)
    time.sleep(0.02)
    assert manager.get(job.job_id).status == "paused"
    manager.resume(job.job_id)
    assert finished.wait(2)
    deadline = time.time() + 2
    while time.time() < deadline and manager.get(job.job_id).status != "completed":
        time.sleep(0.01)
    assert manager.get(job.job_id).status == "completed"

    cancelled = manager.start("review", "取消任务", [], processor)
    manager.cancel(cancelled.job_id)
    time.sleep(0.05)
    assert manager.get(cancelled.job_id).status in {"cancelling", "cancelled"}


def test_quality_review_and_skill_ab_are_deterministic():
    report = review_chapter("他推门而入。" * 300, "第001章")
    assert 0 <= report["score"] <= 100
    assert report["metrics"]["characters"] > 0
    result = compare_skills("旧版", "# 规则\n必须检查。", "新版", "# 规则\n## 示例\n必须检查、验证和回滚。")
    assert result["winner"] == "新版"
    assert result["scores"]["新版"] >= result["scores"]["旧版"]
def test_all_workbench_modules_render_without_exception():
    for key in ("home", "conversation", "skill", "tracking", "feedback", "review", "settings"):
        app = AppTest.from_file("../app.py").run()
        app.button(key=f"nav2_{key}").click().run()
        assert not app.exception, f"module {key} raised: {app.exception}"



def test_workbench_navigation_places_distill_after_chapters():
    from ui.workbench_full import MODULES

    keys = list(MODULES)
    assert keys == [
        "home",
        "material",
        "skill",
        "creation",
        "chapters",
        "distill",
        "tracking",
        "feedback",
        "review",
        "settings",
    ]


def test_workbench_gives_half_the_page_to_file_workspace():
    from ui.workbench_full import FILE_WORKSPACE_COLUMNS, WORKBENCH_COLUMNS

    assert WORKBENCH_COLUMNS == (1, 1)
    assert FILE_WORKSPACE_COLUMNS[0] > FILE_WORKSPACE_COLUMNS[1]


@pytest.mark.parametrize(
    ("module", "placeholder"),
    [
        ("chapters", "和 AI 讨论本章怎么写..."),
        ("distill", "和 AI 讨论如何提炼与改进规则..."),
        ("creation", "和 AI 讨论世界观、人物或黄金三章..."),
    ],
)
def test_creation_modules_use_dedicated_ai_studio(module, placeholder):
    app = AppTest.from_file("../app.py").run()

    app.button(key="nav2_conversation").click().run()
    app.radio(key="conversation_mode").set_value(module).run()

    assert not app.exception
    assert len(app.chat_input) == 1
    assert app.chat_input[0].placeholder == placeholder
    assert app.button(key=f"studio_new_{module}")


def test_studio_prompt_keeps_recent_conversation_and_module_contract():
    from core.studio_chat import build_studio_prompt

    prompt = build_studio_prompt(
        "chapters",
        "把结尾改得更有悬念",
        [
            {"role": "user", "content": "先写一版"},
            {"role": "assistant", "content": "这是第一版正文"},
        ],
        {"章节": 3, "标题": "雨夜追凶"},
    )

    assert "章节写作" in prompt
    assert "这是第一版正文" in prompt
    assert "把结尾改得更有悬念" in prompt
    assert "不得声称已经保存" in prompt


def test_studio_sessions_are_saved_independently(tmp_path, monkeypatch):
    from core.studio_chat import load_sessions, new_session, save_session

    store = _store(tmp_path, monkeypatch)
    chapter_session = new_session(store, "chapters")
    chapter_session["messages"].append({"role": "user", "content": "续写第三章"})
    save_session(store, chapter_session)
    creation_session = new_session(store, "creation")
    creation_session["messages"].append({"role": "user", "content": "设计世界观"})
    save_session(store, creation_session)

    chapters = load_sessions(store, "chapters")
    creation = load_sessions(store, "creation")

    assert chapters[0]["messages"][0]["content"] == "续写第三章"
    assert creation[0]["messages"][0]["content"] == "设计世界观"
    assert chapters[0]["id"] != creation[0]["id"]


def test_distill_uses_only_valid_analysis_outputs(tmp_path, monkeypatch):
    from ui.workbench_full import _distill_analysis_files

    store = _store(tmp_path, monkeypatch)
    store.save_json("拆解结果", "empty.json", {"analyses": []})
    store.save_json("拆解结果", "valid.json", {"analyses": [{"dimension": "节奏"}]})

    assert [path.name for path in _distill_analysis_files(store)] == ["valid.json"]


def test_analysis_result_can_be_edited_into_readable_markdown():
    from core.analysis_skill import analysis_to_markdown

    text = analysis_to_markdown({
        "source": "小说资料/样本.txt",
        "analyses": [{
            "dimension": "节奏",
            "summary": "前三章持续制造小目标。",
            "rules": [{
                "content": "每章结尾留下未完成动作。",
                "weight": 85,
                "explanation": "推动读者继续阅读。",
                "examples": ["门外忽然传来脚步声。"],
            }],
        }],
    })

    assert "样本.txt" in text
    assert "## 节奏" in text
    assert "每章结尾留下未完成动作" in text
    assert "推动读者继续阅读" in text


def test_skill_prompt_combines_edited_analysis_and_author_direction():
    from core.analysis_skill import build_analysis_skill_prompt

    prompt = build_analysis_skill_prompt(
        "我的悬疑写作法",
        "希望更强调普通人视角，不要强行反转。",
        "## 节奏\n每章结尾留下未完成动作。",
    )

    assert "我的悬疑写作法" in prompt
    assert "普通人视角" in prompt
    assert "每章结尾留下未完成动作" in prompt
    assert "SKILL.md" in prompt
    assert "name 和 description" in prompt


def test_generated_skill_is_normalized_and_packaged():
    from core.analysis_skill import build_skill_zip, normalize_skill_markdown

    normalized = normalize_skill_markdown(
        "我的悬疑写作法",
        "用于创作克制的现实悬疑小说。",
        "```markdown\n# 工作流\n先确认人物目标，再设计悬念。\n```",
    )

    assert normalized.startswith("---\nname: novel-writing-skill\n")
    assert "description:" in normalized
    assert "```" not in normalized
    archive_bytes = build_skill_zip("novel-writing-skill", normalized)
    with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
        assert archive.namelist() == ["novel-writing-skill/SKILL.md"]
        assert archive.read(archive.namelist()[0]).decode("utf-8") == normalized


def test_generated_skill_package_becomes_selectable(tmp_path, monkeypatch):
    from core.analysis_skill import build_skill_zip
    from core import skill_library

    monkeypatch.setattr(skill_library, "SKILL_LIBRARY_DIR", tmp_path / "library")
    monkeypatch.setattr(skill_library, "SOURCE_DIR", tmp_path / "missing")
    content = "---\nname: suspense-skill\ndescription: test\n---\n\n# Rules\n"
    skill_library.import_package(
        "suspense-skill-v1.zip",
        build_skill_zip("suspense-skill", content),
    )

    package = skill_library.list_packages()[0]
    assert package.read_entry() == content
    assert package in skill_library.packages_for_module("chapters")


def test_material_page_exposes_analysis_editor_and_skill_generator(tmp_path, monkeypatch):
    monkeypatch.setattr("core.workspace.WORKSPACE_ROOT", tmp_path)
    store = WorkspaceStore("default")
    store.save_json("拆解结果", "sample.json", {
        "source": "小说资料/sample.txt",
        "analyses": [{"dimension": "节奏", "summary": "节奏紧凑", "rules": []}],
    })

    app = AppTest.from_file("../app.py").run()
    app.button(key="nav2_conversation").click().run()

    assert not app.exception
    assert app.text_area(key="analysis_result_editor")
    assert app.text_area(key="analysis_author_direction")
    assert app.text_input(key="analysis_skill_name")
    assert app.button(key="generate_analysis_skill")


def test_four_modes_share_one_conversation_entry():
    from ui.workbench_full import NAVIGATION_MODULES

    assert "conversation" in NAVIGATION_MODULES
    assert "skill" in NAVIGATION_MODULES
    assert not {"material", "creation", "chapters", "distill"}.intersection(NAVIGATION_MODULES)
    app = AppTest.from_file("../app.py").run()
    app.button(key="nav2_conversation").click().run()
    assert app.radio(key="conversation_mode").options == ["素材拆解", "分步创作", "章节写作", "规则蒸馏"]
    assert len(app.chat_input) == 1


def test_material_mode_has_independent_studio_history(tmp_path, monkeypatch):
    from core.studio_chat import load_sessions, new_session, save_session

    store = _store(tmp_path, monkeypatch)
    session = new_session(store, "material")
    session["messages"].append({"role": "user", "content": "分析开篇冲突"})
    save_session(store, session)
    assert load_sessions(store, "material")[0]["messages"][0]["content"] == "分析开篇冲突"
    assert load_sessions(store, "chapters") == []


def test_entering_chapter_mode_does_not_save_empty_chapter(tmp_path, monkeypatch):
    monkeypatch.setattr("core.workspace.WORKSPACE_ROOT", tmp_path)
    app = AppTest.from_file("../app.py").run()
    app.button(key="nav2_conversation").click().run()
    app.radio(key="conversation_mode").set_value("chapters").run()
    assert not app.exception
    assert list((WorkspaceStore("default").root / "章节内容").glob("*")) == []


def test_unified_chat_restores_draft_and_keeps_sessions_separate(tmp_path, monkeypatch):
    monkeypatch.setattr("core.workspace.WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr("ui.workbench_full._generate", lambda *args: "这是当前章节的正文草稿")
    app = AppTest.from_file("../app.py").run()
    app.button(key="nav2_conversation").click().run()
    app.radio(key="conversation_mode").set_value("chapters").run()
    app.chat_input(key="studio_input_chapters").set_value("写雨夜相遇这一章").run()
    assert not app.exception
    first_id = app.session_state["studio_active_chapters"]
    app.radio(key="conversation_mode").set_value("creation").run()
    app.radio(key="conversation_mode").set_value("chapters").run()
    assert app.text_area(key="studio_editor_chapters_新建章节").value == "这是当前章节的正文草稿"
    app.button(key="studio_new_chapters").click().run()
    assert app.text_area(key="studio_editor_chapters_新建章节").value == ""
    app.button(key=f"studio_session_chapters_{first_id}").click().run()
    assert app.text_area(key="studio_editor_chapters_新建章节").value == "这是当前章节的正文草稿"
    assert not app.exception
    app.button(key="nav2_skill").click().run()
    app.button(key="nav2_conversation").click().run()
    assert app.radio(key="conversation_mode").value == "chapters"


def test_studio_storage_skips_damaged_files_and_rejects_bad_modes(tmp_path, monkeypatch):
    from core.studio_chat import build_studio_prompt, load_sessions, new_session, save_session

    store = _store(tmp_path, monkeypatch)
    store.save_text("迭代记录", "studio_material_bad.json", "not-json")
    store.save_json("迭代记录", "studio_material_wrong.json", {"module": "chapters", "messages": [], "id": "wrong"})
    assert load_sessions(store, "material") == []
    with pytest.raises(ValueError):
        new_session(store, "unknown")
    with pytest.raises(ValueError):
        save_session(store, {"module": "material", "id": ""})
    history = [{"role": "user", "content": f"历史{i}"} for i in range(12)]
    prompt = build_studio_prompt("material", "最新请求", history, {})
    assert "历史0\n" not in prompt
    assert "历史11" in prompt

