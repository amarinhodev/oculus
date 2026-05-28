#!/usr/bin/env python3
"""
O.C.U.L.U.S. — Cross-platform installer (Native Mode)
Supports: macOS, Linux, Windows

This version installs dependencies directly into the current Python environment
and registers the watcher as a system service using the current interpreter.
"""

import os
import platform
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

# ---------------------------------------------------------------------------
# ANSI color helpers
# ---------------------------------------------------------------------------

RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
WHITE  = "\033[97m"

def _ansi(text: str, *codes: str) -> str:
    if platform.system() == "Windows":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            return text
    return "".join(codes) + text + RESET

def ok(msg: str) -> None: print(_ansi(f"[✓] {msg}", GREEN, BOLD))
def warn(msg: str) -> None: print(_ansi(f"[!] {msg}", YELLOW, BOLD))
def err(msg: str) -> None: print(_ansi(f"[✗] {msg}", RED, BOLD))
def info(msg: str) -> None: print(_ansi(f"    {msg}", CYAN))
def header(msg: str) -> None:
    print()
    print(_ansi(f"{'─' * 60}", WHITE))
    print(_ansi(f"  {msg}", WHITE, BOLD))
    print(_ansi(f"{'─' * 60}", WHITE))

def abort(msg: str, hint: str = "") -> None:
    err(msg)
    if hint:
        print()
        info("How to fix:")
        for line in hint.strip().splitlines():
            info(f"  {line}")
    sys.exit(1)

def run(cmd: list[str], check: bool = True, capture: bool = True, **kwargs):
    result = subprocess.run(cmd, capture_output=capture, text=True, **kwargs)
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(str(c) for c in cmd)}\nstdout: {result.stdout}\nstderr: {result.stderr}")
    return result

# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

def step1_detect_os() -> str:
    header("Step 1 — Detect operating system")
    os_name = platform.system()
    supported = {"Darwin", "Linux", "Windows"}
    if os_name not in supported:
        abort(f"System '{os_name}' is not supported.", f"Supported systems: {', '.join(supported)}")
    ok(f"System detected: {os_name}")
    return os_name

def step2_check_python() -> None:
    header("Step 2 — Verify Python version")
    major, minor = sys.version_info[:2]
    if major < 3 or (major == 3 and minor < 11):
        abort(f"Python {major}.{minor} found — minimum required: 3.11")
    ok(f"Python {major}.{minor} — OK")

def step3_install_dependencies(oculus_dir: Path) -> None:
    header("Step 3 — Install dependencies into current environment")
    req_file = oculus_dir / "requirements.txt"
    if req_file.exists():
        info(f"Installing from {req_file} ...")
        try:
            # Try normal install first
            run([sys.executable, "-m", "pip", "install", "--upgrade", "pip", "--quiet"])
            run([sys.executable, "-m", "pip", "install", "-r", str(req_file), "--quiet"])
            ok("Dependencies installed successfully")
        except Exception:
            info("Externally managed environment detected. Using --break-system-packages ...")
            try:
                run([sys.executable, "-m", "pip", "install", "-r", str(req_file), "--quiet", "--break-system-packages"])
                ok("Dependencies installed successfully (system-wide)")
            except Exception as exc:
                abort("Failed to install dependencies.", str(exc))
    else:
        warn("requirements.txt not found — skipping")

def step4_gemini_cli() -> str:
    header("Step 4 — Verify Gemini CLI")
    gemini_path = shutil.which("gemini")
    if gemini_path:
        ok(f"gemini CLI found at: {gemini_path}")
        return gemini_path
    
    abort("gemini CLI not found in PATH.", "Please install it first: npm install -g @google/gemini-cli")

def step5_install_skill(os_name: str, oculus_dir: Path) -> None:
    header("Step 5 — Install oculus-analyzer skill")
    skill_src = oculus_dir / "skills" / "oculus-analyzer" / "SKILL.md"
    if not skill_src.exists():
        warn("SKILL.md not found — skipping")
        return

    skills_dir = Path.home() / ".gemini" / "skills"
    if os_name == "Windows":
        appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        skills_dir = Path(appdata) / "gemini" / "skills"
    
    dest_dir = skills_dir / "oculus-analyzer"
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(skill_src), str(dest_dir / "SKILL.md"))
    ok(f"Skill installed at {dest_dir}")

def step6_configure(oculus_dir: Path, gemini_path: str) -> None:
    header("Step 6 — Configuration")
    config_file = oculus_dir / "config.py"
    if config_file.exists():
        # Update GEMINI_BIN even if config exists to ensure it uses the detected path
        content = config_file.read_text(encoding="utf-8")
        if 'GEMINI_BIN =' in content:
            import re
            content = re.sub(r'GEMINI_BIN\s*=\s*.*', f'GEMINI_BIN = "{gemini_path}"', content)
            config_file.write_text(content, encoding="utf-8")
        ok("config.py updated with current gemini path")
        return

    template = (oculus_dir / "config.example.py").read_text(encoding="utf-8")
    user_name = input(_ansi("  User name: ", WHITE)).strip() or "You"
    obsidian_path = input(_ansi("  Obsidian vault path: ", WHITE)).strip() or str(Path.home() / "Documents" / "Obsidian")
    
    patched = template.replace('USER_NAME = "Your Name"', f'USER_NAME = "{user_name}"')
    patched = patched.replace('GEMINI_BIN = "gemini"', f'GEMINI_BIN = "{gemini_path}"')
    if "OBSIDIAN_VAULT" not in patched:
        patched += f'\nOBSIDIAN_VAULT = "{obsidian_path}"\n'
    
    config_file.write_text(patched, encoding="utf-8")
    ok("config.py created")

def _register_macos(python_bin: str, oculus_dir: Path) -> None:
    label = "com.oculus.watcher"
    plist_path = Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"
    log_dir = Path.home() / ".oculus"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Capture current environment to inject into Plist
    env_vars = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(Path.home()),
        "SHELL": os.environ.get("SHELL", "/bin/zsh")
    }
    
    env_dict_str = "\n".join([f"            <key>{k}</key>\n            <string>{v}</string>" for k, v in env_vars.items()])

    plist_content = textwrap.dedent(f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
            <key>Label</key>
            <string>{label}</string>
            <key>ProgramArguments</key>
            <array>
                <string>{python_bin}</string>
                <string>{oculus_dir}/watcher.py</string>
            </array>
            <key>WorkingDirectory</key>
            <string>{oculus_dir}</string>
            <key>EnvironmentVariables</key>
            <dict>
{env_dict_str}
            </dict>
            <key>RunAtLoad</key>
            <true/>
            <key>KeepAlive</key>
            <true/>
            <key>StandardOutPath</key>
            <string>{log_dir}/watcher.log</string>
            <key>StandardErrorPath</key>
            <string>{log_dir}/watcher_error.log</string>
        </dict>
        </plist>
    """)

    if plist_path.exists(): subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)
    plist_path.write_text(plist_content, encoding="utf-8")
    subprocess.run(["launchctl", "load", str(plist_path)], check=True)
    ok("LaunchAgent registered and loaded")

def main():
    print(_ansi("\n  O.C.U.L.U.S. — Native Installer\n", BOLD, CYAN))
    oculus_dir = Path(__file__).resolve().parent
    os_name = step1_detect_os()
    step2_check_python()
    step3_install_dependencies(oculus_dir)
    gemini_path = step4_gemini_cli()
    step5_install_skill(os_name, oculus_dir)
    step6_configure(oculus_dir, gemini_path)
    
    if os_name == "Darwin":
        _register_macos(sys.executable, oculus_dir)
    
    header("Installation Complete!")
    info("The O.C.U.L.U.S. watcher is now running natively in the background.")

if __name__ == "__main__":
    main()
