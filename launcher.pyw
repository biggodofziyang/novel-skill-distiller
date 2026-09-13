"""Start the local Streamlit app and open it in the default browser."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path


APP_URL = "http://127.0.0.1:8501"
PROJECT_DIR = Path(__file__).resolve().parent
LOG_PATH = PROJECT_DIR / "launcher.log"
RUNTIME_PATH = PROJECT_DIR / ".launcher-runtime.json"


def _log(message: str) -> None:
    with LOG_PATH.open("a", encoding="utf-8") as log_file:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_file.write(f"[{timestamp}] {message}\n")


def _app_is_ready() -> bool:
    try:
        with urllib.request.urlopen(APP_URL, timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def _source_stamp() -> str:
    """Return a stable stamp for code that the Streamlit process imports."""
    paths = [PROJECT_DIR / "app.py", PROJECT_DIR / "launcher.pyw"]
    for folder in ("core", "services", "ui"):
        paths.extend((PROJECT_DIR / folder).rglob("*.py"))
    mtimes = [path.stat().st_mtime_ns for path in paths if path.is_file()]
    return str(max(mtimes, default=0))


def _load_runtime() -> dict[str, object] | None:
    try:
        data = json.loads(RUNTIME_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError, TypeError):
        return None


def _save_runtime(pid: int, source_stamp: str) -> None:
    temporary = RUNTIME_PATH.with_suffix(".tmp")
    temporary.write_text(
        json.dumps({"pid": pid, "source_stamp": source_stamp}, indent=2),
        encoding="utf-8",
    )
    temporary.replace(RUNTIME_PATH)


def _should_restart(
    app_ready: bool,
    runtime: dict[str, object] | None,
    source_stamp: str,
) -> bool:
    if not app_ready:
        return False
    return not runtime or runtime.get("source_stamp") != source_stamp


def _is_expected_service_command(command_line: str) -> bool:
    command = " ".join((command_line or "").lower().split())
    return (
        "-m streamlit" in command
        and "run app.py" in command
        and "--server.port 8501" in command
    )


def _listener_pid() -> int | None:
    command = (
        "$item = Get-NetTCPConnection -LocalPort 8501 -State Listen "
        "-ErrorAction SilentlyContinue | Select-Object -First 1; "
        "if ($item) { $item.OwningProcess }"
    )
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
        timeout=8,
        check=False,
    )
    value = completed.stdout.strip()
    return int(value) if value.isdigit() else None


def _process_command_line(pid: int) -> str:
    command = (
        f"$item = Get-CimInstance Win32_Process -Filter 'ProcessId={pid}'; "
        "if ($item) { $item.CommandLine }"
    )
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
        timeout=8,
        check=False,
    )
    return completed.stdout.strip()


def _stop_project_service(pid: int) -> None:
    command_line = _process_command_line(pid)
    if not _is_expected_service_command(command_line):
        raise RuntimeError("8501 端口被其他程序占用，未自动关闭。")
    subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
        timeout=12,
        check=False,
    )
    for _ in range(40):
        if not _app_is_ready():
            return
        time.sleep(0.25)
    raise RuntimeError("旧服务未能停止，请稍后重试。")


def _show_error(message: str) -> None:
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, message, "网文创作Skill蒸馏系统", 0x10)
    except Exception:
        pass


def main() -> None:
    try:
        source_stamp = _source_stamp()
        app_ready = _app_is_ready()
        runtime = _load_runtime()
        listener_pid = _listener_pid() if app_ready else None
        runtime_pid = runtime.get("pid") if runtime else None
        runtime_matches = listener_pid is not None and runtime_pid == listener_pid

        if app_ready and (
            _should_restart(app_ready, runtime, source_stamp)
            or not runtime_matches
        ):
            if listener_pid is None:
                raise RuntimeError("无法识别旧服务进程。")
            _log("Restarting stale Streamlit service")
            _stop_project_service(listener_pid)
            app_ready = False

        if not app_ready:
            _log("Starting Streamlit service")
            python_exe = Path(sys.executable)
            if python_exe.name.lower() == "pythonw.exe":
                candidate = python_exe.with_name("python.exe")
                if candidate.exists():
                    python_exe = candidate
            log_file = LOG_PATH.open("a", encoding="utf-8")
            service = subprocess.Popen(
                [
                    str(python_exe),
                    "-m",
                    "streamlit",
                    "run",
                    "app.py",
                    "--server.address",
                    "127.0.0.1",
                    "--server.port",
                    "8501",
                    "--server.headless",
                    "true",
                ],
                cwd=PROJECT_DIR,
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=log_file,
                stderr=log_file,
            )
            _save_runtime(service.pid, source_stamp)

            for _ in range(180):
                if _app_is_ready():
                    break
                time.sleep(0.25)

        if not _app_is_ready():
            raise RuntimeError("The local service did not become ready.")

        chrome_candidates = [
            Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
        ]
        browser = next((path for path in chrome_candidates if path.exists()), None)
        if browser:
            subprocess.Popen([str(browser), f"--app={APP_URL}", "--start-maximized"], creationflags=subprocess.CREATE_NO_WINDOW)
            _log("Opened desktop app window")
        else:
            os.startfile(APP_URL)
            _log("Opened default browser")
    except Exception as exc:
        _log(f"Launch failed: {type(exc).__name__}: {exc}")
        _show_error(f"软件启动失败：{exc}")


if __name__ == "__main__":
    main()



