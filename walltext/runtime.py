from __future__ import annotations

import ctypes
from ctypes import wintypes
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from .config import default_config_path, run_config_listener


PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_TERMINATE = 0x0001
STILL_ACTIVE = 259


def runtime_dir() -> Path:
    return default_config_path().parent


def listener_state_path() -> Path:
    return runtime_dir() / "listener-state.json"


def startup_launcher_path() -> Path:
    startup_dir = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    startup_dir = startup_dir / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    return startup_dir / "walltext_listener.cmd"


def listener_status() -> dict[str, Any]:
    state = _read_json(listener_state_path())
    if not state:
        return {
            "running": False,
            "pid": None,
            "config_path": None,
            "poll_interval": None,
            "started_at": None,
        }

    pid = state.get("pid")
    if not isinstance(pid, int) or not _is_process_running(pid):
        _clear_listener_state()
        return {
            "running": False,
            "pid": None,
            "config_path": state.get("config_path"),
            "poll_interval": state.get("poll_interval"),
            "started_at": state.get("started_at"),
        }

    return {
        "running": True,
        "pid": pid,
        "config_path": state.get("config_path"),
        "poll_interval": state.get("poll_interval"),
        "started_at": state.get("started_at"),
    }


def startup_status() -> dict[str, Any]:
    path = startup_launcher_path()
    return {
        "enabled": path.exists(),
        "path": path,
    }


def register_listener_process(config_path: str | Path | None, poll_interval: float) -> None:
    status = listener_status()
    current_pid = os.getpid()
    if status["running"] and status["pid"] != current_pid:
        raise RuntimeError(f"Listener already running with pid {status['pid']}.")

    payload = {
        "pid": current_pid,
        "config_path": str(Path(config_path).expanduser().resolve()) if config_path else str(default_config_path()),
        "poll_interval": float(poll_interval),
        "started_at": datetime.now().isoformat(timespec="seconds"),
    }
    _write_json(listener_state_path(), payload)


def unregister_listener_process() -> None:
    state = _read_json(listener_state_path())
    if not state or state.get("pid") == os.getpid():
        _clear_listener_state()


def run_managed_listener(
    config_path: str | Path | None = None,
    *,
    poll_interval: float,
    run_once: bool,
) -> dict[str, Any] | None:
    if run_once:
        return run_config_listener(config_path, poll_interval=poll_interval, run_once=True)

    register_listener_process(config_path, poll_interval)
    try:
        return run_config_listener(config_path, poll_interval=poll_interval, run_once=False)
    finally:
        unregister_listener_process()


def start_listener_background(config_path: str | Path | None = None, *, poll_interval: float = 30.0) -> dict[str, Any]:
    status = listener_status()
    if status["running"]:
        return {**status, "started": False}

    config_value = Path(config_path).expanduser().resolve() if config_path else default_config_path()
    command = [
        sys.executable,
        "-m",
        "walltext",
        "listen",
        "--config",
        str(config_value),
        "--interval",
        str(float(poll_interval)),
    ]

    creationflags = 0
    creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    creationflags |= getattr(subprocess, "DETACHED_PROCESS", 0)
    creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)

    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
        close_fds=True,
    )

    payload = {
        "pid": process.pid,
        "config_path": str(config_value),
        "poll_interval": float(poll_interval),
        "started_at": datetime.now().isoformat(timespec="seconds"),
    }
    _write_json(listener_state_path(), payload)

    return {
        "running": True,
        "pid": process.pid,
        "config_path": str(config_value),
        "poll_interval": float(poll_interval),
        "started_at": payload["started_at"],
        "started": True,
    }


def stop_listener_background() -> dict[str, Any]:
    status = listener_status()
    if not status["running"]:
        return {**status, "stopped": False}

    _terminate_process(int(status["pid"]))
    _clear_listener_state()
    return {**status, "stopped": True}


def enable_startup(config_path: str | Path | None = None, *, poll_interval: float = 30.0) -> Path:
    path = startup_launcher_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    config_value = Path(config_path).expanduser().resolve() if config_path else default_config_path()
    python_value = _ps_quote(sys.executable)
    config_ps = _ps_quote(str(config_value))
    content = (
        "@echo off\r\n"
        "powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden "
        f"-Command \"& {python_value} -m walltext listen --config {config_ps} --interval {float(poll_interval)}\"\r\n"
    )
    path.write_text(content, encoding="ascii")
    return path


def disable_startup() -> Path:
    path = startup_launcher_path()
    if path.exists():
        path.unlink()
    return path


def runtime_snapshot(config_path: str | Path | None = None) -> dict[str, Any]:
    listener = listener_status()
    startup = startup_status()
    return {
        "listener": listener,
        "startup": startup,
        "config_path": str(Path(config_path).expanduser().resolve()) if config_path else str(default_config_path()),
    }


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _clear_listener_state() -> None:
    path = listener_state_path()
    if path.exists():
        path.unlink()


def _is_process_running(pid: int) -> bool:
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False

    try:
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return False
        return int(exit_code.value) == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def _terminate_process(pid: int) -> None:
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(PROCESS_TERMINATE | PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        raise RuntimeError(f"Could not open process {pid}.")

    try:
        if not kernel32.TerminateProcess(handle, 1):
            raise ctypes.WinError()
    finally:
        kernel32.CloseHandle(handle)


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
