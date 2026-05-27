#!/usr/bin/env python3
"""
O.C.U.L.U.S. — Cross-platform installer
Supports: macOS, Linux, Windows

Usage:
    python install.py

This script MUST be run with the system Python (not venv).
It uses only stdlib so it works before the venv is created.
"""

import os
import platform
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

# ---------------------------------------------------------------------------
# ANSI color helpers (no external dependencies)
# ---------------------------------------------------------------------------

RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
WHITE  = "\033[97m"

def _ansi(text: str, *codes: str) -> str:
    """Wrap text in ANSI escape codes (disabled on Windows cmd when not supported)."""
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


def err(msg: str) -> None:
    print(_ansi(f"[✗] {msg}", RED, BOLD))


def info(msg: str) -> None:
    print(_ansi(f"    {msg}", CYAN))


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
    """Run a subprocess command."""
    result = subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        **kwargs,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(str(c) for c in cmd)}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return result


# ---------------------------------------------------------------------------
# Step 1 — Detect OS
# ---------------------------------------------------------------------------

def step1_detect_os() -> str:
    header("Step 1 — Detect operating system")
    os_name = platform.system()
    supported = {"Darwin", "Linux", "Windows"}
    if os_name not in supported:
        abort(f"System '{os_name}' is not supported.", f"Supported systems: {', '.join(supported)}")
    ok(f"System detected: {os_name} ({platform.release()})")
    return os_name


# ---------------------------------------------------------------------------
# Step 2 — Verify Python 3.11+
# ---------------------------------------------------------------------------

def step2_check_python() -> None:
    header("Step 2 — Verify Python version")
    major, minor = sys.version_info[:2]
    version_str = f"{major}.{minor}.{sys.version_info[2]}"
    if major < 3 or (major == 3 and minor < 11):
        abort(
            f"Python {version_str} found — minimum required: 3.11",
            textwrap.dedent("""\
                Install Python 3.11 or higher:
                  macOS:   brew install python@3.11
                  Linux:   sudo apt install python3.11   (or dnf/pacman equivalent)
                  Windows: https://www.python.org/downloads/
                Then run again: python install.py"""),
        )
    ok(f"Python {version_str} — OK")


# ---------------------------------------------------------------------------
# Step 3 — Create venv and install dependencies
# ---------------------------------------------------------------------------

def step3_create_venv(oculus_dir: Path) -> Path:
    header("Step 3 — Create venv and install dependencies")

    venv_dir = Path.home() / ".oculus" / "venv"
    venv_dir.parent.mkdir(parents=True, exist_ok=True)

    if venv_dir.exists():
        warn(f"venv already exists at {venv_dir} — reusing")
    else:
        info(f"Creating venv at {venv_dir} ...")
        try:
            run([sys.executable, "-m", "venv", str(venv_dir)])
        except RuntimeError as exc:
            abort("Failed to create venv.", str(exc))
        ok(f"venv created at {venv_dir}")

    # Determine venv Python / pip paths
    if platform.system() == "Windows":
        venv_python = venv_dir / "Scripts" / "python.exe"
        venv_pip    = venv_dir / "Scripts" / "pip.exe"
    else:
        venv_python = venv_dir / "bin" / "python3"
        venv_pip    = venv_dir / "bin" / "pip"

    # Upgrade pip silently
    info("Upgrading pip ...")
    run([str(venv_python), "-m", "pip", "install", "--quiet", "--upgrade", "pip"])

    # Install from requirements.txt
    req_file = oculus_dir / "requirements.txt"
    if req_file.exists():
        info(f"Installing dependencies from {req_file} ...")
        try:
            run([str(venv_pip), "install", "--quiet", "-r", str(req_file)])
        except RuntimeError as exc:
            abort("Failed to install dependencies.", str(exc))
        ok("Dependencies installed successfully")
    else:
        warn(f"requirements.txt not found at {req_file} — skipping")

    return venv_python


# ---------------------------------------------------------------------------
# Step 4 — Verify / install Gemini CLI
# ---------------------------------------------------------------------------

def step4_gemini_cli() -> None:
    header("Step 4 — Verify Gemini CLI")

    if shutil.which("gemini"):
        ok("gemini CLI is already in PATH")
        return

    warn("gemini CLI not found in PATH")
    npm = shutil.which("npm")

    if npm is None:
        abort(
            "npm not found — cannot install Gemini CLI automatically.",
            textwrap.dedent("""\
                Install Node.js (which includes npm):
                  macOS:   brew install node
                  Linux:   https://nodejs.org/en/download/package-manager
                  Windows: https://nodejs.org/en/download/
                Then run again: python install.py"""),
        )

    info("Installing @google/gemini-cli via npm ...")
    try:
        run(["npm", "install", "-g", "@google/gemini-cli"], capture=False)
    except RuntimeError as exc:
        abort("Failed to install Gemini CLI via npm.", str(exc))

    # Verify again
    if shutil.which("gemini"):
        ok("gemini CLI installed successfully")
    else:
        abort(
            "gemini CLI installed but not found in PATH.",
            textwrap.dedent("""\
                Add the npm global bin directory to your PATH:
                  macOS/Linux: export PATH="$(npm bin -g):$PATH"
                  Windows: check system environment variables
                Then run again: python install.py"""),
        )


# ---------------------------------------------------------------------------
# Step 5 — Install oculus-analyzer skill into Gemini CLI
# ---------------------------------------------------------------------------

def step5_install_skill(os_name: str, oculus_dir: Path) -> None:
    header("Step 5 — Install oculus-analyzer skill into Gemini CLI")

    skill_src = oculus_dir / "skills" / "oculus-analyzer" / "SKILL.md"
    if not skill_src.exists():
        warn(f"SKILL.md not found at {skill_src} — skipping step")
        return

    # Locate gemini skills directory
    if os_name == "Windows":
        appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        candidates = [Path(appdata) / "gemini" / "skills"]
    else:
        candidates = [
            Path.home() / ".gemini" / "skills",
            Path.home() / ".config" / "gemini" / "skills",
        ]

    # Use first candidate (create if needed)
    skills_dir = candidates[0]
    skills_dir.mkdir(parents=True, exist_ok=True)

    dest_dir = skills_dir / "oculus-analyzer"
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest_file = dest_dir / "SKILL.md"
    shutil.copy2(str(skill_src), str(dest_file))

    ok(f"Skill oculus-analyzer installed at {dest_dir}")


# ---------------------------------------------------------------------------
# Step 6 — Interactive config (only on first install)
# ---------------------------------------------------------------------------

def step6_configure(oculus_dir: Path) -> None:
    header("Step 6 — Initial configuration")

    config_file   = oculus_dir / "config.py"
    config_example = oculus_dir / "config.example.py"

    if config_file.exists():
        ok("config.py already exists — skipping interactive configuration")
        return

    if not config_example.exists():
        warn("config.example.py not found — skipping interactive configuration")
        return

    print()
    print(_ansi("  OCULUS initial configuration", BOLD, CYAN))
    print(_ansi("  Answer the questions below (Enter to accept the default):", CYAN))
    print()

    # Read template
    template = config_example.read_text(encoding="utf-8")

    # Ask minimal questions
    user_name = input(_ansi("  User name (as it appears in transcriptions): ", WHITE)).strip()
    if not user_name:
        user_name = "You"

    obsidian_path = input(_ansi("  Obsidian vault path (e.g. ~/Documents/Obsidian): ", WHITE)).strip()
    if not obsidian_path:
        obsidian_path = str(Path.home() / "Documents" / "Obsidian")

    lang_input = input(_ansi("  Preferred language (pt-BR / en-US / es) [en-US]: ", WHITE)).strip()
    lang_map = {
        "pt-br": "Brazilian Portuguese",
        "pt":    "Brazilian Portuguese",
        "en-us": "English",
        "en":    "English",
        "es":    "Spanish",
    }
    preferred_language = lang_map.get(lang_input.lower(), "English")

    # Patch template
    patched = template
    patched = patched.replace('USER_NAME = "Your Name"', f'USER_NAME = "{user_name}"')
    patched = patched.replace('PREFERRED_LANGUAGE = "English"', f'PREFERRED_LANGUAGE = "{preferred_language}"')

    # Add OBSIDIAN_VAULT line if not present
    if "OBSIDIAN_VAULT" not in patched:
        patched += f'\n# Obsidian vault path (set during install)\nOBSIDIAN_VAULT = "{obsidian_path}"\n'
    else:
        import re
        patched = re.sub(
            r'OBSIDIAN_VAULT\s*=\s*["\'].*?["\']',
            f'OBSIDIAN_VAULT = "{obsidian_path}"',
            patched,
        )

    config_file.write_text(patched, encoding="utf-8")
    ok(f"config.py created at {config_file}")


# ---------------------------------------------------------------------------
# Step 7 — Register startup service
# ---------------------------------------------------------------------------

def _register_macos(venv_python: Path, oculus_dir: Path) -> None:
    """Create and load a LaunchAgent plist for macOS."""
    watcher_script = oculus_dir / "watcher.py"
    label = "com.oculus.watcher"
    plist_dir = Path.home() / "Library" / "LaunchAgents"
    plist_dir.mkdir(parents=True, exist_ok=True)
    plist_path = plist_dir / f"{label}.plist"

    log_out = Path.home() / ".oculus" / "watcher.log"
    log_err = Path.home() / ".oculus" / "watcher_error.log"
    log_out.parent.mkdir(parents=True, exist_ok=True)

    plist_content = textwrap.dedent(f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
            "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
            <key>Label</key>
            <string>{label}</string>
            <key>ProgramArguments</key>
            <array>
                <string>{venv_python}</string>
                <string>{watcher_script}</string>
            </array>
            <key>WorkingDirectory</key>
            <string>{oculus_dir}</string>
            <key>RunAtLoad</key>
            <true/>
            <key>KeepAlive</key>
            <true/>
            <key>StandardOutPath</key>
            <string>{log_out}</string>
            <key>StandardErrorPath</key>
            <string>{log_err}</string>
        </dict>
        </plist>
    """)

    # Unload first if it already exists (idempotent)
    if plist_path.exists():
        warn("LaunchAgent already exists — reloading ...")
        subprocess.run(["launchctl", "unload", str(plist_path)],
                       capture_output=True)

    plist_path.write_text(plist_content, encoding="utf-8")
    info(f"Plist created: {plist_path}")

    result = subprocess.run(
        ["launchctl", "load", str(plist_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        abort(
            "Failed to load LaunchAgent.",
            f"Error: {result.stderr}\n"
            f"Try manually: launchctl load {plist_path}",
        )
    ok("LaunchAgent loaded — OCULUS will start on next login")


def _register_linux(venv_python: Path, oculus_dir: Path) -> None:
    """Create and enable a systemd --user service for Linux."""
    watcher_script = oculus_dir / "watcher.py"
    service_dir = Path.home() / ".config" / "systemd" / "user"
    service_dir.mkdir(parents=True, exist_ok=True)
    service_path = service_dir / "oculus.service"

    log_dir = Path.home() / ".oculus"
    log_dir.mkdir(parents=True, exist_ok=True)

    service_content = textwrap.dedent(f"""\
        [Unit]
        Description=OCULUS — Google Meet Transcript Watcher
        After=network.target

        [Service]
        Type=simple
        ExecStart={venv_python} {watcher_script}
        WorkingDirectory={oculus_dir}
        Restart=on-failure
        RestartSec=10
        StandardOutput=append:{log_dir}/watcher.log
        StandardError=append:{log_dir}/watcher_error.log

        [Install]
        WantedBy=default.target
    """)

    service_path.write_text(service_content, encoding="utf-8")
    info(f"Service file created: {service_path}")

    # Reload daemon
    subprocess.run(["systemctl", "--user", "daemon-reload"],
                   capture_output=True)

    # Enable + start (idempotent)
    result_enable = subprocess.run(
        ["systemctl", "--user", "enable", "oculus"],
        capture_output=True, text=True,
    )
    result_start = subprocess.run(
        ["systemctl", "--user", "start", "oculus"],
        capture_output=True, text=True,
    )

    if result_enable.returncode != 0:
        warn(f"systemctl enable returned: {result_enable.stderr.strip()}")
    if result_start.returncode != 0:
        warn(f"systemctl start returned: {result_start.stderr.strip()}")
        info("Try manually: systemctl --user start oculus")
    else:
        ok("systemd service enabled and started")


def _register_windows(venv_python: Path, oculus_dir: Path) -> None:
    """Create a Windows Task Scheduler task triggered on user logon."""
    import getpass
    import tempfile

    watcher_script = oculus_dir / "watcher.py"
    username = getpass.getuser()
    task_name = "OCULUS Watcher"

    xml_content = textwrap.dedent(f"""\
        <?xml version="1.0" encoding="UTF-16"?>
        <Task version="1.2"
              xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
          <RegistrationInfo>
            <Description>OCULUS — Google Meet Transcript Watcher</Description>
          </RegistrationInfo>
          <Triggers>
            <LogonTrigger>
              <Enabled>true</Enabled>
              <UserId>{username}</UserId>
            </LogonTrigger>
          </Triggers>
          <Principals>
            <Principal id="Author">
              <UserId>{username}</UserId>
              <LogonType>InteractiveToken</LogonType>
              <RunLevel>LeastPrivilege</RunLevel>
            </Principal>
          </Principals>
          <Settings>
            <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
            <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
            <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
            <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
            <Enabled>true</Enabled>
          </Settings>
          <Actions Context="Author">
            <Exec>
              <Command>{venv_python}</Command>
              <Arguments>"{watcher_script}"</Arguments>
              <WorkingDirectory>{oculus_dir}</WorkingDirectory>
            </Exec>
          </Actions>
        </Task>
    """)

    # Write XML to temp file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".xml", delete=False, encoding="utf-16"
    ) as tmp:
        tmp.write(xml_content)
        xml_path = tmp.name

    info(f"Task XML generated at: {xml_path}")

    # Delete existing task (idempotent)
    subprocess.run(
        ["schtasks", "/Delete", "/TN", task_name, "/F"],
        capture_output=True,
    )

    # Create task
    result = subprocess.run(
        ["schtasks", "/Create", "/XML", xml_path, "/TN", task_name],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        abort(
            "Failed to create task in Task Scheduler.",
            f"Error: {result.stderr}\n"
            f"Create it manually in Task Scheduler using the XML at: {xml_path}",
        )

    # Run immediately
    subprocess.run(
        ["schtasks", "/Run", "/TN", task_name],
        capture_output=True,
    )

    ok(f"Task '{task_name}' created and started in Task Scheduler")

    # Cleanup XML
    try:
        os.unlink(xml_path)
    except Exception:
        pass


def step7_register_startup(os_name: str, venv_python: Path, oculus_dir: Path) -> None:
    header("Step 7 — Register system startup service")

    if os_name == "Darwin":
        _register_macos(venv_python, oculus_dir)
    elif os_name == "Linux":
        _register_linux(venv_python, oculus_dir)
    elif os_name == "Windows":
        _register_windows(venv_python, oculus_dir)


# ---------------------------------------------------------------------------
# Step 8 — Final confirmation
# ---------------------------------------------------------------------------

def step8_done() -> None:
    print()
    print(_ansi("=" * 60, GREEN, BOLD))
    print(_ansi("  ✅  OCULUS installed successfully!", GREEN, BOLD))
    print(_ansi("=" * 60, GREEN, BOLD))
    print()
    print(_ansi("  The watcher is running in the background and will start", WHITE))
    print(_ansi("  automatically on next login.", WHITE))
    print()
    print(_ansi("  Next step: Install the TranscripTonic extension in Chrome:", CYAN, BOLD))
    print(_ansi("  https://chromewebstore.google.com/detail/transcriptonic/"
                "ciepnfnceimjehngolkijpnbappkkiag", CYAN))
    print()
    print(_ansi("  When a Google Meet meeting ends, the note will", WHITE))
    print(_ansi("  appear automatically in your Obsidian vault.", WHITE))
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print(_ansi("\n  O.C.U.L.U.S. — Cross-Platform Installer\n", BOLD, CYAN))

    # Resolve the OCULUS project directory (same folder as this script)
    oculus_dir = Path(__file__).resolve().parent

    os_name    = step1_detect_os()
    step2_check_python()
    venv_python = step3_create_venv(oculus_dir)
    step4_gemini_cli()
    step5_install_skill(os_name, oculus_dir)
    step6_configure(oculus_dir)
    step7_register_startup(os_name, venv_python, oculus_dir)
    step8_done()


if __name__ == "__main__":
    main()
