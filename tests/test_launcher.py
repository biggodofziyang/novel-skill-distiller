"""Regression tests for desktop launcher service refresh decisions."""

from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import ModuleType


def _load_launcher() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "launcher.pyw"
    return SourceFileLoader("novel_launcher", str(path)).load_module()


def test_running_service_without_runtime_state_is_restarted():
    launcher = _load_launcher()
    assert launcher._should_restart(True, None, "new-stamp") is True


def test_running_service_with_current_source_is_reused():
    launcher = _load_launcher()
    state = {"source_stamp": "same-stamp", "pid": 123}
    assert launcher._should_restart(True, state, "same-stamp") is False


def test_changed_source_restarts_running_service():
    launcher = _load_launcher()
    state = {"source_stamp": "old-stamp", "pid": 123}
    assert launcher._should_restart(True, state, "new-stamp") is True


def test_only_expected_streamlit_command_is_owned():
    launcher = _load_launcher()
    assert launcher._is_expected_service_command(
        "python.exe -m streamlit run app.py --server.port 8501"
    )
    assert not launcher._is_expected_service_command(
        "python.exe -m streamlit run another_app.py --server.port 8501"
    )
