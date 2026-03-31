from __future__ import annotations

from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import random
import re
import sys
import time
from typing import Any

from .core import (
    DEFAULT_BACKGROUND,
    DEFAULT_FONT_SIZE,
    DEFAULT_FOREGROUND,
    DEFAULT_PADDING,
    default_output_path,
    normalize_output_path,
    render_text_image,
    set_wallpaper,
)
from .markdown import render_markdown_text


CONFIG_VERSION = 3
ITEM_TYPE_TEXT = "text"
ITEM_TYPE_MARKDOWN = "markdown"
ITEM_SOURCE_INLINE = "inline"
ITEM_SOURCE_FILE = "file"
SELECTION_MODES = {"random", "sequence"}
SCHEDULE_TYPES = {"daily", "interval"}


def default_config_path() -> Path:
    base_dir = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return base_dir / "walltext" / "walltext.json"


def create_default_config() -> dict[str, Any]:
    return {
        "version": CONFIG_VERSION,
        "items": [create_inline_item("walltext ready")],
        "selection_mode": "sequence",
        "schedule": {
            "type": "daily",
            "hour": 0,
            "minute": 0,
            "minutes": 60,
        },
        "render": {
            "output": str(default_output_path()),
            "font": None,
            "size": DEFAULT_FONT_SIZE,
            "fg": DEFAULT_FOREGROUND,
            "bg": DEFAULT_BACKGROUND,
            "padding": DEFAULT_PADDING,
            "align": "center",
            "valign": "middle",
        },
        "state": {
            "last_applied_at": None,
            "last_item_index": None,
            "last_item_text": None,
            "next_index": 0,
            "applied_count": 0,
        },
    }


def create_inline_item(value: str, *, item_type: str = ITEM_TYPE_TEXT) -> dict[str, str]:
    return {
        "type": _normalize_item_type(item_type),
        "source": ITEM_SOURCE_INLINE,
        "value": str(value).replace("\r\n", "\n"),
    }


def create_file_item(
    path: str | Path,
    *,
    item_type: str | None = None,
    config_dir: str | Path | None = None,
) -> dict[str, str]:
    path_value = str(path).strip()
    inferred_type = item_type or infer_item_type_from_path(path_value)
    return {
        "type": _normalize_item_type(inferred_type),
        "source": ITEM_SOURCE_FILE,
        "path": _normalize_stored_path(path_value, base_dir=config_dir),
    }


def infer_item_type_from_path(path: str | Path) -> str:
    suffix = Path(path).suffix.lower()
    return ITEM_TYPE_MARKDOWN if suffix == ".md" else ITEM_TYPE_TEXT


def normalize_item(item: Any, *, config_dir: str | Path | None = None) -> dict[str, str]:
    if isinstance(item, str):
        return create_inline_item(item)

    if not isinstance(item, dict):
        return create_inline_item("" if item is None else str(item))

    item_type = item.get("type")
    if not item_type and item.get("path"):
        item_type = infer_item_type_from_path(str(item["path"]))
    item_type = _normalize_item_type(item_type)

    source = str(item.get("source") or (ITEM_SOURCE_FILE if item.get("path") else ITEM_SOURCE_INLINE)).strip().lower()
    if source not in {ITEM_SOURCE_INLINE, ITEM_SOURCE_FILE}:
        source = ITEM_SOURCE_FILE if item.get("path") else ITEM_SOURCE_INLINE

    if source == ITEM_SOURCE_FILE:
        path_value = str(item.get("path") or "").strip()
        if not path_value:
            value = item.get("value", item.get("text", item.get("content", "")))
            return create_inline_item("" if value is None else str(value), item_type=item_type)
        return create_file_item(path_value, item_type=item_type, config_dir=config_dir)

    value = item.get("value", item.get("text", item.get("content", "")))
    return create_inline_item("" if value is None else str(value), item_type=item_type)


def resolve_item(item: Any, *, config_path: str | Path | None = None) -> dict[str, Any]:
    path = _normalize_config_path(config_path)
    normalized = normalize_item(item, config_dir=path.parent)

    if normalized["source"] == ITEM_SOURCE_INLINE:
        return {
            **normalized,
            "value": normalized.get("value", ""),
            "resolved_path": None,
        }

    stored_path = normalized["path"]
    resolved_path = _resolve_item_path(stored_path, base_dir=path.parent)
    value = resolved_path.read_text(encoding="utf-8-sig")
    return {
        **normalized,
        "path": stored_path,
        "resolved_path": resolved_path,
        "value": value.replace("\r\n", "\n"),
    }


def item_preview(item: Any, *, max_length: int = 72) -> str:
    normalized = normalize_item(item)
    if normalized["source"] == ITEM_SOURCE_FILE:
        label = Path(normalized["path"]).name or normalized["path"]
        prefix = "md file" if normalized["type"] == ITEM_TYPE_MARKDOWN else "file"
        return _truncate_preview(f"[{prefix}] {label}", max_length=max_length)

    raw_value = normalized.get("value", "").strip()
    if not raw_value:
        text = "(blank)"
    else:
        first_line = next((line.strip() for line in raw_value.splitlines() if line.strip()), "")
        text = first_line or "(blank)"
    prefix = "[md] " if normalized["type"] == ITEM_TYPE_MARKDOWN else ""
    return _truncate_preview(prefix + text, max_length=max_length)


def item_details(item: Any, *, config_path: str | Path | None = None) -> dict[str, Any]:
    normalized = normalize_item(item)
    details: dict[str, Any] = {
        "type": normalized["type"],
        "source": normalized["source"],
        "preview": item_preview(normalized, max_length=200),
    }
    if normalized["source"] == ITEM_SOURCE_INLINE:
        details["value"] = normalized["value"]
        return details

    resolved = resolve_item(normalized, config_path=config_path)
    details["path"] = normalized["path"]
    details["resolved_path"] = str(resolved["resolved_path"])
    details["value"] = resolved["value"]
    return details


def load_config(config_path: str | Path | None = None) -> tuple[Path, dict[str, Any]]:
    path = _normalize_config_path(config_path)
    if not path.exists():
        config = create_default_config()
        save_config(config, path)
        return path, config

    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid config JSON: {path}") from exc

    config = _normalize_config(raw, config_path=path)
    return path, config


def save_config(config: dict[str, Any], config_path: str | Path | None = None) -> Path:
    path = _normalize_config_path(config_path)
    normalized = _normalize_config(config, config_path=path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalized, indent=2) + "\n", encoding="utf-8")
    return path


def init_config(config_path: str | Path | None = None, *, force: bool = False) -> Path:
    path = _normalize_config_path(config_path)
    if path.exists() and not force:
        raise FileExistsError(f"Config already exists: {path}")
    return save_config(create_default_config(), path)


def add_item(config_path: str | Path | None, message: str) -> str:
    return _append_item(config_path, create_inline_item(message))


def add_markdown_item(config_path: str | Path | None, markdown_text: str) -> str:
    return _append_item(config_path, create_inline_item(markdown_text, item_type=ITEM_TYPE_MARKDOWN))


def add_file_item(config_path: str | Path | None, file_path: str | Path, *, item_type: str | None = None) -> str:
    path, config = load_config(config_path)
    config["items"].append(create_file_item(file_path, item_type=item_type, config_dir=path.parent))
    save_config(config, path)
    return f"Added item {len(config['items']) - 1}."


def update_item(config_path: str | Path | None, index: int, message: str) -> str:
    path, config = load_config(config_path)
    normalized_index = _validate_index(index, config["items"])
    config["items"][normalized_index] = create_inline_item(message)
    save_config(config, path)
    return f"Updated item {normalized_index}."


def set_inline_markdown(config_path: str | Path | None, index: int, markdown_text: str) -> str:
    path, config = load_config(config_path)
    normalized_index = _validate_index(index, config["items"])
    config["items"][normalized_index] = create_inline_item(markdown_text, item_type=ITEM_TYPE_MARKDOWN)
    save_config(config, path)
    return f"Updated item {normalized_index}."


def set_item_file(
    config_path: str | Path | None,
    index: int,
    file_path: str | Path,
    *,
    item_type: str | None = None,
) -> str:
    path, config = load_config(config_path)
    normalized_index = _validate_index(index, config["items"])
    config["items"][normalized_index] = create_file_item(file_path, item_type=item_type, config_dir=path.parent)
    save_config(config, path)
    return f"Updated item {normalized_index}."


def get_item_details(config_path: str | Path | None, index: int) -> dict[str, Any]:
    path, config = load_config(config_path)
    normalized_index = _validate_index(index, config["items"])
    return item_details(config["items"][normalized_index], config_path=path)


def duplicate_item(config_path: str | Path | None, index: int) -> str:
    path, config = load_config(config_path)
    normalized_index = _validate_index(index, config["items"])
    config["items"].insert(normalized_index + 1, dict(normalize_item(config["items"][normalized_index], config_dir=path.parent)))
    save_config(config, path)
    return f"Duplicated item {normalized_index}."


def remove_item(config_path: str | Path | None, index: int) -> str:
    path, config = load_config(config_path)
    normalized_index = _validate_index(index, config["items"])
    del config["items"][normalized_index]
    _clamp_sequence_state(config)
    save_config(config, path)
    return f"Removed item {normalized_index}."


def move_item(config_path: str | Path | None, index: int, direction: str) -> str:
    path, config = load_config(config_path)
    normalized_index = _validate_index(index, config["items"])
    if direction not in {"up", "down"}:
        raise ValueError("Direction must be 'up' or 'down'.")

    if direction == "up":
        target = max(normalized_index - 1, 0)
    else:
        target = min(normalized_index + 1, len(config["items"]) - 1)

    if target == normalized_index:
        return f"Item {normalized_index} unchanged."

    item = config["items"].pop(normalized_index)
    config["items"].insert(target, item)
    _clamp_sequence_state(config)
    save_config(config, path)
    return f"Moved item {normalized_index} {direction}."


def clear_items(config_path: str | Path | None) -> str:
    path, config = load_config(config_path)
    config["items"] = []
    reset_state_on_config(config)
    save_config(config, path)
    return "Cleared all items."


def set_selection_mode(config_path: str | Path | None, value: str) -> str:
    normalized_value = value.strip().lower()
    if normalized_value not in SELECTION_MODES:
        raise ValueError("Selection mode must be 'random' or 'sequence'.")

    path, config = load_config(config_path)
    config["selection_mode"] = normalized_value
    save_config(config, path)
    return f"Selection mode set to {normalized_value}."


def set_schedule_daily(config_path: str | Path | None, *, hour: int, minute: int) -> str:
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("Daily time must be within 00:00 and 23:59.")

    path, config = load_config(config_path)
    config["schedule"]["type"] = "daily"
    config["schedule"]["hour"] = int(hour)
    config["schedule"]["minute"] = int(minute)
    save_config(config, path)
    return f"Schedule set to daily at {format_time_string(hour, minute)}."


def set_schedule_interval(config_path: str | Path | None, minutes: int) -> str:
    normalized_minutes = max(int(minutes), 1)
    path, config = load_config(config_path)
    config["schedule"]["type"] = "interval"
    config["schedule"]["minutes"] = normalized_minutes
    save_config(config, path)
    return f"Schedule set to every {normalized_minutes} minute(s)."


def set_render_settings(
    config_path: str | Path | None,
    *,
    output: str | Path | None = None,
    font: str | None = None,
    size: int | None = None,
    foreground: str | None = None,
    background: str | None = None,
    padding: int | None = None,
    align: str | None = None,
    valign: str | None = None,
) -> str:
    path, config = load_config(config_path)

    if output is not None:
        config["render"]["output"] = str(normalize_output_path(output))
    if font is not None:
        config["render"]["font"] = str(font).strip() or None
    if size is not None:
        config["render"]["size"] = max(int(size), 1)
    if foreground is not None:
        config["render"]["fg"] = str(foreground).strip() or DEFAULT_FOREGROUND
    if background is not None:
        config["render"]["bg"] = str(background).strip() or DEFAULT_BACKGROUND
    if padding is not None:
        config["render"]["padding"] = max(int(padding), 0)
    if align is not None:
        config["render"]["align"] = _normalize_align(align)
    if valign is not None:
        config["render"]["valign"] = _normalize_valign(valign)

    save_config(config, path)
    return "Render settings updated."


def reset_state(config_path: str | Path | None) -> str:
    path, config = load_config(config_path)
    reset_state_on_config(config)
    save_config(config, path)
    return "State reset."


def reset_state_on_config(config: dict[str, Any]) -> None:
    config["state"]["last_applied_at"] = None
    config["state"]["last_item_index"] = None
    config["state"]["last_item_text"] = None
    config["state"]["next_index"] = 0
    config["state"]["applied_count"] = 0


def parse_time_string(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", value or "")
    if not match:
        raise ValueError("Time must be in HH:MM format.")
    hour = int(match.group(1))
    minute = int(match.group(2))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("Time must be in HH:MM format.")
    return hour, minute


def format_time_string(hour: int, minute: int) -> str:
    return f"{int(hour):02d}:{int(minute):02d}"


def parse_items_text(text: str, *, mode: str = "blocks") -> list[str]:
    normalized = text.replace("\r\n", "\n").strip()
    if not normalized:
        return []

    if mode == "lines":
        return [line.strip() for line in normalized.splitlines() if line.strip()]
    if mode != "blocks":
        raise ValueError("Mode must be 'lines' or 'blocks'.")

    blocks = re.split(r"\n\s*\n", normalized)
    return [block.strip() for block in blocks if block.strip()]


def bulk_add_items(
    config_path: str | Path | None,
    text: str,
    *,
    mode: str = "blocks",
    replace: bool = False,
) -> str:
    path, config = load_config(config_path)
    new_items = [create_inline_item(item) for item in parse_items_text(text, mode=mode)]
    if replace:
        config["items"] = new_items
        reset_state_on_config(config)
    else:
        config["items"].extend(new_items)
    save_config(config, path)
    return f"Imported {len(new_items)} item(s)."


def import_items(
    config_path: str | Path | None,
    input_path: str,
    *,
    replace: bool = False,
    mode: str | None = None,
) -> str:
    path, config = load_config(config_path)
    source_text, source_path = _read_import_source(input_path)
    normalized_mode = _normalize_import_mode(mode, source_path)

    if normalized_mode == "json":
        new_items = _parse_imported_json_items(source_text, source_path=source_path, config_dir=path.parent)
    else:
        new_items = [create_inline_item(item) for item in parse_items_text(source_text, mode=normalized_mode)]

    if replace:
        config["items"] = new_items
        reset_state_on_config(config)
    else:
        config["items"].extend(new_items)
    save_config(config, path)
    return f"Imported {len(new_items)} item(s)."


def export_items(
    config_path: str | Path | None,
    output_path: str | Path,
    *,
    format_name: str | None = None,
) -> Path:
    path, config = load_config(config_path)
    target = Path(output_path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    normalized_format = _normalize_export_format(format_name, target)
    if normalized_format == "json":
        target.write_text(json.dumps(config["items"], indent=2) + "\n", encoding="utf-8")
        return target

    contents = []
    for item in config["items"]:
        try:
            resolved = resolve_item(item, config_path=path)
            contents.append(resolved["value"].strip("\n"))
        except FileNotFoundError:
            contents.append(item_preview(item, max_length=200))
    payload = "\n\n".join(contents).strip()
    target.write_text(payload + ("\n" if payload else ""), encoding="utf-8")
    return target


def status_snapshot(config_path: str | Path | None = None) -> dict[str, Any]:
    path, config = load_config(config_path)
    next_due = next_due_datetime(config)
    return {
        "config_path": str(path),
        "version": config["version"],
        "item_count": len(config["items"]),
        "selection_mode": config["selection_mode"],
        "schedule": dict(config["schedule"]),
        "schedule_description": describe_schedule(config),
        "due": is_due(config),
        "next_due_at": next_due.isoformat(sep=" ", timespec="seconds") if next_due else None,
        "last_applied_at": config["state"]["last_applied_at"],
        "last_item_index": config["state"]["last_item_index"],
        "last_item_text": config["state"]["last_item_text"],
        "next_index": config["state"]["next_index"],
        "applied_count": config["state"]["applied_count"],
        "render": dict(config["render"]),
        "items": [item_preview(item) for item in config["items"]],
    }


def summarize_config(config_path: str | Path | None = None) -> str:
    snapshot = status_snapshot(config_path)
    return "\n".join(
        [
            f"config: {snapshot['config_path']}",
            f"items: {snapshot['item_count']}",
            f"mode: {snapshot['selection_mode']}",
            f"schedule: {snapshot['schedule_description']}",
            f"due now: {snapshot['due']}",
            f"next run: {snapshot['next_due_at']}",
            f"last item: {snapshot['last_item_index']}",
            f"output: {snapshot['render']['output']}",
        ]
    )


def next_due_datetime(config: dict[str, Any], now: datetime | None = None) -> datetime | None:
    if not config.get("items"):
        return None

    now = now or datetime.now()
    schedule = config["schedule"]
    last_applied = _parse_datetime(config["state"].get("last_applied_at"))

    if schedule["type"] == "interval":
        if last_applied is None:
            return now
        return last_applied + timedelta(minutes=max(int(schedule["minutes"]), 1))

    candidate = now.replace(
        hour=int(schedule["hour"]),
        minute=int(schedule["minute"]),
        second=0,
        microsecond=0,
    )

    if now < candidate:
        return candidate

    if last_applied and last_applied.date() == now.date() and last_applied >= candidate:
        return candidate + timedelta(days=1)

    return candidate


def is_due(config: dict[str, Any], now: datetime | None = None) -> bool:
    next_due = next_due_datetime(config, now=now)
    if next_due is None:
        return False
    return (now or datetime.now()) >= next_due


def describe_schedule(config: dict[str, Any]) -> str:
    schedule = config["schedule"]
    if schedule["type"] == "interval":
        return f"every {schedule['minutes']} minute(s)"
    return f"daily at {format_time_string(schedule['hour'], schedule['minute'])}"


def apply_from_config(
    config_path: str | Path | None = None,
    *,
    force: bool = False,
    item_index: int | None = None,
) -> dict[str, Any]:
    path, config = load_config(config_path)
    if not config["items"]:
        raise RuntimeError("No items configured.")
    if not force and item_index is None and not is_due(config):
        return {
            "applied": False,
            "config_path": str(path),
            "image_path": None,
            "item_index": None,
            "item_type": None,
        }

    selected_index = _select_item_index(config, item_index=item_index)
    item = config["items"][selected_index]
    resolved = resolve_item(item, config_path=path)
    render_settings = dict(config["render"])

    if resolved["type"] == ITEM_TYPE_MARKDOWN:
        image_path = render_markdown_text(
            resolved["value"],
            output_path=render_settings["output"],
            defaults=render_settings,
        )
    else:
        image_path = render_text_image(
            resolved["value"],
            output_path=render_settings["output"],
            font_path=render_settings["font"],
            font_size=render_settings["size"],
            foreground=render_settings["fg"],
            background=render_settings["bg"],
            padding=render_settings["padding"],
        )

    wallpaper_path = set_wallpaper(image_path)
    applied_at = datetime.now().isoformat(timespec="seconds")
    config["state"]["last_applied_at"] = applied_at
    config["state"]["last_item_index"] = selected_index
    config["state"]["last_item_text"] = item_preview(item, max_length=200)
    config["state"]["applied_count"] = int(config["state"].get("applied_count") or 0) + 1
    config["state"]["next_index"] = (selected_index + 1) % len(config["items"]) if config["items"] else 0
    save_config(config, path)

    return {
        "applied": True,
        "config_path": str(path),
        "image_path": str(wallpaper_path),
        "item_index": selected_index,
        "item_type": resolved["type"],
        "item_source": resolved["source"],
        "applied_at": applied_at,
    }


def run_config_listener(
    config_path: str | Path | None = None,
    *,
    poll_interval: float = 30.0,
    run_once: bool = False,
) -> dict[str, Any] | None:
    interval = max(float(poll_interval), 0.2)
    path = _normalize_config_path(config_path)

    if run_once:
        _, config = load_config(path)
        if not is_due(config):
            return None
        return apply_from_config(path, force=True)

    while True:
        try:
            _, config = load_config(path)
            if is_due(config):
                apply_from_config(path, force=True)
        except Exception as exc:  # pragma: no cover - long-running listener path
            print(f"walltext config listener skipped update: {exc}", file=sys.stderr)
        time.sleep(interval)


def _append_item(config_path: str | Path | None, item: dict[str, str]) -> str:
    path, config = load_config(config_path)
    config["items"].append(item)
    save_config(config, path)
    return f"Added item {len(config['items']) - 1}."


def _normalize_config(config: Any, *, config_path: Path) -> dict[str, Any]:
    defaults = create_default_config()
    normalized = create_default_config()

    if not isinstance(config, dict):
        return normalized

    normalized["version"] = CONFIG_VERSION
    normalized["items"] = [
        normalize_item(item, config_dir=config_path.parent)
        for item in config.get("items", defaults["items"])
    ]

    selection_mode = str(config.get("selection_mode", defaults["selection_mode"])).strip().lower()
    normalized["selection_mode"] = selection_mode if selection_mode in SELECTION_MODES else defaults["selection_mode"]

    raw_schedule = config.get("schedule", {})
    if not isinstance(raw_schedule, dict):
        raw_schedule = {}
    schedule_type = str(raw_schedule.get("type", defaults["schedule"]["type"])).strip().lower()
    normalized["schedule"] = {
        "type": schedule_type if schedule_type in SCHEDULE_TYPES else defaults["schedule"]["type"],
        "hour": _safe_int(raw_schedule.get("hour"), defaults["schedule"]["hour"], minimum=0, maximum=23),
        "minute": _safe_int(raw_schedule.get("minute"), defaults["schedule"]["minute"], minimum=0, maximum=59),
        "minutes": _safe_int(raw_schedule.get("minutes"), defaults["schedule"]["minutes"], minimum=1),
    }

    raw_render = config.get("render", {})
    if not isinstance(raw_render, dict):
        raw_render = {}
    render_output = raw_render.get("output", defaults["render"]["output"])
    normalized["render"] = {
        "output": str(normalize_output_path(render_output)),
        "font": _normalize_font_value(raw_render.get("font", defaults["render"]["font"])),
        "size": _safe_int(raw_render.get("size"), defaults["render"]["size"], minimum=1),
        "fg": str(raw_render.get("fg", defaults["render"]["fg"]) or DEFAULT_FOREGROUND),
        "bg": str(raw_render.get("bg", defaults["render"]["bg"]) or DEFAULT_BACKGROUND),
        "padding": _safe_int(raw_render.get("padding"), defaults["render"]["padding"], minimum=0),
        "align": _normalize_align(str(raw_render.get("align", defaults["render"]["align"]))),
        "valign": _normalize_valign(str(raw_render.get("valign", defaults["render"]["valign"]))),
    }

    raw_state = config.get("state", {})
    if not isinstance(raw_state, dict):
        raw_state = {}
    normalized["state"] = {
        "last_applied_at": _normalize_datetime_string(raw_state.get("last_applied_at")),
        "last_item_index": _normalize_optional_index(raw_state.get("last_item_index")),
        "last_item_text": _normalize_optional_text(raw_state.get("last_item_text")),
        "next_index": _safe_int(raw_state.get("next_index"), defaults["state"]["next_index"], minimum=0),
        "applied_count": _safe_int(raw_state.get("applied_count"), defaults["state"]["applied_count"], minimum=0),
    }

    _clamp_sequence_state(normalized)
    return normalized


def _read_import_source(input_path: str) -> tuple[str, Path | None]:
    if input_path == "-":
        return sys.stdin.read(), None
    path = Path(input_path).expanduser().resolve()
    return path.read_text(encoding="utf-8-sig"), path


def _normalize_import_mode(mode: str | None, source_path: Path | None) -> str:
    if mode is not None:
        normalized_mode = mode.strip().lower()
        if normalized_mode not in {"lines", "blocks", "json"}:
            raise ValueError("Import mode must be 'lines', 'blocks', or 'json'.")
        return normalized_mode

    if source_path and source_path.suffix.lower() == ".json":
        return "json"
    return "lines"


def _parse_imported_json_items(
    source_text: str,
    *,
    source_path: Path | None,
    config_dir: Path,
) -> list[dict[str, str]]:
    try:
        payload = json.loads(source_text)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid JSON import payload.") from exc

    if isinstance(payload, dict):
        raw_items = payload.get("items")
    else:
        raw_items = payload
    if not isinstance(raw_items, list):
        raise ValueError("JSON import must be a list of items or an object with an 'items' list.")

    source_dir = source_path.parent if source_path else config_dir
    imported_items: list[dict[str, str]] = []
    for raw_item in raw_items:
        normalized = normalize_item(raw_item)
        if normalized["source"] == ITEM_SOURCE_FILE:
            resolved = _resolve_item_path(normalized["path"], base_dir=source_dir)
            imported_items.append(create_file_item(resolved, item_type=normalized["type"], config_dir=config_dir))
        else:
            imported_items.append(normalized)
    return imported_items


def _normalize_export_format(format_name: str | None, output_path: Path) -> str:
    if format_name is not None:
        normalized = format_name.strip().lower()
        if normalized not in {"json", "txt"}:
            raise ValueError("Export format must be 'json' or 'txt'.")
        return normalized
    return "json" if output_path.suffix.lower() == ".json" else "txt"


def _select_item_index(config: dict[str, Any], *, item_index: int | None) -> int:
    items = config["items"]
    if item_index is not None:
        return _validate_index(item_index, items)

    if config["selection_mode"] == "random":
        choices = list(range(len(items)))
        last_index = config["state"].get("last_item_index")
        if len(choices) > 1 and isinstance(last_index, int) and last_index in choices:
            choices.remove(last_index)
        return random.choice(choices)

    next_index = int(config["state"].get("next_index") or 0)
    return next_index % len(items)


def _resolve_item_path(path_value: str | Path, *, base_dir: Path) -> Path:
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    else:
        path = path.resolve()
    return path


def _normalize_stored_path(path_value: str | Path, *, base_dir: str | Path | None = None) -> str:
    path = Path(path_value).expanduser()
    if base_dir is None:
        return str(path)
    base = Path(base_dir).expanduser().resolve()
    if not path.is_absolute():
        return str(path)

    try:
        return os.path.relpath(path.resolve(), base)
    except ValueError:
        return str(path.resolve())


def _normalize_config_path(config_path: str | Path | None) -> Path:
    path = Path(config_path).expanduser() if config_path else default_config_path()
    return path.resolve()


def _normalize_item_type(value: Any) -> str:
    lowered = str(value or ITEM_TYPE_TEXT).strip().lower()
    return lowered if lowered in {ITEM_TYPE_TEXT, ITEM_TYPE_MARKDOWN} else ITEM_TYPE_TEXT


def _normalize_align(value: str) -> str:
    lowered = value.strip().lower()
    return lowered if lowered in {"left", "center", "right"} else "center"


def _normalize_valign(value: str) -> str:
    lowered = value.strip().lower()
    return lowered if lowered in {"top", "middle", "bottom"} else "middle"


def _normalize_font_value(value: Any) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


def _normalize_datetime_string(value: Any) -> str | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)).isoformat(timespec="seconds")
    except ValueError:
        return None


def _normalize_optional_index(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _safe_int(value: Any, default: int, *, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        normalized = default
    if minimum is not None:
        normalized = max(normalized, minimum)
    if maximum is not None:
        normalized = min(normalized, maximum)
    return normalized


def _validate_index(index: int, items: list[Any]) -> int:
    normalized_index = int(index)
    if normalized_index < 0 or normalized_index >= len(items):
        raise IndexError(f"Item index out of range: {normalized_index}")
    return normalized_index


def _clamp_sequence_state(config: dict[str, Any]) -> None:
    item_count = len(config["items"])
    if item_count == 0:
        config["state"]["next_index"] = 0
        config["state"]["last_item_index"] = None
        return

    next_index = int(config["state"].get("next_index") or 0)
    config["state"]["next_index"] = next_index % item_count
    last_index = config["state"].get("last_item_index")
    if not isinstance(last_index, int) or last_index < 0 or last_index >= item_count:
        config["state"]["last_item_index"] = None


def _truncate_preview(value: str, *, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    if max_length <= 3:
        return value[:max_length]
    return value[: max_length - 3] + "..."
