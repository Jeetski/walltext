from __future__ import annotations

import ctypes
import os
import subprocess
import sys
from pathlib import Path
from tkinter import Tk, StringVar, BooleanVar, messagebox, ttk
from PIL import Image, ImageTk

APP_NAME = "Walltext Setup"
REPO_ROOT = Path(__file__).resolve().parent
LOCAL_APPDATA = Path(os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local")))
INSTALL_ROOT = LOCAL_APPDATA / "walltext"
BIN_DIR = INSTALL_ROOT / "bin"
CONFIG_FILE = INSTALL_ROOT / "walltext.json"

def add_to_user_path(directory: Path) -> None:
    import winreg
    key_path = r"Environment"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
        try:
            current, _ = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            current = ""
        parts = [part for part in current.split(";") if part]
        normalized = {part.rstrip("\\").lower() for part in parts}
        target = str(directory).rstrip("\\")
        if target.lower() not in normalized:
            parts.append(target)
            winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, ";".join(parts))

    HWND_BROADCAST = 0xFFFF
    WM_SETTINGCHANGE = 0x001A
    SMTO_ABORTIFHUNG = 0x0002
    ctypes.windll.user32.SendMessageTimeoutW(HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment", SMTO_ABORTIFHUNG, 5000, None)

def write_cmd(path: Path, python_exe: str, module_args: str) -> None:
    content = f'@echo off\r\nsetlocal\r\n"{python_exe}" -m {module_args} %*\r\n'
    path.write_text(content, encoding="ascii")

def write_startup_launcher(destination: Path, python_exe: str, config_path: str) -> None:
    # A quiet vbs script to launch without console if wanted, or just a cmd.
    # To launch listener quietly, we can use pythonw
    pythonw_exe = python_exe.replace("python.exe", "pythonw.exe")
    if not Path(pythonw_exe).exists():
        pythonw_exe = python_exe
    
    content = f'@echo off\r\nstart "" /b "{pythonw_exe}" -m walltext listen --config "{config_path}"\r\n'
    destination.write_text(content, encoding="ascii")


class InstallerApp:
    def __init__(self) -> None:
        self.root = Tk()
        self.root.title(APP_NAME)
        self.root.geometry("760x520")
        self.root.resizable(False, False)
        
        icon_path = REPO_ROOT / "walltext" / "branding" / "walltext.ico"
        if icon_path.exists():
            try:
                self.root.iconbitmap(str(icon_path))
            except Exception:
                pass

        self.add_to_path = BooleanVar(value=True)
        self.enable_listener = BooleanVar(value=True)
        self.launch_manager = BooleanVar(value=True)
        
        self.step = 0
        self.status_var = StringVar(value="Ready to install.")
        
        self._logo_image = None
        self.build_ui()
        self.show_step(0)

    def build_ui(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        palette = {"bg": "#080808", "fg": "#ffffff", "border": "#333333", "accent": "#00aaff"}
        self.root.configure(bg=palette["bg"])
        style.configure(".", background=palette["bg"], foreground=palette["fg"], font=("Consolas", 10))
        style.configure("TFrame", background=palette["bg"])
        style.configure("TLabel", background=palette["bg"], foreground=palette["fg"])
        style.configure("TCheckbutton", background=palette["bg"], foreground=palette["fg"])
        style.configure("TButton", background=palette["bg"], foreground=palette["fg"], bordercolor=palette["border"])
        style.configure("Accent.TButton", background=palette["fg"], foreground=palette["bg"], bordercolor=palette["accent"])

        outer = ttk.Frame(self.root, padding=20)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)

        header = ttk.Frame(outer)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        
        logo_path = REPO_ROOT / "walltext" / "branding" / "walltext.png"
        if logo_path.exists():
            try:
                img = Image.open(logo_path)
                img.thumbnail((64, 64), getattr(Image, "Resampling", Image).LANCZOS)
                self._logo_image = ImageTk.PhotoImage(img)
                ttk.Label(header, image=self._logo_image).pack(side="left", padx=(0, 12))
            except Exception:
                pass

        title_frame = ttk.Frame(header)
        title_frame.pack(side="left")
        ttk.Label(title_frame, text="WALLTEXT INSTALLER", font=("Consolas", 20, "bold")).pack(anchor="w")
        ttk.Label(title_frame, text="Walltext by Hivemind Studio", font=("Consolas", 11)).pack(anchor="w")

        self.content = ttk.Frame(outer)
        self.content.grid(row=1, column=0, sticky="nsew")
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)

        self.pages = [
            self.build_welcome_page(),
            self.build_options_page(),
            self.build_progress_page(),
        ]
        for page in self.pages:
            page.grid(row=0, column=0, sticky="nsew")

        footer = ttk.Frame(outer)
        footer.grid(row=2, column=0, sticky="ew", pady=(16, 0))
        footer.columnconfigure(0, weight=1)
        ttk.Label(footer, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        self.back_button = ttk.Button(footer, text="Back", command=self.go_back)
        self.back_button.grid(row=0, column=1, padx=(8, 0))
        self.next_button = ttk.Button(footer, text="Next", command=self.go_next, style="Accent.TButton")
        self.next_button.grid(row=0, column=2, padx=(8, 0))
        ttk.Button(footer, text="Cancel", command=self.root.destroy).grid(row=0, column=3, padx=(8, 0))

    def build_welcome_page(self):
        frame = ttk.Frame(self.content)
        ttk.Label(frame, text="Welcome", font=("Consolas", 16, "bold")).pack(anchor="w", pady=(0, 12))
        ttk.Label(
            frame,
            text=(
                "This wizard installs Walltext into your local Python packages and configures "
                "the executable commands for easy terminal access.\n\n"
                "It can also arrange for the background wallpaper listener to "
                "run automatically at Windows login."
            ),
            wraplength=680,
            justify="left",
        ).pack(anchor="w")
        return frame

    def build_options_page(self):
        frame = ttk.Frame(self.content)
        ttk.Label(frame, text="Install Options", font=("Consolas", 16, "bold")).pack(anchor="w", pady=(0, 12))
        ttk.Checkbutton(frame, text="Add Walltext commands to the system PATH", variable=self.add_to_path).pack(anchor="w", pady=(0, 6))
        ttk.Checkbutton(frame, text="Run Walltext background listener at Windows Startup", variable=self.enable_listener).pack(anchor="w", pady=(0, 6))
        ttk.Checkbutton(frame, text="Launch Walltext Manager when setup finishes", variable=self.launch_manager).pack(anchor="w", pady=(14, 0))
        return frame

    def build_progress_page(self):
        frame = ttk.Frame(self.content)
        ttk.Label(frame, text="Installing", font=("Consolas", 16, "bold")).pack(anchor="w", pady=(0, 12))
        self.progress = ttk.Progressbar(frame, mode="determinate", maximum=100)
        self.progress.pack(fill="x")
        self.log = ttk.Label(frame, text="", justify="left", wraplength=680)
        self.log.pack(anchor="w", pady=(12, 0))
        return frame

    def show_step(self, step: int) -> None:
        self.step = step
        self.pages[step].tkraise()
        self.back_button.configure(state="normal" if step > 0 else "disabled")
        self.next_button.configure(text="Install" if step == 1 else "Next")
        if step == 2:
            self.back_button.configure(state="disabled")
            self.next_button.configure(state="disabled")

    def go_back(self) -> None:
        self.show_step(max(0, self.step - 1))

    def go_next(self) -> None:
        if self.step == 0:
            self.show_step(1)
            return
        if self.step == 1:
            self.show_step(2)
            self.root.after(50, self.run_install)

    def run_install(self) -> None:
        try:
            self.set_progress(10, "Upgrading pip...")
            py_exe = sys.executable
            subprocess.run([py_exe, "-m", "pip", "install", "--upgrade", "pip"], check=True, capture_output=True)

            self.set_progress(40, "Installing walltext package (editable mode)...")
            subprocess.run([py_exe, "-m", "pip", "install", "-e", str(REPO_ROOT)], check=True, capture_output=True)

            self.set_progress(60, "Initializing walltext config...")
            subprocess.run([py_exe, "-m", "walltext", "config", "init"], check=False)

            self.set_progress(70, "Creating bin directories and shortcuts...")
            BIN_DIR.mkdir(parents=True, exist_ok=True)
            
            write_cmd(BIN_DIR / "walltext.cmd", py_exe, "walltext")
            write_cmd(BIN_DIR / "walltext_manager.cmd", py_exe, "walltext manager --config \""+str(CONFIG_FILE)+"\"")
            write_cmd(BIN_DIR / "walltext_listener.cmd", py_exe, "walltext listen --config \""+str(CONFIG_FILE)+"\"")

            if self.enable_listener.get():
                self.set_progress(80, "Adding listener to Windows Startup...")
                startup_dir = Path(os.environ.get("APPDATA", "")) / "Microsoft\\Windows\\Start Menu\\Programs\\Startup"
                if startup_dir.exists():
                    write_startup_launcher(startup_dir / "walltext_listener.cmd", py_exe, str(CONFIG_FILE))

            if self.add_to_path.get():
                self.set_progress(90, "Adding to User PATH...")
                add_to_user_path(BIN_DIR)

            self.set_progress(100, "Installation complete.")
            self.status_var.set(f"Successfully installed Walltext!")
            self.next_button.configure(text="Finish", state="normal", command=self.finish_install)
            self.log.configure(text=f"Walltext package and CLI tools have been installed.\nConfigurations are located at:\n{INSTALL_ROOT}")
        except subprocess.CalledProcessError as exc:
            err = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else str(exc)
            self.status_var.set("Installation failed.")
            self.log.configure(text=f"Process Error:\n{err}")
            messagebox.showerror(APP_NAME, "Failed to install dependencies via pip.")
        except Exception as exc:
            self.status_var.set("Installation failed.")
            self.log.configure(text=str(exc))
            messagebox.showerror(APP_NAME, str(exc))

    def finish_install(self) -> None:
        if self.launch_manager.get():
            subprocess.Popen([sys.executable, "-m", "walltext", "manager"])
        self.root.destroy()

    def set_progress(self, value: int, text: str) -> None:
        self.progress["value"] = value
        self.status_var.set(text)
        self.log.configure(text=text)
        self.root.update_idletasks()

    def run(self) -> int:
        self.root.mainloop()
        return 0


def main() -> int:
    return InstallerApp().run()


if __name__ == "__main__":
    raise SystemExit(main())
