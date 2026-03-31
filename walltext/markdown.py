from __future__ import annotations

from dataclasses import dataclass, field
import re
from pathlib import Path
from typing import Any

from .core import (
    DEFAULT_BACKGROUND,
    DEFAULT_FONT_SIZE,
    DEFAULT_FOREGROUND,
    DEFAULT_PADDING,
    Image,
    ImageDraw,
    _require_pillow,
    default_output_path,
    get_screen_size,
    load_font,
    normalize_output_path,
    set_wallpaper,
)


DEFAULT_ALIGN = "center"
DEFAULT_VALIGN = "middle"
HEADING_SCALES = {1: 1.85, 2: 1.55, 3: 1.3}
INLINE_MARKER_PATTERN = re.compile(r"(\*\*|\*|`|\[color=[^\]]+\]|\[/color\])")
DEFAULT_LINE_SPACING = 1.0
THEME_PRESETS: dict[str, dict[str, Any]] = {
    "terminal": {
        "background": "#000000",
        "foreground": "#ffffff",
        "accent": "#6dff8d",
        "heading_fg": "#6dff8d",
        "quote_fg": "#b8f5c8",
        "code_fg": "#ffd166",
        "rule_fg": "#6dff8d",
        "bullet_fg": "#6dff8d",
        "line_spacing": 1.0,
    },
    "poster": {
        "background": "#090909",
        "foreground": "#f6f1e8",
        "accent": "#ff7a45",
        "heading_fg": "#ff7a45",
        "quote_fg": "#ffd8c8",
        "code_fg": "#ffe082",
        "rule_fg": "#ff7a45",
        "bullet_fg": "#ff7a45",
        "line_spacing": 1.08,
    },
    "note": {
        "background": "#0f1115",
        "foreground": "#e6edf3",
        "accent": "#7dd3fc",
        "heading_fg": "#7dd3fc",
        "quote_fg": "#c4d4e2",
        "code_fg": "#f9e2af",
        "rule_fg": "#7dd3fc",
        "bullet_fg": "#7dd3fc",
        "line_spacing": 1.04,
    },
}


@dataclass
class MarkdownRun:
    text: str
    bold: bool = False
    italic: bool = False
    code: bool = False
    color: str | None = None


@dataclass
class MarkdownBlock:
    kind: str
    runs: list[MarkdownRun] = field(default_factory=list)
    level: int = 0
    items: list[list[MarkdownRun]] = field(default_factory=list)


@dataclass
class MarkdownDocument:
    frontmatter: dict[str, Any]
    blocks: list[MarkdownBlock]


@dataclass
class LayoutSegment:
    text: str
    font: Any
    width: float
    fill: str


@dataclass
class LayoutLine:
    kind: str
    segments: list[LayoutSegment]
    width: float
    height: float
    spacing_after: float
    indent: float = 0.0
    fill: str | None = None


def parse_markdown_document(markdown_text: str) -> MarkdownDocument:
    frontmatter, body = _split_frontmatter(markdown_text)
    blocks = _parse_blocks(body)
    return MarkdownDocument(frontmatter=frontmatter, blocks=blocks)


def validate_markdown_text(markdown_text: str) -> dict[str, Any]:
    document = parse_markdown_document(markdown_text)
    return {
        "frontmatter": document.frontmatter,
        "block_count": len(document.blocks),
        "block_types": [block.kind for block in document.blocks],
    }


def validate_markdown_file(input_path: str | Path) -> dict[str, Any]:
    path = Path(input_path).expanduser().resolve()
    return {
        "path": str(path),
        **validate_markdown_text(path.read_text(encoding="utf-8-sig")),
    }


def render_markdown_text(
    markdown_text: str,
    output_path: str | Path | None = None,
    *,
    defaults: dict[str, Any] | None = None,
    font_path: str | None = None,
    font_size: int | None = None,
    foreground: str | None = None,
    background: str | None = None,
    padding: int | None = None,
    align: str | None = None,
    valign: str | None = None,
) -> Path:
    _require_pillow()
    document = parse_markdown_document(markdown_text)

    settings = _resolve_render_settings(
        frontmatter=document.frontmatter,
        defaults=defaults,
        font_path=font_path,
        font_size=font_size,
        foreground=foreground,
        background=background,
        padding=padding,
        align=align,
        valign=valign,
    )
    width, height = get_screen_size()
    target_path = normalize_output_path(output_path or settings["output"])
    target_path.parent.mkdir(parents=True, exist_ok=True)

    image = Image.new("RGB", (width, height), settings["background"])
    draw = ImageDraw.Draw(image)
    max_width = max(width - (settings["padding"] * 2), 1)
    lines = _layout_document(
        document,
        draw=draw,
        max_width=max_width,
        font_path=settings["font_path"],
        base_size=settings["font_size"],
        settings=settings,
    )

    total_height = sum(line.height + line.spacing_after for line in lines)
    if settings["valign"] == "top":
        y = float(settings["padding"])
    elif settings["valign"] == "bottom":
        y = max(float(height - settings["padding"]) - total_height, float(settings["padding"]))
    else:
        y = max((height - total_height) / 2.0, float(settings["padding"]))

    for line in lines:
        if line.kind == "rule":
            line_y = y + (line.height / 2.0)
            start_x = _aligned_x(width=width, padding=settings["padding"], content_width=line.width, align=settings["align"])
            draw.line(
                (start_x, line_y, start_x + line.width, line_y),
                fill=line.fill or settings["rule_fg"],
                width=max(int(settings["font_size"] * 0.08), 1),
            )
            y += line.height + line.spacing_after
            continue

        x = _aligned_x(width=width, padding=settings["padding"], content_width=line.width + line.indent, align=settings["align"])
        x += line.indent
        for segment in line.segments:
            draw.text((x, y), segment.text, fill=segment.fill, font=segment.font)
            x += segment.width
        y += line.height + line.spacing_after

    image.save(target_path, format="PNG")
    return target_path


def render_markdown_file(
    input_path: str | Path,
    output_path: str | Path | None = None,
    *,
    defaults: dict[str, Any] | None = None,
    font_path: str | None = None,
    font_size: int | None = None,
    foreground: str | None = None,
    background: str | None = None,
    padding: int | None = None,
    align: str | None = None,
    valign: str | None = None,
) -> Path:
    path = Path(input_path).expanduser().resolve()
    return render_markdown_text(
        path.read_text(encoding="utf-8-sig"),
        output_path=output_path,
        defaults=defaults,
        font_path=font_path,
        font_size=font_size,
        foreground=foreground,
        background=background,
        padding=padding,
        align=align,
        valign=valign,
    )


def apply_markdown_file(
    input_path: str | Path,
    output_path: str | Path | None = None,
    *,
    defaults: dict[str, Any] | None = None,
    font_path: str | None = None,
    font_size: int | None = None,
    foreground: str | None = None,
    background: str | None = None,
    padding: int | None = None,
    align: str | None = None,
    valign: str | None = None,
) -> Path:
    image_path = render_markdown_file(
        input_path,
        output_path=output_path,
        defaults=defaults,
        font_path=font_path,
        font_size=font_size,
        foreground=foreground,
        background=background,
        padding=padding,
        align=align,
        valign=valign,
    )
    return set_wallpaper(image_path)


def render_markdown_source(
    markdown_text: str,
    *,
    defaults: dict[str, Any] | None = None,
) -> Path:
    return render_markdown_text(markdown_text, defaults=defaults)


def _split_frontmatter(markdown_text: str) -> tuple[dict[str, Any], str]:
    normalized = markdown_text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return {}, normalized

    lines = normalized.split("\n")
    closing_index = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            closing_index = index
            break

    if closing_index is None:
        return {}, normalized

    frontmatter: dict[str, Any] = {}
    for line in lines[1:closing_index]:
        if not line.strip() or ":" not in line:
            continue
        key, value = line.split(":", 1)
        frontmatter[key.strip().lower()] = _parse_frontmatter_value(value.strip())

    body = "\n".join(lines[closing_index + 1 :])
    return frontmatter, body


def _parse_frontmatter_value(value: str) -> Any:
    stripped = value.strip()
    if (stripped.startswith('"') and stripped.endswith('"')) or (stripped.startswith("'") and stripped.endswith("'")):
        stripped = stripped[1:-1]

    if re.fullmatch(r"-?\d+", stripped):
        return int(stripped)
    if re.fullmatch(r"-?\d+\.\d+", stripped):
        return float(stripped)
    return stripped


def _parse_blocks(body: str) -> list[MarkdownBlock]:
    lines = body.splitlines()
    blocks: list[MarkdownBlock] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            index += 1
            continue

        heading_match = re.match(r"^(#{1,3})\s+(.*)$", stripped)
        if heading_match:
            blocks.append(
                MarkdownBlock(
                    kind="heading",
                    level=len(heading_match.group(1)),
                    runs=_parse_inline(heading_match.group(2).strip()),
                )
            )
            index += 1
            continue

        if re.fullmatch(r"[-*_]{3,}", stripped):
            blocks.append(MarkdownBlock(kind="rule"))
            index += 1
            continue

        if stripped.startswith(">"):
            quote_lines: list[str] = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                quote_lines.append(re.sub(r"^\s*>\s?", "", lines[index]).rstrip())
                index += 1
            blocks.append(MarkdownBlock(kind="blockquote", runs=_parse_inline(" ".join(quote_lines).strip())))
            continue

        if re.match(r"^\s*[-*]\s+", line):
            items: list[list[MarkdownRun]] = []
            while index < len(lines) and re.match(r"^\s*[-*]\s+", lines[index]):
                item_text = re.sub(r"^\s*[-*]\s+", "", lines[index]).rstrip()
                items.append(_parse_inline(item_text))
                index += 1
            blocks.append(MarkdownBlock(kind="list", items=items))
            continue

        paragraph_lines = [stripped]
        index += 1
        while index < len(lines):
            next_line = lines[index]
            next_stripped = next_line.strip()
            if not next_stripped:
                break
            if re.match(r"^(#{1,3})\s+", next_stripped) or re.fullmatch(r"[-*_]{3,}", next_stripped):
                break
            if next_stripped.startswith(">") or re.match(r"^\s*[-*]\s+", next_line):
                break
            paragraph_lines.append(next_stripped)
            index += 1

        blocks.append(MarkdownBlock(kind="paragraph", runs=_parse_inline(" ".join(paragraph_lines).strip())))

    return blocks


def _parse_inline(text: str, *, bold: bool = False, italic: bool = False) -> list[MarkdownRun]:
    runs: list[MarkdownRun] = []
    index = 0

    while index < len(text):
        if text.startswith("**", index):
            closing = text.find("**", index + 2)
            if closing != -1:
                runs.extend(_parse_inline(text[index + 2 : closing], bold=True, italic=italic))
                index = closing + 2
                continue

        if text.startswith("`", index):
            closing = text.find("`", index + 1)
            if closing != -1:
                runs.append(MarkdownRun(text=text[index + 1 : closing], bold=bold, italic=italic, code=True))
                index = closing + 1
                continue

        if text.startswith("*", index):
            closing = text.find("*", index + 1)
            if closing != -1:
                runs.extend(_parse_inline(text[index + 1 : closing], bold=bold, italic=True))
                index = closing + 1
                continue

        if text.startswith("[color=", index):
            match = re.match(r"^\[color=([^\]]+)\]", text[index:])
            if match:
                color_val = match.group(1)
                closing = text.find("[/color]", index + match.end())
                if closing != -1:
                    inner_runs = _parse_inline(text[index + match.end() : closing], bold=bold, italic=italic)
                    for run in inner_runs:
                        if run.color is None:
                            run.color = color_val
                    runs.extend(inner_runs)
                    index = closing + len("[/color]")
                    continue

        next_marker = INLINE_MARKER_PATTERN.search(text, index)
        
        if next_marker and next_marker.start() == index:
            marker_text = next_marker.group(0)
            runs.append(MarkdownRun(text=marker_text, bold=bold, italic=italic))
            index += len(marker_text)
            continue

        end = next_marker.start() if next_marker else len(text)
        plain = text[index:end]
        if plain:
            runs.append(MarkdownRun(text=plain, bold=bold, italic=italic))
        index = end

    return _merge_runs(runs)


def _merge_runs(runs: list[MarkdownRun]) -> list[MarkdownRun]:
    merged: list[MarkdownRun] = []
    for run in runs:
        if not run.text:
            continue
        if merged and (merged[-1].bold, merged[-1].italic, merged[-1].code, merged[-1].color) == (
            run.bold,
            run.italic,
            run.code,
            run.color,
        ):
            merged[-1].text += run.text
        else:
            merged.append(run)
    return merged


def _resolve_render_settings(
    *,
    frontmatter: dict[str, Any],
    defaults: dict[str, Any] | None,
    font_path: str | None,
    font_size: int | None,
    foreground: str | None,
    background: str | None,
    padding: int | None,
    align: str | None,
    valign: str | None,
) -> dict[str, Any]:
    settings = {
        "output": str(default_output_path()),
        "font_path": None,
        "font_size": DEFAULT_FONT_SIZE,
        "theme": None,
        "foreground": DEFAULT_FOREGROUND,
        "background": DEFAULT_BACKGROUND,
        "accent": DEFAULT_FOREGROUND,
        "heading_fg": DEFAULT_FOREGROUND,
        "quote_fg": DEFAULT_FOREGROUND,
        "code_fg": DEFAULT_FOREGROUND,
        "rule_fg": DEFAULT_FOREGROUND,
        "bullet_fg": DEFAULT_FOREGROUND,
        "line_spacing": DEFAULT_LINE_SPACING,
        "padding": DEFAULT_PADDING,
        "align": DEFAULT_ALIGN,
        "valign": DEFAULT_VALIGN,
    }

    if defaults:
        default_theme = _normalize_theme_name(defaults.get("theme"))
        if default_theme:
            _apply_theme_settings(settings, default_theme)
        _apply_render_overrides(settings, defaults)

    frontmatter_theme = _normalize_theme_name(frontmatter.get("theme"))
    if frontmatter_theme:
        _apply_theme_settings(settings, frontmatter_theme)
    _apply_render_overrides(settings, frontmatter)

    if font_path is not None:
        settings["font_path"] = font_path
    if font_size is not None:
        settings["font_size"] = max(int(font_size), 1)
    if foreground is not None:
        settings["foreground"] = foreground
    if background is not None:
        settings["background"] = background
    if padding is not None:
        settings["padding"] = max(int(padding), 0)
    if align is not None:
        settings["align"] = _normalize_align(align)
    if valign is not None:
        settings["valign"] = _normalize_valign(valign)

    _sync_color_defaults(settings)

    return settings


def _apply_theme_settings(settings: dict[str, Any], theme_name: str) -> None:
    preset = THEME_PRESETS.get(theme_name)
    if not preset:
        return
    settings["theme"] = theme_name
    settings["background"] = preset["background"]
    settings["foreground"] = preset["foreground"]
    settings["accent"] = preset["accent"]
    settings["heading_fg"] = preset["heading_fg"]
    settings["quote_fg"] = preset["quote_fg"]
    settings["code_fg"] = preset["code_fg"]
    settings["rule_fg"] = preset["rule_fg"]
    settings["bullet_fg"] = preset["bullet_fg"]
    settings["line_spacing"] = float(preset["line_spacing"])


def _apply_render_overrides(settings: dict[str, Any], source: dict[str, Any]) -> None:
    if "output" in source:
        settings["output"] = str(source["output"])
    if "font" in source:
        settings["font_path"] = source["font"] or None
    elif "font_path" in source:
        settings["font_path"] = source["font_path"] or None
    if "size" in source:
        settings["font_size"] = max(int(source["size"]), 1)
    elif "font_size" in source:
        settings["font_size"] = max(int(source["font_size"]), 1)
    if "fg" in source:
        settings["foreground"] = str(source["fg"])
    elif "foreground" in source:
        settings["foreground"] = str(source["foreground"])
    if "bg" in source:
        settings["background"] = str(source["bg"])
    elif "background" in source:
        settings["background"] = str(source["background"])
    if "accent" in source:
        settings["accent"] = str(source["accent"])
    if "heading_fg" in source:
        settings["heading_fg"] = str(source["heading_fg"])
    if "quote_fg" in source:
        settings["quote_fg"] = str(source["quote_fg"])
    if "code_fg" in source:
        settings["code_fg"] = str(source["code_fg"])
    if "rule_fg" in source:
        settings["rule_fg"] = str(source["rule_fg"])
    if "bullet_fg" in source:
        settings["bullet_fg"] = str(source["bullet_fg"])
    if "line_spacing" in source:
        settings["line_spacing"] = max(_safe_float(source["line_spacing"], DEFAULT_LINE_SPACING), 0.7)
    if "padding" in source:
        settings["padding"] = max(int(source["padding"]), 0)
    if "align" in source:
        settings["align"] = _normalize_align(str(source["align"]))
    if "valign" in source:
        settings["valign"] = _normalize_valign(str(source["valign"]))


def _sync_color_defaults(settings: dict[str, Any]) -> None:
    settings["accent"] = str(settings.get("accent") or settings["foreground"])
    settings["heading_fg"] = str(settings.get("heading_fg") or settings["accent"])
    settings["quote_fg"] = str(settings.get("quote_fg") or settings["foreground"])
    settings["code_fg"] = str(settings.get("code_fg") or settings["accent"])
    settings["rule_fg"] = str(settings.get("rule_fg") or settings["accent"])
    settings["bullet_fg"] = str(settings.get("bullet_fg") or settings["accent"])


def _normalize_theme_name(value: Any) -> str | None:
    if value is None:
        return None
    lowered = str(value).strip().lower()
    return lowered if lowered in THEME_PRESETS else None


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _layout_document(
    document: MarkdownDocument,
    *,
    draw,
    max_width: int,
    font_path: str | None,
    base_size: int,
    settings: dict[str, Any],
) -> list[LayoutLine]:
    font_cache: dict[tuple[int, bool, bool], Any] = {}
    line_spacing = max(float(settings["line_spacing"]), 0.7)

    def font_for(*, size: int, bold: bool = False, italic: bool = False, code: bool = False):
        key = (size, bold or code, italic and not code)
        if key not in font_cache:
            font_cache[key] = load_font(font_path=font_path, font_size=size, bold=bold or code, italic=italic and not code)
        return font_cache[key]

    lines: list[LayoutLine] = []
    for block in document.blocks:
        if block.kind == "rule":
            lines.append(
                LayoutLine(
                    kind="rule",
                    segments=[],
                    width=max_width * 0.42,
                    height=max(base_size * 0.85, 12),
                    spacing_after=base_size * 0.9 * line_spacing,
                    fill=settings["rule_fg"],
                )
            )
            continue

        block_runs_list: list[tuple[list[MarkdownRun], float, float, int, str, bool]] = []
        if block.kind == "heading":
            block_runs_list.append(
                (
                    block.runs,
                    HEADING_SCALES.get(block.level, 1.0),
                    base_size * 0.7 * line_spacing,
                    0,
                    settings["heading_fg"],
                    True,
                )
            )
        elif block.kind == "blockquote":
            quote_runs = [MarkdownRun(text="> ", italic=True, color=settings["accent"])] + [
                MarkdownRun(text=run.text, bold=run.bold, italic=True, code=run.code, color=run.color)
                for run in block.runs
            ]
            block_runs_list.append(
                (
                    quote_runs,
                    1.0,
                    base_size * 0.72 * line_spacing,
                    int(base_size * 0.8),
                    settings["quote_fg"],
                    False,
                )
            )
        elif block.kind == "list":
            for item in block.items:
                bullet_runs = [MarkdownRun(text="• ", bold=False, italic=False, code=False, color=settings["bullet_fg"])] + item
                block_runs_list.append(
                    (
                        bullet_runs,
                        1.0,
                        base_size * 0.34 * line_spacing,
                        int(base_size * 0.95),
                        settings["foreground"],
                        False,
                    )
                )
        else:
            block_runs_list.append((block.runs, 1.0, base_size * 0.62 * line_spacing, 0, settings["foreground"], False))

        for item_index, (runs, scale, spacing_after, indent, block_fill, force_bold) in enumerate(block_runs_list):
            size = max(int(round(base_size * scale)), 1)
            wrapped_lines = _wrap_runs_to_lines(
                runs,
                draw=draw,
                max_width=max_width - int(indent),
                font_resolver=font_for,
                size=size,
                default_fill=block_fill,
                code_fill=settings["code_fg"],
                force_bold=force_bold,
            )
            for line_index, line in enumerate(wrapped_lines):
                is_last_item_line = item_index == len(block_runs_list) - 1 and line_index == len(wrapped_lines) - 1
                line.spacing_after = spacing_after if is_last_item_line else base_size * 0.22 * line_spacing
                line.indent = float(indent)
                lines.append(line)

    if lines:
        lines[-1].spacing_after = 0.0
    return lines


def _wrap_runs_to_lines(
    runs: list[MarkdownRun],
    *,
    draw,
    max_width: int,
    font_resolver,
    size: int,
    default_fill: str,
    code_fill: str,
    force_bold: bool = False,
) -> list[LayoutLine]:
    tokens = list(_tokenize_runs(runs))
    lines: list[LayoutLine] = []
    current_segments: list[LayoutSegment] = []
    current_width = 0.0

    def flush() -> None:
        nonlocal current_segments, current_width
        current_segments = _trim_trailing_whitespace(current_segments)
        if not current_segments:
            current_width = 0.0
            return
        line_height = max(_segment_height(draw, segment) for segment in current_segments)
        line_width = sum(segment.width for segment in current_segments)
        lines.append(LayoutLine(kind="text", segments=current_segments, width=line_width, height=line_height, spacing_after=0.0))
        current_segments = []
        current_width = 0.0

    for token_text, run in tokens:
        font = font_resolver(size=size, bold=force_bold or run.bold, italic=run.italic, code=run.code)
        fill = run.color or (code_fill if run.code else default_fill)
        if token_text.isspace():
            if not current_segments:
                continue
            segment = LayoutSegment(text=token_text, font=font, width=float(draw.textlength(token_text, font=font)), fill=fill)
            if current_width + segment.width <= max_width:
                current_segments.append(segment)
                current_width += segment.width
            continue

        token_parts = _split_token_to_fit(token_text, draw=draw, font=font, max_width=max_width)
        for part in token_parts:
            segment = LayoutSegment(text=part, font=font, width=float(draw.textlength(part, font=font)), fill=fill)
            if current_segments and current_width + segment.width > max_width:
                flush()
            current_segments.append(segment)
            current_width += segment.width

    flush()
    return lines or [LayoutLine(kind="text", segments=[], width=0.0, height=size * 1.25, spacing_after=0.0)]


def _tokenize_runs(runs: list[MarkdownRun]) -> list[tuple[str, MarkdownRun]]:
    tokens: list[tuple[str, MarkdownRun]] = []
    for run in runs:
        for token in re.findall(r"\S+|\s+", run.text):
            tokens.append((token, run))
    return tokens


def _split_token_to_fit(token: str, *, draw, font, max_width: int) -> list[str]:
    if not token:
        return []
    if float(draw.textlength(token, font=font)) <= max_width:
        return [token]

    parts: list[str] = []
    current = ""
    for character in token:
        candidate = f"{current}{character}"
        if current and float(draw.textlength(candidate, font=font)) > max_width:
            parts.append(current)
            current = character
        else:
            current = candidate
    if current:
        parts.append(current)
    return parts


def _trim_trailing_whitespace(segments: list[LayoutSegment]) -> list[LayoutSegment]:
    trimmed = list(segments)
    while trimmed and trimmed[-1].text.isspace():
        trimmed.pop()
    return trimmed


def _segment_height(draw, segment: LayoutSegment) -> float:
    if not segment.text:
        return 0.0
    bbox = draw.textbbox((0, 0), segment.text, font=segment.font)
    return max(float(bbox[3] - bbox[1]), 1.0)


def _aligned_x(*, width: int, padding: int, content_width: float, align: str) -> float:
    if align == "left":
        return float(padding)
    if align == "right":
        return float(width - padding) - content_width
    return (width - content_width) / 2.0


def _normalize_align(value: str) -> str:
    lowered = value.strip().lower()
    return lowered if lowered in {"left", "center", "right"} else DEFAULT_ALIGN


def _normalize_valign(value: str) -> str:
    lowered = value.strip().lower()
    if lowered == "middle":
        return "middle"
    return lowered if lowered in {"top", "middle", "bottom"} else DEFAULT_VALIGN
