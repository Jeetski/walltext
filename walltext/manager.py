from __future__ import annotations

import os
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox

try:
    from PIL import Image, ImageTk
except ModuleNotFoundError:
    Image = None
    ImageTk = None

from .config import (
    apply_from_config,
    bulk_add_items,
    create_file_item,
    create_inline_item,
    duplicate_item,
    export_items,
    format_time_string,
    import_items,
    item_preview,
    load_config,
    move_item,
    normalize_item,
    parse_time_string,
    remove_item,
    resolve_item,
    save_config,
    status_snapshot,
)
from .core import set_wallpaper
from .markdown import render_markdown_text, validate_markdown_text
from .runtime import (
    disable_startup,
    enable_startup,
    runtime_snapshot,
    start_listener_background,
    stop_listener_background,
)


UI_BG = "black"
UI_FG = "white"
UI_ALT = "#111111"
UI_INPUT_BG = "black"
UI_BORDER = "#222222"
UI_SELECT = "#1f1f1f"
UI_MUTED = "#aaaaaa"
UI_FONT = ("Consolas", 11)
UI_FONT_LARGE = ("Consolas", 13)


class WalltextManager:
    def __init__(self, config_path: str | Path | None = None) -> None:
        path, _ = load_config(config_path)
        self.config_path = path
        self.root = tk.Tk()
        self.root.title("Walltext Manager")
        self.root.configure(bg=UI_BG)
        self.root.geometry("1280x780")
        self.root.minsize(1180, 700)
        self.root.state("zoomed")

        branding_dir = Path(__file__).parent / "branding"
        icon_path = branding_dir / "walltext.ico"
        if icon_path.exists():
            try:
                self.root.iconbitmap(str(icon_path))
            except Exception:
                pass

        self.selection_mode_var = tk.StringVar()
        self.schedule_type_var = tk.StringVar()
        self.interval_minutes_var = tk.StringVar()
        self.daily_time_var = tk.StringVar()
        self.item_type_var = tk.StringVar(value="text")
        self.item_source_var = tk.StringVar(value="inline")
        self.item_file_var = tk.StringVar()
        self.item_details_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.font_var = tk.StringVar()
        self.font_size_var = tk.StringVar()
        self.padding_var = tk.StringVar()
        self.fg_var = tk.StringVar()
        self.bg_var = tk.StringVar()
        self.mode_var = tk.StringVar(value="list")
        self.markdown_path_var = tk.StringVar(value="unsaved markdown")
        self.markdown_preview_var = tk.StringVar()
        self.markdown_status_var = tk.StringVar()
        self.status_var = tk.StringVar()
        self.next_run_var = tk.StringVar()
        self.listener_var = tk.StringVar()
        self.startup_var = tk.StringVar()
        self.markdown_file_path: Path | None = None
        self.markdown_file_signature: tuple[int, int] | None = None
        self.markdown_dirty = False
        self._ignore_markdown_modified = False

        self._build_ui()
        self.root.bind("<FocusIn>", self._on_root_focus_in)
        self.reload()

    def run(self) -> None:
        self.root.mainloop()

    def _build_ui(self) -> None:
        shell = tk.Frame(self.root, bg=UI_BG)
        shell.pack(fill="both", expand=True, padx=16, pady=16)

        branding_dir = Path(__file__).parent / "branding"
        header_frame = tk.Frame(shell, bg=UI_BG)
        header_frame.pack(fill="x", pady=(0, 16))

        left_header = tk.Frame(header_frame, bg=UI_BG)
        left_header.pack(side="left")

        try:
            if Image and ImageTk:
                logo_path = branding_dir / "walltext.png"
                if logo_path.exists():
                    logo_img = Image.open(logo_path)
                    logo_img.thumbnail((64, 64), getattr(Image, "Resampling", Image).LANCZOS)
                    self._walltext_logo = ImageTk.PhotoImage(logo_img)
                    tk.Label(left_header, image=self._walltext_logo, bg=UI_BG).pack(side="left", padx=(0, 12))
        except Exception:
            pass

        title_frame = tk.Frame(left_header, bg=UI_BG)
        title_frame.pack(side="left")
        tk.Label(title_frame, text="Walltext v1", bg=UI_BG, fg=UI_FG, font=("Consolas", 18, "bold"), anchor="w").pack(fill="x")
        tk.Label(title_frame, text="Tiny Windows-first CLI for turning text into wallpapers", bg=UI_BG, fg=UI_MUTED, font=UI_FONT, anchor="w").pack(fill="x")

        right_header = tk.Frame(header_frame, bg=UI_BG)
        right_header.pack(side="right")

        studio_text_frame = tk.Frame(right_header, bg=UI_BG)
        studio_text_frame.pack(side="left")
        tk.Label(studio_text_frame, text="Hivemind Studio", bg=UI_BG, fg=UI_FG, font=("Consolas", 12, "bold"), anchor="e").pack(fill="x")
        
        link = tk.Label(studio_text_frame, text="hivemindstudio.art", bg=UI_BG, fg=UI_FG, cursor="hand2", font=("Consolas", 11, "underline"), anchor="e")
        link.pack(fill="x")
        link.bind("<Button-1>", lambda e: webbrowser.open("https://hivemindstudio.art"))

        try:
            if Image and ImageTk:
                hivemind_path = branding_dir / "hivemind_studio.png"
                if hivemind_path.exists():
                    hm_img = Image.open(hivemind_path)
                    hm_img.thumbnail((48, 48), getattr(Image, "Resampling", Image).LANCZOS)
                    self._hivemind_logo = ImageTk.PhotoImage(hm_img)
                    tk.Label(right_header, image=self._hivemind_logo, bg=UI_BG).pack(side="left", padx=(12, 0))
        except Exception:
            pass

        mode_row = tk.Frame(shell, bg=UI_BG)
        mode_row.pack(fill="x", pady=(0, 12))
        self.list_mode_button = self._button(mode_row, "List", lambda: self._switch_mode("list"))
        self.list_mode_button.pack(side="left", padx=(0, 8))
        self.markdown_mode_button = self._button(mode_row, "Markdown", lambda: self._switch_mode("markdown"))
        self.markdown_mode_button.pack(side="left")

        self.mode_container = tk.Frame(shell, bg=UI_BG)
        self.mode_container.pack(fill="both", expand=True)

        self.list_mode_frame = tk.Frame(self.mode_container, bg=UI_BG)
        self.markdown_mode_frame = tk.Frame(self.mode_container, bg=UI_BG)

        self._build_list_mode(self.list_mode_frame)
        self._build_markdown_mode(self.markdown_mode_frame)
        self._switch_mode("list")

    def _build_list_mode(self, parent: tk.Frame) -> None:
        left = tk.Frame(parent, bg=UI_BG, highlightbackground=UI_BORDER, highlightthickness=1)
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))

        right_shell = tk.Frame(parent, bg=UI_BG, highlightbackground=UI_BORDER, highlightthickness=1, width=470)
        right_shell.pack(side="right", fill="y")
        right_shell.pack_propagate(False)

        right_scrollbar = tk.Scrollbar(
            right_shell,
            bg=UI_INPUT_BG,
            activebackground=UI_INPUT_BG,
            troughcolor=UI_INPUT_BG,
            borderwidth=0,
            highlightthickness=0,
            elementborderwidth=0,
        )
        right_scrollbar.pack(side="right", fill="y")

        self.right_canvas = tk.Canvas(
            right_shell,
            bg=UI_BG,
            highlightthickness=0,
            borderwidth=0,
            relief="flat",
            yscrollcommand=right_scrollbar.set,
        )
        self.right_canvas.pack(side="left", fill="both", expand=True)
        right_scrollbar.config(command=self.right_canvas.yview)

        right = tk.Frame(self.right_canvas, bg=UI_BG)
        self._right_window = self.right_canvas.create_window((0, 0), window=right, anchor="nw")
        right.bind("<Configure>", self._on_right_content_configure)
        self.right_canvas.bind("<Configure>", self._on_right_canvas_configure)
        self._bind_mousewheel_to_right_panel(right)

        tk.Label(left, text="ITEMS", bg=UI_BG, fg=UI_FG, font=UI_FONT_LARGE, anchor="w").pack(fill="x", padx=12, pady=(12, 8))

        list_frame = tk.Frame(left, bg=UI_BG)
        list_frame.pack(fill="both", expand=True, padx=12)

        self.listbox = tk.Listbox(
            list_frame,
            bg=UI_BG,
            fg=UI_FG,
            selectbackground=UI_SELECT,
            selectforeground=UI_FG,
            borderwidth=0,
            highlightthickness=0,
            activestyle="none",
            font=UI_FONT,
            exportselection=False,
        )
        self.listbox.pack(side="left", fill="both", expand=True)
        self.listbox.bind("<<ListboxSelect>>", self._on_list_select)

        scrollbar = tk.Scrollbar(
            list_frame,
            command=self.listbox.yview,
            bg=UI_INPUT_BG,
            activebackground=UI_INPUT_BG,
            troughcolor=UI_INPUT_BG,
            borderwidth=0,
            highlightthickness=0,
            elementborderwidth=0,
        )
        scrollbar.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=scrollbar.set)

        button_row = tk.Frame(left, bg=UI_BG)
        button_row.pack(fill="x", padx=12, pady=(12, 8))
        self._button(button_row, "↑ Move Up", self.move_up).pack(side="left", padx=(0, 8))
        self._button(button_row, "↓ Move Down", self.move_down).pack(side="left", padx=(0, 8))
        self._button(button_row, "⧉ Duplicate", self.duplicate_selected).pack(side="left", padx=(0, 8))
        self._button(button_row, "✖ Remove", self.remove_selected).pack(side="left")

        import_row = tk.Frame(left, bg=UI_BG)
        import_row.pack(fill="x", padx=12, pady=(0, 12))
        self._button(import_row, "⭳ Import JSON", self.import_json).pack(side="left", padx=(0, 8))
        self._button(import_row, "⭳ Import TXT", self.import_text).pack(side="left", padx=(0, 8))
        self._button(import_row, "▤ Bulk Add", self.bulk_add_dialog).pack(side="left", padx=(0, 8))
        self._button(import_row, "⭱ Export JSON", self.export_json).pack(side="left", padx=(0, 8))
        self._button(import_row, "⭱ Export TXT", self.export_text).pack(side="left")

        self._section_label(right, "ITEM").pack(fill="x", padx=12, pady=(12, 6))
        item_frame = tk.Frame(right, bg=UI_BG)
        item_frame.pack(fill="x", padx=12)
        self._radio(item_frame, "Text", self.item_type_var, "text", self._sync_item_widgets).pack(anchor="w")
        self._radio(item_frame, "Markdown", self.item_type_var, "markdown", self._sync_item_widgets).pack(anchor="w")
        self._radio(item_frame, "Inline", self.item_source_var, "inline", self._sync_item_widgets).pack(anchor="w", pady=(8, 0))
        self._radio(item_frame, "File Pointer", self.item_source_var, "file", self._sync_item_widgets).pack(anchor="w")

        self.item_file_shell = tk.Frame(right, bg=UI_BG)
        self.item_file_shell.pack(fill="x", padx=12, pady=(10, 0))
        self._label(self.item_file_shell, "Item File").pack(anchor="w")
        item_file_row = tk.Frame(self.item_file_shell, bg=UI_BG)
        item_file_row.pack(fill="x", pady=(4, 0))
        self.item_file_entry = self._entry(item_file_row, self.item_file_var)
        self.item_file_entry.pack(side="left", fill="x", expand=True)
        self._button(item_file_row, "📂 Browse", self.pick_item_file).pack(side="left", padx=(8, 0))
        self._button(item_file_row, "↗ Open", self.open_item_file).pack(side="left", padx=(8, 0))

        self._section_label(right, "DETAILS").pack(fill="x", padx=12, pady=(12, 6))
        item_details = tk.Label(
            right,
            textvariable=self.item_details_var,
            bg=UI_BG,
            fg=UI_MUTED,
            justify="left",
            anchor="w",
            wraplength=430,
            font=UI_FONT,
        )
        item_details.pack(fill="x", padx=12)

        tk.Label(right, text="EDITOR", bg=UI_BG, fg=UI_FG, font=UI_FONT_LARGE, anchor="w").pack(fill="x", padx=12, pady=(12, 8))

        self.editor = tk.Text(
            right,
            height=10,
            wrap="word",
            bg=UI_INPUT_BG,
            fg=UI_FG,
            insertbackground=UI_FG,
            relief="flat",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=UI_BORDER,
            highlightcolor=UI_BORDER,
            font=UI_FONT,
        )
        self.editor.pack(fill="x", padx=12)

        editor_buttons_1 = tk.Frame(right, bg=UI_BG)
        editor_buttons_1.pack(fill="x", padx=12, pady=(12, 4))
        self._button(editor_buttons_1, "➕ Add", self.add_item).pack(side="left", padx=(0, 8))
        self._button(editor_buttons_1, "✍ Update", self.update_selected).pack(side="left", padx=(0, 8))
        self._button(editor_buttons_1, "⎚ Clear", self.clear_editor).pack(side="left")

        editor_buttons_2 = tk.Frame(right, bg=UI_BG)
        editor_buttons_2.pack(fill="x", padx=12, pady=(0, 12))
        self._button(editor_buttons_2, "📝 Edit Md", self.open_selected_in_markdown_mode).pack(side="left", padx=(0, 8))
        self._button(editor_buttons_2, "▶ Apply Selected", self.apply_selected).pack(side="left", padx=(0, 8))
        self._button(editor_buttons_2, "▶ Apply Next", self.apply_now).pack(side="left")

        self._section_label(right, "SELECTION").pack(fill="x", padx=12, pady=(6, 6))
        selection_frame = tk.Frame(right, bg=UI_BG)
        selection_frame.pack(fill="x", padx=12)
        self._radio(selection_frame, "Random", self.selection_mode_var, "random").pack(anchor="w")
        self._radio(selection_frame, "In Order", self.selection_mode_var, "sequence").pack(anchor="w")

        self._section_label(right, "SCHEDULE").pack(fill="x", padx=12, pady=(16, 6))
        schedule_frame = tk.Frame(right, bg=UI_BG)
        schedule_frame.pack(fill="x", padx=12)
        self._radio(schedule_frame, "Once Per Day", self.schedule_type_var, "daily", self._sync_schedule_widgets).pack(anchor="w")
        self._radio(schedule_frame, "Every X Minutes", self.schedule_type_var, "interval", self._sync_schedule_widgets).pack(anchor="w")

        schedule_values = tk.Frame(right, bg=UI_BG)
        schedule_values.pack(fill="x", padx=12, pady=(8, 0))
        self._label(schedule_values, "Daily Time").grid(row=0, column=0, sticky="w")
        self.daily_time_entry = self._entry(schedule_values, self.daily_time_var, width=10)
        self.daily_time_entry.grid(row=0, column=1, sticky="w", padx=(12, 18))
        self._label(schedule_values, "Minutes").grid(row=0, column=2, sticky="w")
        self.interval_entry = self._entry(schedule_values, self.interval_minutes_var, width=10)
        self.interval_entry.grid(row=0, column=3, sticky="w", padx=(12, 0))

        next_run = tk.Label(
            right,
            textvariable=self.next_run_var,
            bg=UI_BG,
            fg=UI_MUTED,
            justify="left",
            anchor="w",
            font=UI_FONT,
        )
        next_run.pack(fill="x", padx=12, pady=(8, 0))

        self._section_label(right, "RENDER").pack(fill="x", padx=12, pady=(16, 6))

        render_output = tk.Frame(right, bg=UI_BG)
        render_output.pack(fill="x", padx=12)
        self._label(render_output, "Output PNG").pack(anchor="w")
        output_row = tk.Frame(render_output, bg=UI_BG)
        output_row.pack(fill="x", pady=(4, 0))
        self.output_entry = self._entry(output_row, self.output_var)
        self.output_entry.pack(side="left", fill="x", expand=True)
        self._button(output_row, "📂 Browse", self.pick_output).pack(side="left", padx=(8, 0))

        render_font = tk.Frame(right, bg=UI_BG)
        render_font.pack(fill="x", padx=12, pady=(10, 0))
        self._label(render_font, "Font").pack(anchor="w")
        font_row = tk.Frame(render_font, bg=UI_BG)
        font_row.pack(fill="x", pady=(4, 0))
        self.font_entry = self._entry(font_row, self.font_var)
        self.font_entry.pack(side="left", fill="x", expand=True)
        self._button(font_row, "📂 Browse", self.pick_font).pack(side="left", padx=(8, 0))
        self._button(font_row, "⎚ Clear", self.clear_font).pack(side="left", padx=(8, 0))

        render_values = tk.Frame(right, bg=UI_BG)
        render_values.pack(fill="x", padx=12, pady=(10, 0))
        self._label(render_values, "Size").grid(row=0, column=0, sticky="w")
        self._entry(render_values, self.font_size_var, width=8).grid(row=0, column=1, sticky="w", padx=(12, 18))
        self._label(render_values, "Padding").grid(row=0, column=2, sticky="w")
        self._entry(render_values, self.padding_var, width=8).grid(row=0, column=3, sticky="w", padx=(12, 0))
        self._label(render_values, "FG").grid(row=1, column=0, sticky="w", pady=(10, 0))
        self._entry(render_values, self.fg_var, width=12).grid(row=1, column=1, sticky="w", padx=(12, 18), pady=(10, 0))
        self._label(render_values, "BG").grid(row=1, column=2, sticky="w", pady=(10, 0))
        self._entry(render_values, self.bg_var, width=12).grid(row=1, column=3, sticky="w", padx=(12, 0), pady=(10, 0))

        render_actions = tk.Frame(right, bg=UI_BG)
        render_actions.pack(fill="x", padx=12, pady=(12, 0))
        self._button(render_actions, "💾 Save Settings", self.save_settings).pack(side="left", padx=(0, 8))
        self._button(render_actions, "📂 Open Config", self.open_config_folder).pack(side="left", padx=(0, 8))
        self._button(render_actions, "📂 Open Output", self.open_output_folder).pack(side="left")

        self._section_label(right, "LISTENER").pack(fill="x", padx=12, pady=(16, 6))
        listener_info = tk.Label(
            right,
            textvariable=self.listener_var,
            bg=UI_BG,
            fg=UI_FG,
            justify="left",
            anchor="w",
            font=UI_FONT,
        )
        listener_info.pack(fill="x", padx=12)

        startup_info = tk.Label(
            right,
            textvariable=self.startup_var,
            bg=UI_BG,
            fg=UI_MUTED,
            justify="left",
            anchor="w",
            font=UI_FONT,
        )
        startup_info.pack(fill="x", padx=12, pady=(6, 0))

        listener_actions = tk.Frame(right, bg=UI_BG)
        listener_actions.pack(fill="x", padx=12, pady=(12, 0))
        self._button(listener_actions, "▶ Start Listener", self.start_listener).pack(side="left", padx=(0, 8))
        self._button(listener_actions, "⏹ Stop Listener", self.stop_listener).pack(side="left", padx=(0, 8))
        self._button(listener_actions, "⚡ Enable Startup", self.enable_startup).pack(side="left", padx=(0, 8))
        self._button(listener_actions, "🚫 Disable Startup", self.disable_startup).pack(side="left")

        footer_actions = tk.Frame(right, bg=UI_BG)
        footer_actions.pack(fill="x", padx=12, pady=(12, 0))
        self._button(footer_actions, "⟳ Reload", self.reload).pack(side="left", padx=(0, 8))
        self._button(footer_actions, "⏮ Reset Sequence", self.reset_sequence_state).pack(side="left")

        status = tk.Label(
            right,
            textvariable=self.status_var,
            bg=UI_BG,
            fg=UI_FG,
            justify="left",
            wraplength=430,
            anchor="w",
            font=UI_FONT,
        )
        status.pack(fill="x", padx=12, pady=(16, 12))

    def _build_markdown_mode(self, parent: tk.Frame) -> None:
        shell = tk.Frame(parent, bg=UI_BG, highlightbackground=UI_BORDER, highlightthickness=1)
        shell.pack(fill="both", expand=True)

        tk.Label(shell, text="MARKDOWN", bg=UI_BG, fg=UI_FG, font=UI_FONT_LARGE, anchor="w").pack(fill="x", padx=12, pady=(12, 8))

        file_row = tk.Frame(shell, bg=UI_BG)
        file_row.pack(fill="x", padx=12)
        self._label(file_row, "File").pack(side="left")
        self.markdown_path_entry = self._entry(file_row, self.markdown_path_var)
        self.markdown_path_entry.pack(side="left", fill="x", expand=True, padx=(12, 8))
        self.markdown_path_entry.configure(state="readonly")
        self._button(file_row, "📄 New", self.new_markdown_document).pack(side="left", padx=(0, 8))
        self._button(file_row, "📂 Open", self.open_markdown_file).pack(side="left", padx=(0, 8))
        self._button(file_row, "⟳ Reload", self.reload_markdown_file).pack(side="left", padx=(0, 8))
        self._button(file_row, "💾 Save", self.save_markdown_document).pack(side="left", padx=(0, 8))
        self._button(file_row, "💾 Save As", self.save_markdown_document_as).pack(side="left")

        toolbar = tk.Frame(shell, bg=UI_BG)
        toolbar.pack(fill="x", padx=12, pady=(12, 8))
        self._button(toolbar, "H1", lambda: self.insert_markdown_heading(1)).pack(side="left", padx=(0, 8))
        self._button(toolbar, "H2", lambda: self.insert_markdown_heading(2)).pack(side="left", padx=(0, 8))
        self._button(toolbar, "H3", lambda: self.insert_markdown_heading(3)).pack(side="left", padx=(0, 8))
        self._button(toolbar, "B", lambda: self.wrap_markdown_selection("**", "**")).pack(side="left", padx=(0, 8))
        self._button(toolbar, "I", lambda: self.wrap_markdown_selection("*", "*")).pack(side="left", padx=(0, 8))
        self._button(toolbar, "</>", lambda: self.wrap_markdown_selection("`", "`")).pack(side="left", padx=(0, 8))
        self._button(toolbar, "🎨", self.insert_markdown_color).pack(side="left", padx=(0, 8))
        self._button(toolbar, "❞", lambda: self.prefix_markdown_lines("> ")).pack(side="left", padx=(0, 8))
        self._button(toolbar, "☰", lambda: self.prefix_markdown_lines("- ")).pack(side="left", padx=(0, 8))
        self._button(toolbar, "—", self.insert_markdown_rule).pack(side="left")

        info = tk.Label(
            shell,
            text="Frontmatter supports theme, accent, heading_fg, quote_fg, code_fg, rule_fg, bullet_fg, line_spacing, align, and valign. Render/apply use the current saved walltext render settings.",
            bg=UI_BG,
            fg=UI_MUTED,
            justify="left",
            anchor="w",
            font=UI_FONT,
        )
        info.pack(fill="x", padx=12)

        preview = tk.Label(
            shell,
            textvariable=self.markdown_preview_var,
            bg=UI_BG,
            fg=UI_FG,
            justify="left",
            anchor="w",
            wraplength=1180,
            font=UI_FONT,
        )
        preview.pack(fill="x", padx=12, pady=(8, 0))

        editor_frame = tk.Frame(shell, bg=UI_BG)
        editor_frame.pack(fill="both", expand=True, padx=12, pady=(10, 0))

        markdown_scrollbar = tk.Scrollbar(
            editor_frame,
            bg=UI_INPUT_BG,
            activebackground=UI_INPUT_BG,
            troughcolor=UI_INPUT_BG,
            borderwidth=0,
            highlightthickness=0,
            elementborderwidth=0,
        )
        markdown_scrollbar.pack(side="right", fill="y")

        self.markdown_editor = tk.Text(
            editor_frame,
            wrap="word",
            bg=UI_INPUT_BG,
            fg=UI_FG,
            insertbackground=UI_FG,
            relief="flat",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=UI_BORDER,
            highlightcolor=UI_BORDER,
            font=UI_FONT,
            yscrollcommand=markdown_scrollbar.set,
        )
        self.markdown_editor.pack(side="left", fill="both", expand=True)
        self.markdown_editor.bind("<<Modified>>", self._on_markdown_modified)
        markdown_scrollbar.config(command=self.markdown_editor.yview)

        actions = tk.Frame(shell, bg=UI_BG)
        actions.pack(fill="x", padx=12, pady=12)
        self._button(actions, "🖼 Render", self.render_markdown_document).pack(side="left", padx=(0, 8))
        self._button(actions, "▶ Apply", self.apply_markdown_document).pack(side="left", padx=(0, 8))
        self._button(actions, "➕ Add To List", self.add_markdown_to_list).pack(side="left", padx=(0, 8))
        self._button(actions, "📂 Load Selected", self.open_selected_in_markdown_mode).pack(side="left", padx=(0, 8))
        self._button(actions, "⎚ Clear", self.clear_markdown_editor).pack(side="left")

        status = tk.Label(
            shell,
            textvariable=self.markdown_status_var,
            bg=UI_BG,
            fg=UI_FG,
            justify="left",
            wraplength=1180,
            anchor="w",
            font=UI_FONT,
        )
        status.pack(fill="x", padx=12, pady=(0, 12))

    def reload(self) -> None:
        previous_index = self._selected_index()
        _, self.config = load_config(self.config_path)
        snapshot = status_snapshot(self.config_path)
        runtime = runtime_snapshot(self.config_path)

        self._populate_items()
        self.selection_mode_var.set(self.config["selection_mode"])
        self.schedule_type_var.set(self.config["schedule"]["type"])
        self.interval_minutes_var.set(str(self.config["schedule"]["minutes"]))
        self.daily_time_var.set(format_time_string(self.config["schedule"]["hour"], self.config["schedule"]["minute"]))
        self.output_var.set(self.config["render"]["output"])
        self.font_var.set(self.config["render"]["font"] or "")
        self.font_size_var.set(str(self.config["render"]["size"]))
        self.padding_var.set(str(self.config["render"]["padding"]))
        self.fg_var.set(self.config["render"]["fg"])
        self.bg_var.set(self.config["render"]["bg"])
        self._sync_schedule_widgets()
        self._sync_item_widgets()

        if previous_index is not None and previous_index < self.listbox.size():
            self.listbox.selection_set(previous_index)
            self._on_list_select()
        elif self.listbox.size():
            self.listbox.selection_set(0)
            self._on_list_select()
        else:
            self.clear_editor()
            self.item_details_var.set("No item selected.")

        self.next_run_var.set(
            "next run: "
            + str(snapshot["next_due_at"])
            + "\ndue now: "
            + str(snapshot["due"])
        )

        listener = runtime["listener"]
        self.listener_var.set(
            "listener: "
            + ("running" if listener["running"] else "stopped")
            + "\npid: "
            + str(listener["pid"])
        )
        self.startup_var.set(
            "startup: "
            + ("enabled" if runtime["startup"]["enabled"] else "disabled")
            + "\nstartup file: "
            + str(runtime["startup"]["path"])
        )

        self.status_var.set(
            "config: "
            + str(self.config_path)
            + "\nitems: "
            + str(snapshot["item_count"])
            + "\nlast applied: "
            + str(snapshot["last_applied_at"])
            + "\nlast item index: "
            + str(snapshot["last_item_index"])
            + "\noutput: "
            + str(snapshot["render"]["output"])
        )
        self._update_markdown_preview()
        self._switch_mode(self.mode_var.get())

    def add_item(self) -> None:
        try:
            item = self._build_item_from_inputs()
        except ValueError as exc:
            self._set_status(str(exc))
            return

        self.config["items"].append(item)
        save_config(self.config, self.config_path)
        self.reload()
        self.listbox.selection_clear(0, "end")
        self.listbox.selection_set(max(self.listbox.size() - 1, 0))
        self._on_list_select()
        self._set_status("Item added.")

    def update_selected(self) -> None:
        index = self._selected_index()
        if index is None:
            self._set_status("Select an item to update.")
            return

        try:
            item = self._build_item_from_inputs()
        except ValueError as exc:
            self._set_status(str(exc))
            return

        self.config["items"][index] = item
        save_config(self.config, self.config_path)
        self.reload()
        self.listbox.selection_set(index)
        self._on_list_select()
        self._set_status("Item updated.")

    def duplicate_selected(self) -> None:
        index = self._selected_index()
        if index is None:
            self._set_status("Select an item to duplicate.")
            return

        duplicate_item(self.config_path, index)
        self.reload()
        self.listbox.selection_set(min(index + 1, self.listbox.size() - 1))
        self._set_status("Item duplicated.")

    def remove_selected(self) -> None:
        index = self._selected_index()
        if index is None:
            self._set_status("Select an item to remove.")
            return

        if not messagebox.askyesno("Walltext Manager", "Remove the selected item?"):
            return

        remove_item(self.config_path, index)
        self.reload()
        self.clear_editor()
        self._set_status("Item removed.")

    def move_up(self) -> None:
        self._move_selected("up")

    def move_down(self) -> None:
        self._move_selected("down")

    def save_settings(self) -> bool:
        try:
            minutes = max(int(self.interval_minutes_var.get() or "1"), 1)
            hour, minute = parse_time_string(self.daily_time_var.get() or "00:00")
            size = max(int(self.font_size_var.get() or "1"), 1)
            padding = max(int(self.padding_var.get() or "0"), 0)
        except ValueError as exc:
            messagebox.showerror("Walltext Manager", str(exc))
            return False

        _, config = load_config(self.config_path)
        config["selection_mode"] = self.selection_mode_var.get()
        config["schedule"]["type"] = self.schedule_type_var.get()
        config["schedule"]["minutes"] = minutes
        config["schedule"]["hour"] = hour
        config["schedule"]["minute"] = minute
        config["render"]["output"] = self.output_var.get().strip() or config["render"]["output"]
        config["render"]["font"] = self.font_var.get().strip() or None
        config["render"]["size"] = size
        config["render"]["padding"] = padding
        config["render"]["fg"] = self.fg_var.get().strip() or "white"
        config["render"]["bg"] = self.bg_var.get().strip() or "black"
        save_config(config, self.config_path)
        self.reload()
        self._set_status("Settings saved.")
        return True

    def apply_now(self) -> None:
        if not self.save_settings():
            return
        try:
            result = apply_from_config(self.config_path, force=True)
        except Exception as exc:
            messagebox.showerror("Walltext Manager", str(exc))
            return

        self.reload()
        self._set_status(f"Applied item {result['item_index']}.")

    def apply_selected(self) -> None:
        index = self._selected_index()
        if index is None:
            self._set_status("Select an item to apply.")
            return
        if not self.save_settings():
            return

        try:
            result = apply_from_config(self.config_path, force=True, item_index=index)
        except Exception as exc:
            messagebox.showerror("Walltext Manager", str(exc))
            return

        self.reload()
        self._set_status(f"Applied selected item {result['item_index']}.")

    def start_listener(self) -> None:
        if not self.save_settings():
            return
        try:
            result = start_listener_background(self.config_path, poll_interval=30.0)
        except Exception as exc:
            messagebox.showerror("Walltext Manager", str(exc))
            return

        self.reload()
        self._set_status(f"Listener running: pid {result['pid']}.")

    def stop_listener(self) -> None:
        try:
            result = stop_listener_background()
        except Exception as exc:
            messagebox.showerror("Walltext Manager", str(exc))
            return

        self.reload()
        self._set_status("Listener stopped." if result["stopped"] else "Listener was not running.")

    def enable_startup(self) -> None:
        if not self.save_settings():
            return
        enable_startup(self.config_path, poll_interval=30.0)
        self.reload()
        self._set_status("Startup enabled.")

    def disable_startup(self) -> None:
        disable_startup()
        self.reload()
        self._set_status("Startup disabled.")

    def reset_sequence_state(self) -> None:
        _, config = load_config(self.config_path)
        config["state"]["last_applied_at"] = None
        config["state"]["last_item_index"] = None
        config["state"]["last_item_text"] = None
        config["state"]["next_index"] = 0
        config["state"]["applied_count"] = 0
        save_config(config, self.config_path)
        self.reload()
        self._set_status("Sequence state reset.")

    def import_json(self) -> None:
        path = filedialog.askopenfilename(
            title="Import JSON Items",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return

        import_items(self.config_path, path, replace=False, mode="json")
        self.reload()
        self._set_status("Imported JSON items.")

    def import_text(self) -> None:
        path = filedialog.askopenfilename(
            title="Import Text Items",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return

        import_items(self.config_path, path, replace=False, mode="lines")
        self.reload()
        self._set_status("Imported text items.")

    def export_json(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export JSON Items",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
        )
        if not path:
            return

        export_items(self.config_path, path, format_name="json")
        self._set_status("Exported JSON items.")

    def export_text(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export Text Items",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")],
        )
        if not path:
            return

        export_items(self.config_path, path, format_name="txt")
        self._set_status("Exported text items.")

    def bulk_add_dialog(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Bulk Add")
        dialog.configure(bg=UI_BG)
        dialog.geometry("720x520")
        dialog.transient(self.root)
        dialog.grab_set()

        mode_var = tk.StringVar(value="blocks")
        replace_var = tk.BooleanVar(value=False)

        tk.Label(dialog, text="Paste items below", bg=UI_BG, fg=UI_FG, font=UI_FONT_LARGE, anchor="w").pack(fill="x", padx=12, pady=(12, 8))
        text = tk.Text(
            dialog,
            wrap="word",
            bg=UI_INPUT_BG,
            fg=UI_FG,
            insertbackground=UI_FG,
            relief="flat",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=UI_BORDER,
            highlightcolor=UI_BORDER,
            font=UI_FONT,
        )
        text.pack(fill="both", expand=True, padx=12)

        controls = tk.Frame(dialog, bg=UI_BG)
        controls.pack(fill="x", padx=12, pady=12)
        self._radio(controls, "Blank-line blocks", mode_var, "blocks").pack(side="left", padx=(0, 12))
        self._radio(controls, "One item per line", mode_var, "lines").pack(side="left", padx=(0, 12))
        tk.Checkbutton(
            controls,
            text="Replace existing items",
            variable=replace_var,
            bg=UI_BG,
            fg=UI_FG,
            selectcolor=UI_BG,
            activebackground=UI_BG,
            activeforeground=UI_FG,
            highlightthickness=0,
            font=UI_FONT,
        ).pack(side="left")

        buttons = tk.Frame(dialog, bg=UI_BG)
        buttons.pack(fill="x", padx=12, pady=(0, 12))

        def submit() -> None:
            payload = text.get("1.0", "end").strip()
            if not payload:
                messagebox.showerror("Walltext Manager", "Nothing to import.")
                return

            bulk_add_items(self.config_path, payload, mode=mode_var.get(), replace=replace_var.get())
            self.reload()
            self._set_status("Bulk import complete.")
            dialog.destroy()

        self._button(buttons, "➕ Add", submit).pack(side="left", padx=(0, 8))
        self._button(buttons, "✖ Cancel", dialog.destroy).pack(side="left")

    def pick_output(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Select Output PNG",
            defaultextension=".png",
            filetypes=[("PNG files", "*.png")],
        )
        if path:
            self.output_var.set(path)

    def pick_font(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Font",
            filetypes=[("TrueType fonts", "*.ttf"), ("OpenType fonts", "*.otf"), ("All files", "*.*")],
        )
        if path:
            self.font_var.set(path)

    def clear_font(self) -> None:
        self.font_var.set("")

    def open_config_folder(self) -> None:
        self._open_path(self.config_path.parent)

    def open_output_folder(self) -> None:
        output = Path(self.output_var.get().strip()).expanduser()
        self._open_path(output.parent)

    def clear_editor(self) -> None:
        self.item_type_var.set("text")
        self.item_source_var.set("inline")
        self.item_file_var.set("")
        self._set_text_widget_content(self.editor, "", editable=True)
        self._sync_item_widgets()

    def clear_markdown_editor(self) -> None:
        self.markdown_file_path = None
        self.markdown_file_signature = None
        self.markdown_dirty = False
        self.markdown_path_var.set("unsaved markdown")
        self._set_text_widget_content(self.markdown_editor, "", editable=True)
        self._update_markdown_preview()
        self._set_markdown_status("Markdown editor cleared.")

    def pick_item_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Text or Markdown File",
            filetypes=[("Text and Markdown", "*.txt *.md"), ("All files", "*.*")],
        )
        if path:
            self.item_file_var.set(path)
            self.item_source_var.set("file")
            self.item_type_var.set("markdown" if Path(path).suffix.lower() == ".md" else "text")
            self._sync_item_widgets()

    def open_item_file(self) -> None:
        value = self.item_file_var.get().strip()
        if not value:
            self._set_status("Select a file-backed item path first.")
            return
        self._open_path(self._resolve_manager_path(value))

    def new_markdown_document(self) -> None:
        self.markdown_file_path = None
        self.markdown_file_signature = None
        self.markdown_dirty = False
        self.markdown_path_var.set("unsaved markdown")
        self._set_text_widget_content(self.markdown_editor, "", editable=True)
        self._update_markdown_preview()
        self._switch_mode("markdown")
        self._set_markdown_status("New Markdown document.")

    def open_markdown_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Open Markdown File",
            filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
        )
        if not path:
            return
        self._load_markdown_file(Path(path))

    def save_markdown_document(self) -> None:
        if self.markdown_file_path is None:
            self.save_markdown_document_as()
            return
        self.markdown_file_path.write_text(self._markdown_text(), encoding="utf-8")
        self.markdown_dirty = False
        self.markdown_file_signature = self._file_signature(self.markdown_file_path)
        self.markdown_path_var.set(str(self.markdown_file_path))
        self._update_markdown_preview()
        self._set_markdown_status(f"Saved {self.markdown_file_path.name}.")

    def save_markdown_document_as(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save Markdown File",
            defaultextension=".md",
            filetypes=[("Markdown files", "*.md")],
        )
        if not path:
            return
        self.markdown_file_path = Path(path).expanduser().resolve()
        self.save_markdown_document()

    def render_markdown_document(self) -> None:
        text = self._markdown_text()
        if not text:
            self._set_markdown_status("Markdown editor is empty.")
            return
        _, config = load_config(self.config_path)
        render_settings = dict(config["render"])
        try:
            image_path = render_markdown_text(text, output_path=render_settings["output"], defaults=render_settings)
        except Exception as exc:
            messagebox.showerror("Walltext Manager", str(exc))
            return
        self._set_markdown_status(f"Rendered {image_path}.")

    def apply_markdown_document(self) -> None:
        text = self._markdown_text()
        if not text:
            self._set_markdown_status("Markdown editor is empty.")
            return
        _, config = load_config(self.config_path)
        render_settings = dict(config["render"])
        try:
            image_path = render_markdown_text(text, output_path=render_settings["output"], defaults=render_settings)
            set_wallpaper(image_path)
        except Exception as exc:
            messagebox.showerror("Walltext Manager", str(exc))
            return
        self.reload()
        self._set_markdown_status(f"Applied {image_path}.")

    def add_markdown_to_list(self) -> None:
        text = self._markdown_text()
        if not text:
            self._set_markdown_status("Markdown editor is empty.")
            return
        if self.markdown_file_path is not None:
            item = create_file_item(self.markdown_file_path, item_type="markdown", config_dir=self.config_path.parent)
            detail = f"Added markdown file item: {self.markdown_file_path.name}."
        else:
            item = create_inline_item(text, item_type="markdown")
            detail = "Added inline markdown item."
        self.config["items"].append(item)
        save_config(self.config, self.config_path)
        self.reload()
        self._set_markdown_status(detail)

    def open_selected_in_markdown_mode(self) -> None:
        index = self._selected_index()
        if index is None:
            self._set_status("Select an item first.")
            return

        item = normalize_item(self.config["items"][index], config_dir=self.config_path.parent)
        if item["source"] == "file" and item["type"] == "markdown":
            self._load_markdown_file(self._resolve_manager_path(item["path"]))
            return

        try:
            resolved = resolve_item(self.config["items"][index], config_path=self.config_path)
        except Exception as exc:
            messagebox.showerror("Walltext Manager", str(exc))
            return

        self.markdown_file_path = None
        self.markdown_file_signature = None
        self.markdown_dirty = False
        self.markdown_path_var.set("unsaved markdown")
        self._set_text_widget_content(self.markdown_editor, resolved["value"], editable=True)
        self._update_markdown_preview()
        self._switch_mode("markdown")
        self._set_markdown_status("Loaded selected item into Markdown mode.")

    def reload_markdown_file(self) -> None:
        if self.markdown_file_path is None:
            self._set_markdown_status("No Markdown file is open.")
            return
        if self.markdown_dirty and not messagebox.askyesno(
            "Walltext Manager",
            "Reload the file and discard unsaved Markdown edits?",
        ):
            return
        self._load_markdown_file(self.markdown_file_path)

    def _populate_items(self) -> None:
        self.listbox.delete(0, "end")
        for index, item in enumerate(self.config["items"]):
            self.listbox.insert("end", f"{index:02d}  {item_preview(item)}")

    def _selected_index(self) -> int | None:
        selection = self.listbox.curselection()
        return selection[0] if selection else None

    def _on_list_select(self, _event: object | None = None) -> None:
        index = self._selected_index()
        if index is None:
            return

        item = self.config["items"][index]
        normalized = normalize_item(item, config_dir=self.config_path.parent)
        self.item_type_var.set(normalized["type"])
        self.item_source_var.set(normalized["source"])
        self.item_file_var.set(normalized.get("path", ""))

        try:
            resolved = resolve_item(item, config_path=self.config_path)
            self._set_text_widget_content(self.editor, resolved["value"], editable=normalized["source"] == "inline")
            self._set_item_details(item, resolved)
        except Exception as exc:
            self._set_text_widget_content(self.editor, str(exc), editable=False)
            self._set_item_details(item, error=str(exc))

        self._sync_item_widgets()
        if normalized["source"] == "file":
            self._set_status("Previewing a file-backed item. Update changes the pointer path, not the file contents.")
        elif normalized["type"] == "markdown":
            self._set_status("Editing an inline Markdown item.")
        else:
            self._set_status("Editing an inline text item.")

    def _move_selected(self, direction: str) -> None:
        index = self._selected_index()
        if index is None:
            self._set_status("Select an item to move.")
            return

        move_item(self.config_path, index, direction)
        self.reload()
        target = max(index - 1, 0) if direction == "up" else min(index + 1, self.listbox.size() - 1)
        self.listbox.selection_set(target)
        self._set_status(f"Moved item {direction}.")

    def _editor_text(self) -> str:
        return self.editor.get("1.0", "end").strip()

    def _markdown_text(self) -> str:
        return self.markdown_editor.get("1.0", "end").strip()

    def _build_item_from_inputs(self) -> dict[str, str]:
        item_type = self.item_type_var.get().strip() or "text"
        source = self.item_source_var.get().strip() or "inline"
        if source == "file":
            path = self.item_file_var.get().strip()
            if not path:
                raise ValueError("Choose a file for this item.")
            return create_file_item(path, item_type=item_type, config_dir=self.config_path.parent)

        text = self._editor_text()
        if not text:
            raise ValueError("Editor is empty.")
        return create_inline_item(text, item_type=item_type)

    def _sync_schedule_widgets(self) -> None:
        if self.schedule_type_var.get() == "interval":
            self.interval_entry.config(state="normal")
            self.daily_time_entry.config(state="disabled")
        else:
            self.interval_entry.config(state="disabled")
            self.daily_time_entry.config(state="normal")

    def _sync_item_widgets(self) -> None:
        if self.item_source_var.get() == "file":
            self.item_file_entry.config(state="normal")
            self.editor.config(state="disabled")
        else:
            self.item_file_entry.config(state="disabled")
            self.editor.config(state="normal")

    def _on_right_content_configure(self, _event: tk.Event) -> None:
        self.right_canvas.configure(scrollregion=self.right_canvas.bbox("all"))

    def _on_right_canvas_configure(self, event: tk.Event) -> None:
        self.right_canvas.itemconfigure(self._right_window, width=event.width)

    def _set_status(self, value: str) -> None:
        self.status_var.set(value)

    def _set_markdown_status(self, value: str) -> None:
        self.markdown_status_var.set(value)

    def _switch_mode(self, mode: str) -> None:
        normalized = "markdown" if mode == "markdown" else "list"
        self.mode_var.set(normalized)
        self.list_mode_frame.pack_forget()
        self.markdown_mode_frame.pack_forget()
        if normalized == "markdown":
            self.markdown_mode_frame.pack(fill="both", expand=True)
        else:
            self.list_mode_frame.pack(fill="both", expand=True)
        self.list_mode_button.configure(bg=UI_SELECT if normalized == "list" else UI_ALT)
        self.markdown_mode_button.configure(bg=UI_SELECT if normalized == "markdown" else UI_ALT)

    def _set_text_widget_content(self, widget: tk.Text, text: str, *, editable: bool) -> None:
        is_markdown = widget is self.markdown_editor
        if is_markdown:
            self._ignore_markdown_modified = True
        widget.config(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.config(state="normal" if editable else "disabled")
        if is_markdown:
            widget.edit_modified(False)
            self._ignore_markdown_modified = False

    def _load_markdown_file(self, path: Path) -> None:
        resolved = path.expanduser().resolve()
        text = resolved.read_text(encoding="utf-8-sig")
        self.markdown_file_path = resolved
        self.markdown_file_signature = self._file_signature(resolved)
        self.markdown_dirty = False
        self.markdown_path_var.set(str(resolved))
        self._set_text_widget_content(self.markdown_editor, text, editable=True)
        self._update_markdown_preview()
        self._switch_mode("markdown")
        self._set_markdown_status(f"Opened {resolved.name}.")

    def _resolve_manager_path(self, value: str) -> Path:
        path = Path(value).expanduser()
        if path.is_absolute():
            return path.resolve()
        return (self.config_path.parent / path).resolve()

    def insert_markdown_heading(self, level: int) -> None:
        self.prefix_markdown_lines("#" * max(level, 1) + " ")

    def insert_markdown_color(self) -> None:
        color = colorchooser.askcolor(title="Select Text Color", parent=self.root)
        if color and color[1]:
            self.wrap_markdown_selection(f"[color={color[1]}]", "[/color]")

    def wrap_markdown_selection(self, prefix: str, suffix: str) -> None:
        try:
            start = self.markdown_editor.index("sel.first")
            end = self.markdown_editor.index("sel.last")
            selected = self.markdown_editor.get(start, end)
            self.markdown_editor.delete(start, end)
            self.markdown_editor.insert(start, f"{prefix}{selected}{suffix}")
            return
        except tk.TclError:
            insert_at = self.markdown_editor.index("insert")
            self.markdown_editor.insert(insert_at, f"{prefix}{suffix}")
            self.markdown_editor.mark_set("insert", f"{insert_at}+{len(prefix)}c")

    def prefix_markdown_lines(self, prefix: str) -> None:
        try:
            start_index = self.markdown_editor.index("sel.first linestart")
            end_index = self.markdown_editor.index("sel.last lineend")
        except tk.TclError:
            cursor_line = self.markdown_editor.index("insert linestart")
            line_text = self.markdown_editor.get(cursor_line, f"{cursor_line} lineend")
            self.markdown_editor.delete(cursor_line, f"{cursor_line} lineend")
            self.markdown_editor.insert(cursor_line, prefix + line_text)
            return

        block_text = self.markdown_editor.get(start_index, end_index)
        updated = "\n".join(prefix + line if line else prefix.rstrip() for line in block_text.splitlines())
        self.markdown_editor.delete(start_index, end_index)
        self.markdown_editor.insert(start_index, updated)

    def insert_markdown_rule(self) -> None:
        self.markdown_editor.insert("insert", "\n---\n")

    def _set_item_details(self, item: dict[str, str], resolved: dict[str, object] | None = None, *, error: str | None = None) -> None:
        normalized = normalize_item(item, config_dir=self.config_path.parent)
        lines = [
            f"type: {normalized['type']}",
            f"source: {normalized['source']}",
            f"preview: {item_preview(item, max_length=140)}",
        ]
        if normalized["source"] == "file":
            lines.append(f"path: {normalized.get('path', '')}")
        if resolved and resolved.get("resolved_path"):
            lines.append(f"resolved: {resolved['resolved_path']}")
        if resolved and isinstance(resolved.get("value"), str):
            value = str(resolved["value"])
            lines.append(f"chars: {len(value)}")
            lines.append(f"lines: {len(value.splitlines()) or 1}")
            if normalized["type"] == "markdown":
                try:
                    md_details = validate_markdown_text(value)
                    lines.append(f"md blocks: {md_details['block_count']}")
                    lines.append(f"md frontmatter: {', '.join(sorted(md_details['frontmatter'].keys())) or 'none'}")
                except Exception as exc:
                    lines.append(f"md error: {exc}")
        if error:
            lines.append(f"error: {error}")
        self.item_details_var.set("\n".join(lines))

    def _update_markdown_preview(self) -> None:
        text = self._markdown_text()
        hints = "hints: # heading  **bold**  *italic*  `code`  > quote  - list  --- rule  |  frontmatter: theme, accent, line_spacing"
        if not text:
            file_state = self._markdown_file_state()
            self.markdown_preview_var.set(f"{hints}\npreview: empty document{file_state}")
            return

        try:
            details = validate_markdown_text(text)
            frontmatter = ", ".join(sorted(details["frontmatter"].keys())) or "none"
            block_types = ", ".join(details["block_types"][:5]) or "none"
            extra = "" if len(details["block_types"]) <= 5 else f" +{len(details['block_types']) - 5}"
            file_state = self._markdown_file_state()
            theme = details["frontmatter"].get("theme", "custom")
            accent = details["frontmatter"].get("accent", "default")
            spacing = details["frontmatter"].get("line_spacing", "1.0")
            self.markdown_preview_var.set(
                f"{hints}\nblocks: {details['block_count']} ({block_types}{extra}) | frontmatter: {frontmatter} | theme: {theme} | accent: {accent} | spacing: {spacing}{file_state}"
            )
        except Exception as exc:
            self.markdown_preview_var.set(f"{hints}\npreview error: {exc}")

    def _markdown_file_state(self) -> str:
        if self.markdown_file_path is None:
            return " | file: unsaved"
        dirty = "dirty" if self.markdown_dirty else "saved"
        return f" | file: {self.markdown_file_path.name} ({dirty})"

    def _on_markdown_modified(self, _event: tk.Event | None = None) -> None:
        if self._ignore_markdown_modified or not self.markdown_editor.edit_modified():
            return
        self.markdown_dirty = True
        self.markdown_editor.edit_modified(False)
        self._update_markdown_preview()

    def _on_root_focus_in(self, _event: tk.Event | None = None) -> None:
        self._check_external_markdown_change()

    def _check_external_markdown_change(self) -> None:
        if self.mode_var.get() != "markdown" or self.markdown_file_path is None:
            return
        current = self._file_signature(self.markdown_file_path)
        if current is None or self.markdown_file_signature is None or current == self.markdown_file_signature:
            return

        prompt = "Reload it now?" if not self.markdown_dirty else "Reload it now and discard unsaved edits?"
        should_reload = messagebox.askyesno(
            "Walltext Manager",
            f"The open Markdown file changed on disk.\n\n{self.markdown_file_path}\n\n{prompt}",
        )
        if should_reload:
            self._load_markdown_file(self.markdown_file_path)
            return

        self.markdown_file_signature = current
        self._set_markdown_status("Markdown file changed on disk. Keeping current editor contents.")

    def _file_signature(self, path: Path) -> tuple[int, int] | None:
        try:
            stat = path.stat()
        except OSError:
            return None
        return stat.st_mtime_ns, stat.st_size

    def _open_path(self, path: Path) -> None:
        try:
            os.startfile(path)
        except OSError as exc:
            messagebox.showerror("Walltext Manager", str(exc))

    def _button(self, parent: tk.Misc, text: str, command) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=UI_ALT,
            fg=UI_FG,
            activebackground=UI_SELECT,
            activeforeground=UI_FG,
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=10,
            pady=8,
            font=UI_FONT,
        )

    def _radio(self, parent: tk.Misc, text: str, variable: tk.Variable, value: str, command=None) -> tk.Radiobutton:
        return tk.Radiobutton(
            parent,
            text=text,
            variable=variable,
            value=value,
            command=command,
            bg=UI_BG,
            fg=UI_FG,
            selectcolor=UI_BG,
            activebackground=UI_BG,
            activeforeground=UI_FG,
            highlightthickness=0,
            font=UI_FONT,
        )

    def _label(self, parent: tk.Misc, text: str) -> tk.Label:
        return tk.Label(parent, text=text, bg=UI_BG, fg=UI_FG, anchor="w", font=UI_FONT)

    def _entry(self, parent: tk.Misc, variable: tk.StringVar, *, width: int | None = None) -> tk.Entry:
        return tk.Entry(
            parent,
            textvariable=variable,
            bg=UI_INPUT_BG,
            fg=UI_FG,
            insertbackground=UI_FG,
            disabledbackground=UI_INPUT_BG,
            disabledforeground=UI_FG,
            readonlybackground=UI_INPUT_BG,
            relief="flat",
            width=width,
            font=UI_FONT,
        )

    def _section_label(self, parent: tk.Misc, text: str) -> tk.Label:
        return tk.Label(parent, text=text, bg=UI_BG, fg=UI_FG, anchor="w", font=UI_FONT_LARGE)

    def _bind_mousewheel_to_right_panel(self, widget: tk.Misc) -> None:
        widget.bind("<Enter>", lambda _event: self.root.bind_all("<MouseWheel>", self._on_right_mousewheel))
        widget.bind("<Leave>", lambda _event: self.root.unbind_all("<MouseWheel>"))

    def _on_right_mousewheel(self, event: tk.Event) -> None:
        if event.delta:
            self.right_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


def launch_manager(config_path: str | Path | None = None) -> None:
    WalltextManager(config_path).run()
