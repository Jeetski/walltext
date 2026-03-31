from __future__ import annotations

import ctypes
import os
from pathlib import Path
import sys
import time
from typing import Iterable
import winreg

try:
    from PIL import Image, ImageDraw, ImageFont
except ModuleNotFoundError:  # pragma: no cover - handled at runtime
    Image = None
    ImageDraw = None
    ImageFont = None


SPI_SETDESKWALLPAPER = 20
SPIF_UPDATEINIFILE = 0x01
SPIF_SENDWININICHANGE = 0x02

DEFAULT_FONT_SIZE = 32
DEFAULT_FOREGROUND = "white"
DEFAULT_BACKGROUND = "black"
DEFAULT_PADDING = 80


def default_output_path() -> Path:
    base_dir = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return base_dir / "walltext" / "walltext.png"


def default_text_path() -> Path:
    return default_output_path().with_suffix(".txt")


def get_screen_size() -> tuple[int, int]:
    user32 = ctypes.windll.user32

    try:
        user32.SetProcessDPIAware()
    except AttributeError:
        pass

    width = int(user32.GetSystemMetrics(0))
    height = int(user32.GetSystemMetrics(1))
    return width, height


def render_text_image(
    text: str,
    output_path: str | Path | None = None,
    *,
    font_path: str | None = None,
    font_size: int = DEFAULT_FONT_SIZE,
    foreground: str = DEFAULT_FOREGROUND,
    background: str = DEFAULT_BACKGROUND,
    padding: int = DEFAULT_PADDING,
) -> Path:
    _require_pillow()

    width, height = get_screen_size()
    target_path = normalize_output_path(output_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    normalized_text = text.replace("\r\n", "\n").strip("\n")

    image = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(image)
    font = load_font(font_path=font_path, font_size=font_size)
    wrapped_text = _wrap_text(
        text=normalized_text,
        font=font,
        draw=draw,
        max_width=max(width - (padding * 2), 1),
    )

    spacing = max(int(font_size * 0.3), 6)
    if wrapped_text:
        bbox = draw.multiline_textbbox((0, 0), wrapped_text, font=font, align="center", spacing=spacing)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = ((width - text_width) / 2) - bbox[0]
        y = ((height - text_height) / 2) - bbox[1]

        draw.multiline_text(
            (x, y),
            wrapped_text,
            fill=foreground,
            font=font,
            align="center",
            spacing=spacing,
        )
    image.save(target_path, format="PNG")
    return target_path


def set_wallpaper(image_path: str | Path) -> Path:
    target = Path(image_path).expanduser().resolve()
    if not target.exists():
        raise FileNotFoundError(f"Image not found: {target}")

    _set_wallpaper_style()
    result = ctypes.windll.user32.SystemParametersInfoW(
        SPI_SETDESKWALLPAPER,
        0,
        str(target),
        SPIF_UPDATEINIFILE | SPIF_SENDWININICHANGE,
    )
    if not result:
        raise ctypes.WinError()

    return target


def watch_text_file(
    input_path: str | Path | None = None,
    *,
    output_path: str | Path | None = None,
    font_path: str | None = None,
    font_size: int = DEFAULT_FONT_SIZE,
    foreground: str = DEFAULT_FOREGROUND,
    background: str = DEFAULT_BACKGROUND,
    padding: int = DEFAULT_PADDING,
    interval: float = 1.0,
    run_once: bool = False,
) -> Path | None:
    source_path = Path(input_path).expanduser() if input_path else default_text_path()
    source_path.parent.mkdir(parents=True, exist_ok=True)

    if run_once:
        if not source_path.exists():
            raise FileNotFoundError(f"Text file not found: {source_path}")
        return _apply_text_file(
            input_path=source_path,
            output_path=output_path,
            font_path=font_path,
            font_size=font_size,
            foreground=foreground,
            background=background,
            padding=padding,
        )

    last_signature: tuple[int, int] | None = None
    while True:
        if not source_path.exists():
            time.sleep(interval)
            continue

        stat = source_path.stat()
        signature = (stat.st_mtime_ns, stat.st_size)
        if signature != last_signature:
            try:
                _apply_text_file(
                    input_path=source_path,
                    output_path=output_path,
                    font_path=font_path,
                    font_size=font_size,
                    foreground=foreground,
                    background=background,
                    padding=padding,
                )
                last_signature = signature
            except Exception as exc:  # pragma: no cover - long-running listener path
                print(f"walltext listener skipped update: {exc}", file=sys.stderr)

        time.sleep(interval)


def _require_pillow() -> None:
    if Image is None or ImageDraw is None or ImageFont is None:
        raise RuntimeError("Pillow is required. Install dependencies with `pip install -e .`.")


def normalize_output_path(output_path: str | Path | None) -> Path:
    target = Path(output_path).expanduser() if output_path else default_output_path()
    if target.suffix.lower() != ".png":
        target = target.with_suffix(".png")
    return target.resolve()


def load_font(*, font_path: str | None, font_size: int, bold: bool = False, italic: bool = False):
    if font_size < 1:
        raise ValueError("Font size must be at least 1.")

    if font_path:
        candidates = _font_path_candidates(font_path=font_path, bold=bold, italic=italic)
        for candidate in candidates:
            try:
                return ImageFont.truetype(candidate, font_size)
            except OSError:
                continue
        raise RuntimeError(f"Could not load font: {font_path}")

    for candidate in _font_candidates(bold=bold, italic=italic):
        if candidate.exists():
            return ImageFont.truetype(str(candidate), font_size)

    try:
        fallback_name = _default_font_name(bold=bold, italic=italic)
        return ImageFont.truetype(fallback_name, font_size)
    except OSError:
        return ImageFont.load_default()


def _font_candidates(*, bold: bool = False, italic: bool = False) -> Iterable[Path]:
    font_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    ordered_names = [_default_font_name(bold=bold, italic=italic)]
    ordered_names.extend(
        [
            "CascadiaMono.ttf",
            "cour.ttf",
            "lucon.ttf",
        ]
    )
    return tuple(font_dir / name for name in ordered_names)


def _wrap_text(*, text: str, font, draw, max_width: int) -> str:
    if not text:
        return ""

    wrapped_lines: list[str] = []
    for paragraph in text.splitlines():
        if not paragraph.strip():
            wrapped_lines.append("")
            continue

        current = ""
        for word in paragraph.split():
            candidate = word if not current else f"{current} {word}"
            if _text_width(draw, candidate, font) <= max_width:
                current = candidate
                continue

            if current:
                wrapped_lines.append(current)
                current = ""

            if _text_width(draw, word, font) <= max_width:
                current = word
                continue

            split_parts = _break_long_word(word=word, font=font, draw=draw, max_width=max_width)
            wrapped_lines.extend(split_parts[:-1])
            current = split_parts[-1]

        if current:
            wrapped_lines.append(current)

    return "\n".join(wrapped_lines)


def _break_long_word(*, word: str, font, draw, max_width: int) -> list[str]:
    parts: list[str] = []
    current = ""

    for character in word:
        candidate = f"{current}{character}"
        if current and _text_width(draw, candidate, font) > max_width:
            parts.append(current)
            current = character
        else:
            current = candidate

    if current:
        parts.append(current)

    return parts or [word]


def _text_width(draw, text: str, font) -> float:
    return float(draw.textlength(text, font=font))


def _apply_text_file(
    *,
    input_path: Path,
    output_path: str | Path | None,
    font_path: str | None,
    font_size: int,
    foreground: str,
    background: str,
    padding: int,
) -> Path:
    text = input_path.read_text(encoding="utf-8-sig")
    image_path = render_text_image(
        text,
        output_path=output_path,
        font_path=font_path,
        font_size=font_size,
        foreground=foreground,
        background=background,
        padding=padding,
    )
    return set_wallpaper(image_path)


def _set_wallpaper_style() -> None:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Control Panel\Desktop",
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, "10")
            winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, "0")
    except OSError:
        pass


def _default_font_name(*, bold: bool, italic: bool) -> str:
    if bold and italic:
        return "consolaz.ttf"
    if bold:
        return "consolab.ttf"
    if italic:
        return "consolai.ttf"
    return "consola.ttf"


def _font_path_candidates(*, font_path: str, bold: bool, italic: bool) -> tuple[str, ...]:
    explicit = Path(font_path).expanduser()
    stem = explicit.stem.lower()
    suffix = explicit.suffix or ".ttf"
    parent = explicit.parent if explicit.parent != Path("") else None

    variant_names: list[str] = []
    if stem in {"consola", "consolab", "consolai", "consolaz"}:
        variant_names.append(_default_font_name(bold=bold, italic=italic))
        variant_names.append("consola.ttf")
    else:
        variant_names.append(explicit.name)

    candidates: list[str] = []
    for name in variant_names:
        if parent:
            candidates.append(str(parent / name))
        candidates.append(name)

    candidates.append(str(explicit))
    return tuple(dict.fromkeys(candidates))
