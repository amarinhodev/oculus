"""
O.C.U.L.U.S. Watcher — File system monitor for Google Meet transcripts.

Uses watchdog for cross-platform filesystem events (inotify on Linux,
FSEvents on macOS, ReadDirectoryChangesW on Windows).
Migrated from discontinued Gemini CLI (`gemini`) to Antigravity CLI (`agy`).
"""

import base64
import json
import logging
import logging.handlers
import os
import re
import shutil
import subprocess
import threading
import time
from datetime import datetime

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

import config

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def _setup_logging() -> logging.Logger:
    """Configure structured logging with RotatingFileHandler + console."""
    logger = logging.getLogger("oculus.watcher")
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.handlers.RotatingFileHandler(
        config.LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(fmt)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


logger = _setup_logging()

# ---------------------------------------------------------------------------
# In-memory & persistent state for analyzed files
# ---------------------------------------------------------------------------

_pending_analysis: list[str] = []
_batch_lock = threading.Lock()
_last_auth_error: bool = False


def _ensure_agy_keychain_onboarding() -> None:
    """
    Self-healing guard for Antigravity CLI (`agy` v1.5.9+) Keychain StoredToken.

    In `agy` v1.5.9+, `keyringAuth.TryAuth` (`keyring.go:51`) treats a `gcp` token
    as unauthenticated if both `project_id` and `user_tier` are empty in the
    `go-keyring-base64:` JSON stored in macOS Keychain (`svce="gemini"`, `acct="antigravity"`),
    which triggers an interactive browser OAuth flow in print mode.
    Older `agy` v1.5.8 processes in memory overwrite the Keychain entry without
    `project_id`/`region` when refreshing the OAuth token hourly.
    This guard restores `project_id` and `region` before every headless invocation.
    """
    try:
        raw = subprocess.check_output(
            ["security", "find-generic-password", "-s", "gemini", "-a", "antigravity", "-w"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).strip()
        if not raw.startswith("go-keyring-base64:"):
            return
        b64 = raw.split("go-keyring-base64:", 1)[1]
        data = json.loads(base64.b64decode(b64).decode("utf-8"))
        if data.get("auth_method") != "gcp":
            return

        # Read canonical project/location from config or ~/.gemini/antigravity-cli/settings.json
        project_id = getattr(config, "GCP_PROJECT", "")
        region = getattr(config, "GCP_LOCATION", "global")
        settings_path = os.path.expanduser("~/.gemini/antigravity-cli/settings.json")
        if os.path.exists(settings_path):
            try:
                with open(settings_path, "r", encoding="utf-8") as sf:
                    sdata = json.load(sf)
                    gcp_cfg = sdata.get("gcp") or {}
                    project_id = gcp_cfg.get("project") or project_id
                    region = gcp_cfg.get("location") or region
            except Exception:
                pass

        if not project_id:
            return

        changed = False
        if data.get("project_id") != project_id:
            data["project_id"] = project_id
            changed = True
        if data.get("region") != region:
            data["region"] = region
            changed = True
        if data.get("user_tier") == "enterprise":
            # "enterprise" is not a valid enum for cloudcode-pa fetchAvailableModels
            data.pop("user_tier", None)
            changed = True

        if changed:
            new_raw = "go-keyring-base64:" + base64.b64encode(
                json.dumps(data, separators=(",", ":")).encode("utf-8")
            ).decode("utf-8")
            subprocess.run(
                ["security", "add-generic-password", "-U", "-s", "gemini", "-a", "antigravity", "-w", new_raw],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
            logger.info(
                "🔐 Healed AGY Keychain StoredToken onboarding metadata (project_id=%s, region=%s).",
                project_id,
                region,
            )
    except Exception as exc:
        logger.debug("Keychain onboarding check skipped: %s", exc)


def _load_analyzed_state() -> set[str]:
    """Load set of caption filenames already processed or skipped."""
    state_file = getattr(config, "STATE_FILE", os.path.join(config.PROJECT_ROOT, ".analyzed_captions.json"))
    if os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                if isinstance(data, dict):
                    return set(data.get("analyzed", []))
                return set(data)
        except Exception:
            pass
    return set()


def _mark_analyzed(caption_filename: str) -> None:
    """Persist caption filename as analyzed."""
    state_file = getattr(config, "STATE_FILE", os.path.join(config.PROJECT_ROOT, ".analyzed_captions.json"))
    analyzed = _load_analyzed_state()
    analyzed.add(caption_filename)
    try:
        with open(state_file, "w", encoding="utf-8") as fh:
            json.dump(sorted(analyzed), fh, indent=2, ensure_ascii=False)
    except Exception as exc:
        logger.warning("Could not save analyzed state: %s", exc)


def is_already_analyzed(md_path: str) -> bool:
    """Check if a caption `.md` already has a corresponding meeting note in Vault or state."""
    base = os.path.basename(md_path)
    if base in _load_analyzed_state():
        return True

    meetings_dir = getattr(
        config,
        "MEETINGS_PATH",
        os.path.join(config.VAULT_PATH, "Meetings"),
    )
    if not os.path.exists(meetings_dir):
        return False

    # Match by exact filename or by YYYY-MM-DD_HH-MM prefix
    m = re.match(r"^(\d{4}-\d{2}-\d{2}_\d{2}-\d{2})_", base)
    prefix = m.group(1) if m else base.replace(".md", "")
    for existing in os.listdir(meetings_dir):
        if existing == base or (m and existing.startswith(prefix)):
            _mark_analyzed(base)
            return True
    return False


def has_meaningful_dialogue(md_path: str) -> bool:
    """Return False if the caption file has no real dialogue turns (e.g. empty/aborted room)."""
    try:
        with open(md_path, "r", encoding="utf-8") as fh:
            content = fh.read()
        turns = re.findall(r"^\*\*\[.*?\] .*?:\*\* .+", content, flags=re.M)
        if len(turns) == 0 and len(content.strip()) < 650:
            return False
        return True
    except Exception:
        return True


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def get_files(directory: str) -> set:
    """Return the set of transcript .txt files in *directory*."""
    try:
        if not os.path.exists(directory):
            return set()
        return {
            f
            for f in os.listdir(directory)
            if f.startswith(config.TRANSCRIPT_PREFIX) and f.endswith(".txt")
        }
    except Exception as exc:
        logger.error("Error listing directory '%s': %s", directory, exc)
        return set()


def _resolve_agy_bin() -> str:
    """Resolve the path to `agy` CLI."""
    configured = getattr(config, "AGY_BIN", getattr(config, "GEMINI_BIN", "agy"))
    first_token = configured.split()[0]
    if os.path.exists(first_token) and "gemini" not in os.path.basename(first_token):
        return first_token
    found = shutil.which("agy")
    if found:
        return found
    fallback = os.path.expanduser("~/.local/bin/agy")
    return fallback if os.path.exists(fallback) else first_token


def analyze_file(md_path: str) -> bool:
    """
    Trigger Antigravity CLI (`agy`) analysis for *md_path*.

    Returns True on successful note generation, False otherwise.
    """
    base = os.path.basename(md_path)
    if is_already_analyzed(md_path):
        logger.debug("Skipping '%s' — already analyzed.", base)
        return True

    if not has_meaningful_dialogue(md_path):
        logger.info("⏭️ Skipping '%s' — empty/aborted meeting transcript (<1 dialogue turn).", base)
        _mark_analyzed(base)
        return True

    meetings_dir = getattr(
        config,
        "MEETINGS_PATH",
        os.path.join(config.VAULT_PATH, "Meetings"),
    )
    expected_out = os.path.join(meetings_dir, base)

    logger.info("🚀 Triggering AGY (Antigravity) analysis for: %s", md_path)
    skill_path = getattr(
        config,
        "SKILL_PATH",
        os.path.join(config.PROJECT_ROOT, "skills", "oculus-analyzer", "SKILL.md"),
    )
    custom_instructions = getattr(config, "CUSTOM_PROMPT_INSTRUCTIONS", "").strip()
    extra_rules = f"{custom_instructions} " if custom_instructions else ""

    prompt = (
        f"Analyze the meeting transcription at '{md_path}' using the oculus-analyzer skill "
        f"({skill_path}). "
        f"CRITICAL: Write the structured meeting note in {config.PREFERRED_LANGUAGE} to '{expected_out}' "
        f"(or with the same YYYY-MM-DD_HH-MM_ prefix in '{meetings_dir}') and append the entry under "
        f"'## 🗓️ Meetings' in '{config.DAILY_PATH}' for the meeting's date. "
        f"{extra_rules}"
        "DO NOT ASK QUESTIONS. EXECUTE IMMEDIATELY."
    )

    agy_bin = _resolve_agy_bin()
    _ensure_agy_keychain_onboarding()

    settings_dict: dict = {
        "toolPermission": "always-proceed",
        "allowNonWorkspaceAccess": True,
        "permissions": {
            "allow": [
                "write_file(*)",
                "edit_file(*)",
                "read_file(*)",
                "list_dir(*)",
                "find_by_name(*)",
                "grep_search(*)",
                "command(*)",
                "mcp(gemini-obsidian/*)",
            ]
        },
    }
    gcp_project = getattr(config, "GCP_PROJECT", "")
    if gcp_project:
        settings_dict["gcp"] = {
            "project": gcp_project,
            "location": getattr(config, "GCP_LOCATION", "global"),
        }
    headless_settings = json.dumps(settings_dict)
    cmd = [
        agy_bin,
        "--dangerously-skip-permissions",
        "--settings",
        headless_settings,
        "--add-dir",
        config.VAULT_PATH,
        "--add-dir",
        config.PROJECT_ROOT,
        "-p",
        prompt,
    ]

    logger.debug("Executing command: %s", " ".join(cmd))

    global _last_auth_error
    _last_auth_error = False

    # Prepend headless browser guard directory (.bin/open) so AGY can never
    # pop open interactive Google OAuth browser tabs in background mode.
    env = os.environ.copy()
    guard_bin = os.path.join(config.PROJECT_ROOT, ".bin")
    if os.path.isdir(guard_bin):
        env["PATH"] = f"{guard_bin}:{env.get('PATH', '')}"
    env["BROWSER"] = "/usr/bin/true"

    try:
        result = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
        )

        if is_already_analyzed(md_path):
            logger.info("✅ AGY analysis completed and verified in Vault for: %s", base)
            _mark_analyzed(base)
            return True
        elif result.returncode == 0 and "---" in (result.stdout or "") and "#" in (result.stdout or ""):
            # Fallback: if AGY returned the markdown note in stdout instead of calling write_file
            out_text = result.stdout.strip()
            idx = out_text.find("---")
            if idx >= 0:
                out_text = out_text[idx:]
            os.makedirs(meetings_dir, exist_ok=True)
            with open(expected_out, "w", encoding="utf-8") as fh:
                fh.write(out_text + "\n")
            logger.info("✅ AGY stdout captured and saved to Vault for: %s", base)
            _mark_analyzed(base)
            return True
        else:
            stderr_text = (result.stderr or "").strip()
            stdout_text = (result.stdout or "").strip()
            if "Authentication required" in stderr_text or "Authentication required" in stdout_text:
                _last_auth_error = True
            logger.error(
                "❌ AGY analysis did not produce Vault note (code=%s) for '%s'. stdout=%s | stderr=%s",
                result.returncode,
                base,
                stdout_text[:300],
                stderr_text[:300],
            )
            if md_path not in _pending_analysis:
                _pending_analysis.append(md_path)
            return False

    except Exception as exc:
        logger.error("Failed to launch AGY for '%s': %s", md_path, exc)
        if md_path not in _pending_analysis:
            _pending_analysis.append(md_path)
        return False


def analyze_file_with_retry(md_path: str, max_retries: int = 3) -> bool:
    """
    Attempt to trigger AGY analysis with exponential backoff retry.

    Waits 5s → 15s → 30s between attempts. Stops immediately on auth error
    to avoid repetitive authentication attempts.
    """
    if is_already_analyzed(md_path):
        return True

    delays = [5, 15, 30]
    for attempt in range(1, max_retries + 1):
        logger.info("Analysis attempt %d/%d for: %s", attempt, max_retries, md_path)
        if analyze_file(md_path):
            return True
        if _last_auth_error:
            logger.error(
                "Aborting remaining retries for '%s' due to authentication requirement (queued for later).",
                md_path,
            )
            break
        if attempt < max_retries:
            wait = delays[attempt - 1]
            logger.warning("Analysis failed (attempt %d). Retrying in %ds…", attempt, wait)
            time.sleep(wait)

    logger.error(
        "Analysis attempts exhausted for '%s'. Added to pending queue.",
        md_path,
    )
    return False


def run_batch_process() -> None:
    """
    Process all pending TXT files in SOURCE_DIR and trigger AGY analysis
    for unanalyzed Markdown files in CAPTIONS_DIR from today.
    Uses a non-blocking lock so duplicate FSEvents do not stack concurrent runs.
    """
    if not _batch_lock.acquire(blocking=False):
        logger.debug("Batch process already running — skipping duplicate FSEvent trigger.")
        return

    try:
        txt_files = get_files(config.SOURCE_DIR)
        if txt_files:
            logger.info("Processing batch of %d file(s)…", len(txt_files))
            result = subprocess.run(
                [config.PYTHON_BIN, config.PROCESSOR_SCRIPT],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                logger.warning(
                    "Processor exited with code %d. stderr: %s",
                    result.returncode,
                    result.stderr.strip(),
                )
            else:
                logger.info("Processor completed successfully.")
        else:
            logger.debug("No pending transcript files found in SOURCE_DIR.")

        today_str = datetime.now().strftime("%Y-%m-%d")
        try:
            md_files = sorted(f for f in os.listdir(config.CAPTIONS_DIR) if f.endswith(".md"))
        except Exception as exc:
            logger.error("Cannot list CAPTIONS_DIR: %s", exc)
            return

        for md in md_files:
            if md.startswith(today_str):
                md_path = os.path.join(config.CAPTIONS_DIR, md)
                if not is_already_analyzed(md_path):
                    analyze_file_with_retry(md_path)

        _retry_pending_analysis()

    except Exception as exc:
        logger.error("Unexpected error in run_batch_process: %s", exc, exc_info=True)
    finally:
        _batch_lock.release()


def _retry_pending_analysis() -> None:
    """Attempt to re-analyse files queued when AGY was unavailable."""
    if not _pending_analysis:
        return

    agy_bin = _resolve_agy_bin()
    if not (os.path.exists(agy_bin) or shutil.which(agy_bin)):
        logger.warning(
            "%d file(s) still pending analysis — AGY CLI not found at %s.",
            len(_pending_analysis),
            agy_bin,
        )
        return

    logger.info("Retrying analysis for %d queued file(s)…", len(_pending_analysis))
    still_pending = []
    for md_path in list(_pending_analysis):
        if not analyze_file(md_path):
            still_pending.append(md_path)
    _pending_analysis.clear()
    _pending_analysis.extend(still_pending)


# ---------------------------------------------------------------------------
# Watchdog event handler
# ---------------------------------------------------------------------------

class TranscriptHandler(FileSystemEventHandler):
    """React to new transcript files appearing in SOURCE_DIR."""

    def on_created(self, event):
        if event.is_directory:
            return
        filename = os.path.basename(event.src_path)
        if filename.startswith(config.TRANSCRIPT_PREFIX) and filename.endswith(".txt"):
            logger.info(
                "[%s] New transcript detected: %s",
                datetime.now().strftime("%H:%M:%S"),
                filename,
            )
            run_batch_process()


# ---------------------------------------------------------------------------
# Main watcher entrypoint
# ---------------------------------------------------------------------------

def run_watcher() -> None:
    """Start the OCULUS watcher using watchdog Observer."""
    logger.info(
        "👁️  O.C.U.L.U.S. Watcher Active (Engine: AGY -> %s). Monitoring: %s",
        _resolve_agy_bin(),
        config.SOURCE_DIR,
    )

    run_batch_process()

    event_handler = TranscriptHandler()
    observer = Observer()
    observer.schedule(event_handler, config.SOURCE_DIR, recursive=False)
    observer.start()
    logger.info("Watchdog observer started (path: %s).", config.SOURCE_DIR)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutdown signal received. Stopping observer…")
    except Exception as exc:
        logger.error("Unexpected error in watcher loop: %s", exc, exc_info=True)
    finally:
        observer.stop()
        observer.join()
        logger.info("O.C.U.L.U.S. Watcher stopped.")


if __name__ == "__main__":
    if not os.path.exists(config.SOURCE_DIR):
        os.makedirs(config.SOURCE_DIR)
    run_watcher()
