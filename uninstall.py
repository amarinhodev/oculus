#!/usr/bin/env python3
"""
O.C.U.L.U.S. — Cross-platform uninstaller
Supports: macOS, Linux, Windows

Usage:
    python uninstall.py
"""

import os
import platform
import shutil
import subprocess
import sys
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


def ok(msg: str) -> None:
    print(_ansi(f"[✓] {msg}", GREEN, BOLD))


def warn(msg: str) -> None:
    print(_ansi(f"[!] {msg}", YELLOW, BOLD))


def info(msg: str) -> None:
    print(_ansi(f"    {msg}", CYAN))


def err(msg: str) -> None:
    print(_ansi(f"[✗] {msg}", RED, BOLD))


def header(msg: str) -> None:
    print()
    print(_ansi(f"{'─' * 60}", WHITE))
    print(_ansi(f"  {msg}", WHITE, BOLD))
    print(_ansi(f"{'─' * 60}", WHITE))


# ---------------------------------------------------------------------------
# Step 1 — Detect OS
# ---------------------------------------------------------------------------

def step1_detect_os() -> str:
    header("Step 1 — Detect operating system")
    os_name = platform.system()
    ok(f"System detected: {os_name} ({platform.release()})")
    return os_name


# ---------------------------------------------------------------------------
# Step 2 — Stop and remove startup service
# ---------------------------------------------------------------------------

def _remove_macos() -> None:
    label = "com.oculus.watcher"
    plist_path = Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"

    if plist_path.exists():
        info("Unloading LaunchAgent ...")
        result = subprocess.run(
            ["launchctl", "unload", str(plist_path)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            warn(f"launchctl unload returned: {result.stderr.strip()}")

        plist_path.unlink(missing_ok=True)
        ok(f"LaunchAgent removed: {plist_path}")
    else:
        warn(f"LaunchAgent not found: {plist_path} — nothing to remove")


def _remove_linux() -> None:
    service_path = Path.home() / ".config" / "systemd" / "user" / "oculus.service"

    # Stop + disable (ignore errors if not running)
    subprocess.run(["systemctl", "--user", "stop", "oculus"],
                   capture_output=True)
    subprocess.run(["systemctl", "--user", "disable", "oculus"],
                   capture_output=True)

    if service_path.exists():
        service_path.unlink(missing_ok=True)
        info("Reloading systemd daemon ...")
        subprocess.run(["systemctl", "--user", "daemon-reload"],
                       capture_output=True)
        ok(f"systemd service removed: {service_path}")
    else:
        warn(f"Service file not found: {service_path} — nothing to remove")


def _remove_windows() -> None:
    task_name = "OCULUS Watcher"

    result = subprocess.run(
        ["schtasks", "/Delete", "/TN", task_name, "/F"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        ok(f"Task '{task_name}' removed from Task Scheduler")
    else:
        if "cannot find" in result.stderr.lower():
            warn(f"Task '{task_name}' not found — nothing to remove")
        else:
            err(f"Failed to remove task: {result.stderr.strip()}")
            info(f"Remove it manually in Task Scheduler: '{task_name}'")


def step2_remove_service(os_name: str) -> None:
    header("Step 2 — Stop and remove startup service")

    if os_name == "Darwin":
        _remove_macos()
    elif os_name == "Linux":
        _remove_linux()
    elif os_name == "Windows":
        _remove_windows()
    else:
        warn(f"System '{os_name}' not supported — skipping service removal")


# ---------------------------------------------------------------------------
# Step 3 — Remove Gemini CLI skill
# ---------------------------------------------------------------------------

def step3_remove_skill(os_name: str) -> None:
    header("Step 3 — Remove oculus-analyzer skill from Gemini CLI")

    if os_name == "Windows":
        appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        candidates = [Path(appdata) / "gemini" / "skills" / "oculus-analyzer"]
    else:
        candidates = [
            Path.home() / ".gemini" / "skills" / "oculus-analyzer",
            Path.home() / ".config" / "gemini" / "skills" / "oculus-analyzer",
        ]

    removed_any = False
    for skill_dir in candidates:
        if skill_dir.exists():
            shutil.rmtree(str(skill_dir))
            ok(f"Skill removed: {skill_dir}")
            removed_any = True

    if not removed_any:
        warn("oculus-analyzer skill not found — nothing to remove")


# ---------------------------------------------------------------------------
# Step 4 — Remove venv
# ---------------------------------------------------------------------------

def step4_remove_venv() -> None:
    header("Step 4 — Remove virtual environment (~/.oculus/venv/)")

    venv_dir = Path.home() / ".oculus" / "venv"
    if venv_dir.exists():
        shutil.rmtree(str(venv_dir))
        ok(f"venv removed: {venv_dir}")
    else:
        warn(f"venv not found at {venv_dir} — nothing to remove")

    # Check if ~/.oculus is now empty and remove it too
    oculus_home = Path.home() / ".oculus"
    if oculus_home.exists() and not any(oculus_home.iterdir()):
        oculus_home.rmdir()
        info(f"Directory {oculus_home} removed (was empty)")


# ---------------------------------------------------------------------------
# Step 5 — Optional: remove config.py
# ---------------------------------------------------------------------------

def step5_remove_config(oculus_dir: Path) -> None:
    header("Step 5 — Remove configuration (optional)")

    config_file = oculus_dir / "config.py"
    if not config_file.exists():
        warn("config.py not found — nothing to remove")
        return

    try:
        answer = input(
            _ansi("  Do you want to remove config.py as well? (y/N): ", WHITE)
        ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = "n"

    if answer in ("y", "yes"):
        config_file.unlink(missing_ok=True)
        ok("config.py removed")
    else:
        info("config.py kept (default)")


# ---------------------------------------------------------------------------
# Final confirmation
# ---------------------------------------------------------------------------

def final_message() -> None:
    print()
    print(_ansi("=" * 60, GREEN, BOLD))
    print(_ansi("  ✅  OCULUS uninstalled successfully!", GREEN, BOLD))
    print(_ansi("=" * 60, GREEN, BOLD))
    print()
    print(_ansi("  The watcher has been stopped and will no longer start automatically.", WHITE))
    print()
    print(_ansi("  Project files at:", WHITE))
    oculus_dir = Path(__file__).resolve().parent
    print(_ansi(f"    {oculus_dir}", CYAN))
    print(_ansi("  were kept — remove them manually if you no longer need them.", WHITE))
    print()
    print(_ansi("  To reinstall, run: python install.py", CYAN))
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print(_ansi("\n  O.C.U.L.U.S. — Cross-Platform Uninstaller\n", BOLD, CYAN))

    oculus_dir = Path(__file__).resolve().parent

    os_name = step1_detect_os()
    step2_remove_service(os_name)
    step3_remove_skill(os_name)
    step4_remove_venv()
    step5_remove_config(oculus_dir)
    final_message()


if __name__ == "__main__":
    main()
