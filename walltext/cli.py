from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

from .config import (
    add_file_item,
    add_item,
    add_markdown_item,
    apply_from_config,
    bulk_add_items,
    clear_items,
    default_config_path,
    duplicate_item,
    export_items,
    get_item_details,
    import_items,
    init_config,
    item_preview,
    load_config,
    move_item,
    parse_time_string,
    remove_item,
    reset_state,
    set_inline_markdown,
    set_item_file,
    set_render_settings,
    set_schedule_daily,
    set_schedule_interval,
    set_selection_mode,
    status_snapshot,
    summarize_config,
    update_item,
)
from .core import (
    DEFAULT_BACKGROUND,
    DEFAULT_FONT_SIZE,
    DEFAULT_FOREGROUND,
    DEFAULT_PADDING,
    default_output_path,
    default_text_path,
    get_screen_size,
    render_text_image,
    set_wallpaper,
    watch_text_file,
)
from .markdown import apply_markdown_file, render_markdown_file, validate_markdown_file
from .manager import launch_manager
from .runtime import (
    disable_startup,
    enable_startup,
    listener_status,
    run_managed_listener,
    runtime_snapshot,
    start_listener_background,
    startup_status,
    stop_listener_background,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="walltext",
        description="Render centered text to a screen-sized PNG and optionally apply it as wallpaper.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    text_parser = subparsers.add_parser("text", help="Render text and set it as wallpaper.")
    text_parser.add_argument("message", nargs="+", help="Text to render.")
    _add_render_options(text_parser)

    file_parser = subparsers.add_parser("file", help="Read text from a file, render it, and set it as wallpaper.")
    file_parser.add_argument("input_path", help="Text file to read.")
    _add_render_options(file_parser)

    render_parser = subparsers.add_parser("render", help="Render text to a PNG without applying it.")
    render_parser.add_argument("output", help="PNG file to write.")
    render_parser.add_argument("message", nargs="+", help="Text to render.")
    _add_render_options(render_parser, include_output=False)

    apply_parser = subparsers.add_parser("apply", help="Apply an existing PNG as wallpaper.")
    apply_parser.add_argument("image_path", help="PNG file to set as wallpaper.")

    md_parser = subparsers.add_parser("md", help="Render or apply Markdown documents.")
    md_subparsers = md_parser.add_subparsers(dest="md_command", required=True)
    md_render = md_subparsers.add_parser("render", help="Render a Markdown file to PNG without applying it.")
    md_render.add_argument("input_path", help="Markdown file to render.")
    _add_render_options(md_render)
    md_apply = md_subparsers.add_parser("apply", help="Render a Markdown file and set it as wallpaper.")
    md_apply.add_argument("input_path", help="Markdown file to render.")
    _add_render_options(md_apply)
    md_validate = md_subparsers.add_parser("validate", help="Validate and summarize a Markdown file.")
    md_validate.add_argument("input_path", help="Markdown file to inspect.")

    watch_parser = subparsers.add_parser("watch", help="Watch a text file and reapply the wallpaper on changes.")
    watch_parser.add_argument(
        "input_path",
        nargs="?",
        default=str(default_text_path()),
        help="Text file to watch. Defaults to %%LOCALAPPDATA%%\\walltext\\walltext.txt.",
    )
    watch_parser.add_argument("--interval", type=float, default=1.0, help="Polling interval in seconds.")
    watch_parser.add_argument("--once", action="store_true", help="Apply the current text once and exit.")
    _add_render_options(watch_parser)

    run_parser = subparsers.add_parser("run", help="Apply the next JSON-configured item immediately.")
    run_parser.add_argument("--config", default=str(default_config_path()), help="Config JSON path.")
    run_parser.add_argument("--index", type=int, help="Specific zero-based item index to apply.")

    listen_parser = subparsers.add_parser("listen", help="Run the JSON-configured scheduler loop in the foreground.")
    listen_parser.add_argument("--config", default=str(default_config_path()), help="Config JSON path.")
    listen_parser.add_argument("--interval", type=float, default=30.0, help="Polling interval in seconds.")
    listen_parser.add_argument("--once", action="store_true", help="Check once and exit if nothing is due.")

    manager_parser = subparsers.add_parser("manager", help="Open the Walltext Manager GUI.")
    manager_parser.add_argument("--config", default=str(default_config_path()), help="Config JSON path.")

    listener_parser = subparsers.add_parser("listener", help="Manage the background listener process.")
    listener_subparsers = listener_parser.add_subparsers(dest="listener_command", required=True)
    listener_start = listener_subparsers.add_parser("start", help="Start the listener in the background.")
    listener_start.add_argument("--config", default=str(default_config_path()), help="Config JSON path.")
    listener_start.add_argument("--interval", type=float, default=30.0, help="Polling interval in seconds.")
    listener_subparsers.add_parser("stop", help="Stop the background listener.")
    listener_subparsers.add_parser("status", help="Print background listener status.")

    startup_parser = subparsers.add_parser("startup", help="Manage listener startup at login.")
    startup_subparsers = startup_parser.add_subparsers(dest="startup_command", required=True)
    startup_enable = startup_subparsers.add_parser("enable", help="Enable listener startup at login.")
    startup_enable.add_argument("--config", default=str(default_config_path()), help="Config JSON path.")
    startup_enable.add_argument("--interval", type=float, default=30.0, help="Polling interval in seconds.")
    startup_subparsers.add_parser("disable", help="Disable listener startup at login.")
    startup_subparsers.add_parser("status", help="Print startup status.")

    status_parser = subparsers.add_parser("status", help="Print config, listener, and startup status.")
    status_parser.add_argument("--config", default=str(default_config_path()), help="Config JSON path.")

    config_parser = subparsers.add_parser("config", help="Manage the JSON config.")
    config_parser.add_argument("--config", default=str(default_config_path()), help="Config JSON path.")
    config_subparsers = config_parser.add_subparsers(dest="config_command", required=True)

    init_parser = config_subparsers.add_parser("init", help="Create the default config.")
    init_parser.add_argument("--force", action="store_true", help="Overwrite an existing config.")

    config_subparsers.add_parser("show", help="Print the full config JSON.")
    config_subparsers.add_parser("summary", help="Print a short config summary.")
    config_subparsers.add_parser("list", help="Print the configured items.")

    add_parser = config_subparsers.add_parser("add", help="Add a new item.")
    add_parser.add_argument("message", nargs="+", help="Text to add.")

    add_md_parser = config_subparsers.add_parser("add-md", help="Add a new inline Markdown item.")
    add_md_parser.add_argument("message", nargs="+", help="Markdown to add.")

    add_file_parser = config_subparsers.add_parser("add-file", help="Add a file-backed text or Markdown item.")
    add_file_parser.add_argument("input_path", help="Path to a .txt or .md file.")
    add_file_parser.add_argument("--type", choices=("text", "markdown"), help="Explicit item type override.")

    update_parser = config_subparsers.add_parser("update", help="Replace an existing item.")
    update_parser.add_argument("index", type=int, help="Zero-based item index.")
    update_parser.add_argument("message", nargs="+", help="Replacement text.")

    update_md_parser = config_subparsers.add_parser("set-inline-md", help="Replace an item with inline Markdown.")
    update_md_parser.add_argument("index", type=int, help="Zero-based item index.")
    update_md_parser.add_argument("message", nargs="+", help="Replacement Markdown.")

    set_file_parser = config_subparsers.add_parser("set-file", help="Replace an item with a file-backed item.")
    set_file_parser.add_argument("index", type=int, help="Zero-based item index.")
    set_file_parser.add_argument("input_path", help="Path to a .txt or .md file.")
    set_file_parser.add_argument("--type", choices=("text", "markdown"), help="Explicit item type override.")

    show_item_parser = config_subparsers.add_parser("show-item", help="Print a resolved item.")
    show_item_parser.add_argument("index", type=int, help="Zero-based item index.")

    duplicate_parser = config_subparsers.add_parser("duplicate", help="Duplicate an existing item.")
    duplicate_parser.add_argument("index", type=int, help="Zero-based item index.")

    remove_parser = config_subparsers.add_parser("remove", help="Remove an item.")
    remove_parser.add_argument("index", type=int, help="Zero-based item index.")

    move_parser = config_subparsers.add_parser("move", help="Move an item up or down.")
    move_parser.add_argument("index", type=int, help="Zero-based item index.")
    move_parser.add_argument("direction", choices=("up", "down"))

    config_subparsers.add_parser("clear", help="Remove all items.")

    mode_parser = config_subparsers.add_parser("mode", help="Set selection mode.")
    mode_parser.add_argument("value", choices=("random", "sequence"))

    schedule_parser = config_subparsers.add_parser("schedule", help="Set schedule mode.")
    schedule_subparsers = schedule_parser.add_subparsers(dest="schedule_command", required=True)
    schedule_daily_parser = schedule_subparsers.add_parser("daily", help="Apply once per day.")
    schedule_daily_parser.add_argument("--time", default="00:00", help="Daily time in HH:MM format.")
    schedule_interval_parser = schedule_subparsers.add_parser("interval", help="Apply every X minutes.")
    schedule_interval_parser.add_argument("minutes", type=int, help="Minutes between updates.")

    render_parser_config = config_subparsers.add_parser("render", help="Set or show render settings.")
    render_subparsers = render_parser_config.add_subparsers(dest="render_command", required=True)
    render_subparsers.add_parser("show", help="Print render settings.")
    render_set = render_subparsers.add_parser("set", help="Update render settings.")
    render_set.add_argument("--output", help="PNG output path.")
    render_set.add_argument("--font", help="TTF font path.")
    render_set.add_argument("--clear-font", action="store_true", help="Clear the explicit font path.")
    render_set.add_argument("--size", type=int, help="Font size.")
    render_set.add_argument("--fg", help="Text color.")
    render_set.add_argument("--bg", help="Background color.")
    render_set.add_argument("--padding", type=int, help="Outer padding in pixels.")

    import_parser = config_subparsers.add_parser("import-items", help="Import items from JSON, TXT, or stdin (-).")
    import_parser.add_argument("input_path", help="Source file path or - for stdin.")
    import_parser.add_argument("--replace", action="store_true", help="Replace current items instead of appending.")
    import_parser.add_argument("--mode", choices=("lines", "blocks", "json"), help="Import mode for text or stdin.")

    export_parser = config_subparsers.add_parser("export-items", help="Export items to JSON or TXT.")
    export_parser.add_argument("output_path", help="Destination file path.")
    export_parser.add_argument("--format", choices=("json", "txt"), help="Export format.")

    bulk_add_parser = config_subparsers.add_parser("bulk-add", help="Add many items from text blocks or lines.")
    bulk_add_parser.add_argument("input_path", help="Source file path or - for stdin.")
    bulk_add_parser.add_argument("--replace", action="store_true", help="Replace current items instead of appending.")
    bulk_add_parser.add_argument("--mode", choices=("lines", "blocks"), default="blocks", help="How to split the text.")

    config_subparsers.add_parser("reset-state", help="Reset sequence and scheduler state.")

    subparsers.add_parser("info", help="Print screen resolution and current defaults.")
    subparsers.add_parser("help", help="Show this help message and banner.")

    return parser


def print_custom_help(parser: argparse.ArgumentParser) -> None:
    columns = shutil.get_terminal_size().columns
    left = "Walltext by Hivemind Studio"
    right = "https://hivemindstudio.art"
    if columns > len(left) + len(right):
        # We need to print left, right, and enough spaces in between, but if it hits exactly max columns, 
        # windows terminal might wrap. So let's pad based on max(columns - 1, len(left)+len(right))
        space_len = (columns - 1) - len(left) - len(right)
        print(f"{left}{' ' * space_len}{right}")
    else:
        print(f"{left} - {right}")
    print()
    parser.print_help()


def main() -> None:
    parser = build_parser()
    if len(sys.argv) == 1:
        print_custom_help(parser)
        return
    
    args = parser.parse_args()

    if args.command == "help":
        print_custom_help(parser)
        return

    if args.command == "info":
        width, height = get_screen_size()
        print(f"screen: {width}x{height}")
        print(f"default output: {default_output_path()}")
        print(f"default text file: {default_text_path()}")
        print(f"default config file: {default_config_path()}")
        print(f"default font size: {DEFAULT_FONT_SIZE}")
        print(f"default fg: {DEFAULT_FOREGROUND}")
        print(f"default bg: {DEFAULT_BACKGROUND}")
        return

    if args.command == "apply":
        print(set_wallpaper(args.image_path))
        return

    if args.command == "md":
        _handle_markdown_command(args)
        return

    if args.command == "watch":
        applied_path = watch_text_file(
            args.input_path,
            output_path=args.output,
            font_path=args.font,
            font_size=args.size,
            foreground=args.fg,
            background=args.bg,
            padding=args.padding,
            interval=args.interval,
            run_once=args.once,
        )
        if applied_path:
            print(applied_path)
        return

    if args.command == "run":
        result = apply_from_config(args.config, force=True, item_index=args.index)
        print(result["image_path"])
        return

    if args.command == "listen":
        result = run_managed_listener(args.config, poll_interval=args.interval, run_once=args.once)
        if result:
            print(result["image_path"])
        return

    if args.command == "listener":
        _handle_listener_command(args)
        return

    if args.command == "startup":
        _handle_startup_command(args)
        return

    if args.command == "status":
        _handle_status_command(args)
        return

    if args.command == "manager":
        launch_manager(args.config)
        return

    if args.command == "config":
        _handle_config_command(args)
        return

    if args.command == "file":
        text = Path(args.input_path).expanduser().read_text(encoding="utf-8-sig")
        output = args.output
        apply_wallpaper = True
    elif args.command == "render":
        text = " ".join(args.message)
        output = args.output
        apply_wallpaper = False
    else:
        text = " ".join(args.message)
        output = args.output
        apply_wallpaper = True

    image_path = render_text_image(
        text,
        output_path=output,
        font_path=args.font,
        font_size=args.size,
        foreground=args.fg,
        background=args.bg,
        padding=args.padding,
    )

    if apply_wallpaper:
        set_wallpaper(image_path)

    print(image_path)


def _add_render_options(parser: argparse.ArgumentParser, *, include_output: bool = True) -> None:
    if include_output:
        parser.add_argument(
            "--output",
            default=str(default_output_path()),
            help="PNG file to write. Defaults to %%LOCALAPPDATA%%\\walltext\\walltext.png.",
        )

    parser.add_argument("--font", help="TTF font path or font filename.")
    parser.add_argument("--size", type=int, default=DEFAULT_FONT_SIZE, help="Font size in points.")
    parser.add_argument("--fg", default=DEFAULT_FOREGROUND, help="Text color.")
    parser.add_argument("--bg", default=DEFAULT_BACKGROUND, help="Background color.")
    parser.add_argument("--padding", type=int, default=DEFAULT_PADDING, help="Outer padding in pixels.")


def _handle_listener_command(args: argparse.Namespace) -> None:
    if args.listener_command == "start":
        print(json.dumps(start_listener_background(args.config, poll_interval=args.interval), indent=2))
        return

    if args.listener_command == "stop":
        print(json.dumps(stop_listener_background(), indent=2))
        return

    print(json.dumps(listener_status(), indent=2))


def _handle_startup_command(args: argparse.Namespace) -> None:
    if args.startup_command == "enable":
        print(enable_startup(args.config, poll_interval=args.interval))
        return

    if args.startup_command == "disable":
        print(disable_startup())
        return

    print(json.dumps(startup_status(), indent=2, default=str))


def _handle_status_command(args: argparse.Namespace) -> None:
    snapshot = status_snapshot(args.config)
    runtime = runtime_snapshot(args.config)
    payload = {
        "config": snapshot,
        "listener": runtime["listener"],
        "startup": runtime["startup"],
    }
    print(json.dumps(payload, indent=2, default=str))


def _handle_config_command(args: argparse.Namespace) -> None:
    config_path = args.config

    if args.config_command == "init":
        print(init_config(config_path, force=args.force))
        return

    if args.config_command == "show":
        _, config = load_config(config_path)
        print(json.dumps(config, indent=2))
        return

    if args.config_command == "summary":
        print(summarize_config(config_path))
        return

    if args.config_command == "list":
        _, config = load_config(config_path)
        for index, item in enumerate(config["items"]):
            print(f"{index}: {item_preview(item)}")
        return

    if args.config_command == "add":
        print(add_item(config_path, " ".join(args.message)))
        return

    if args.config_command == "add-md":
        print(add_markdown_item(config_path, " ".join(args.message)))
        return

    if args.config_command == "add-file":
        print(add_file_item(config_path, args.input_path, item_type=args.type))
        return

    if args.config_command == "update":
        print(update_item(config_path, args.index, " ".join(args.message)))
        return

    if args.config_command == "set-inline-md":
        print(set_inline_markdown(config_path, args.index, " ".join(args.message)))
        return

    if args.config_command == "set-file":
        print(set_item_file(config_path, args.index, args.input_path, item_type=args.type))
        return

    if args.config_command == "show-item":
        print(json.dumps(get_item_details(config_path, args.index), indent=2))
        return

    if args.config_command == "duplicate":
        print(duplicate_item(config_path, args.index))
        return

    if args.config_command == "remove":
        print(remove_item(config_path, args.index))
        return

    if args.config_command == "move":
        print(move_item(config_path, args.index, args.direction))
        return

    if args.config_command == "clear":
        print(clear_items(config_path))
        return

    if args.config_command == "mode":
        print(set_selection_mode(config_path, args.value))
        return

    if args.config_command == "schedule":
        if args.schedule_command == "daily":
            hour, minute = parse_time_string(args.time)
            print(set_schedule_daily(config_path, hour=hour, minute=minute))
            return

        print(set_schedule_interval(config_path, args.minutes))
        return

    if args.config_command == "render":
        if args.render_command == "show":
            _, config = load_config(config_path)
            print(json.dumps(config["render"], indent=2))
            return

        kwargs: dict[str, object | None] = {}
        if args.output is not None:
            kwargs["output"] = args.output
        if args.clear_font:
            kwargs["font"] = None
        elif args.font is not None:
            kwargs["font"] = args.font
        if args.size is not None:
            kwargs["size"] = args.size
        if args.fg is not None:
            kwargs["foreground"] = args.fg
        if args.bg is not None:
            kwargs["background"] = args.bg
        if args.padding is not None:
            kwargs["padding"] = args.padding

        print(set_render_settings(config_path, **kwargs))
        return

    if args.config_command == "import-items":
        print(import_items(config_path, args.input_path, replace=args.replace, mode=args.mode))
        return

    if args.config_command == "export-items":
        print(export_items(config_path, args.output_path, format_name=args.format))
        return

    if args.config_command == "bulk-add":
        source = args.input_path
        if source == "-":
            text = sys.stdin.read()
        else:
            text = Path(source).expanduser().read_text(encoding="utf-8-sig")
        print(bulk_add_items(config_path, text, mode=args.mode, replace=args.replace))
        return

    if args.config_command == "reset-state":
        print(reset_state(config_path))


def _handle_markdown_command(args: argparse.Namespace) -> None:
    if args.md_command == "validate":
        print(json.dumps(validate_markdown_file(args.input_path), indent=2))
        return

    if args.md_command == "render":
        print(
            render_markdown_file(
                args.input_path,
                output_path=args.output,
                font_path=args.font,
                font_size=args.size,
                foreground=args.fg,
                background=args.bg,
                padding=args.padding,
            )
        )
        return

    print(
        apply_markdown_file(
            args.input_path,
            output_path=args.output,
            font_path=args.font,
            font_size=args.size,
            foreground=args.fg,
            background=args.bg,
            padding=args.padding,
        )
    )
