"""
O.C.U.L.U.S. Watcher — File system monitor for Google Meet transcripts.

Uses watchdog for cross-platform filesystem events (inotify on Linux,
FSEvents on macOS, ReadDirectoryChangesW on Windows).
"""

import logging
import logging.handlers
import os
import shutil
import subprocess
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

    # Rotating file handler — max 5 MB, keep 3 backups
    file_handler = logging.handlers.RotatingFileHandler(
        config.LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)

    # Console handler — INFO+
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(fmt)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


logger = _setup_logging()

# ---------------------------------------------------------------------------
# In-memory queue for files pending Gemini analysis
# ---------------------------------------------------------------------------

_pending_analysis: list[str] = []

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


def analyze_file(md_path: str) -> bool:
    """
    Trigger Gemini CLI analysis for *md_path*.

    Returns True on successful launch, False otherwise.
    """
    if not shutil.which("gemini"):
        logger.warning(
            "Gemini CLI not found in PATH. Analysis will be skipped until installed. "
            "File queued for later: %s",
            md_path,
        )
        if md_path not in _pending_analysis:
            _pending_analysis.append(md_path)
        return False

    logger.info("Triggering Gemini analysis for: %s", md_path)
    prompt = (
        f"Analyze the transcription {md_path} using the oculus-analyzer skill. "
        f"CRITICAL: Generate all output (summaries, tasks, notes) in {config.PREFERRED_LANGUAGE}. "
        "Identify contexts via RAG, extract tasks and decisions, "
        "and organize results according to the skill workflow. "
        "DO NOT ASK QUESTIONS, EXECUTE IMMEDIATELY."
    )
    cmd = ["gemini", "-y", "-p", prompt]
    try:
        subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=open(config.LOG_ANALYSIS, "a"),
            stderr=open(config.LOG_ANALYSIS_ERROR, "a"),
        )
        return True
    except Exception as exc:
        logger.error("Failed to launch Gemini for '%s': %s", md_path, exc)
        if md_path not in _pending_analysis:
            _pending_analysis.append(md_path)
        return False


def analyze_file_with_retry(md_path: str, max_retries: int = 3) -> bool:
    """
    Attempt to trigger Gemini analysis with exponential backoff retry.

    Waits 5s → 15s → 30s between attempts.
    Returns True if analysis launched successfully, False if all retries exhausted.
    """
    delays = [5, 15, 30]
    for attempt in range(1, max_retries + 1):
        logger.info("Analysis attempt %d/%d for: %s", attempt, max_retries, md_path)
        if analyze_file(md_path):
            return True
        if attempt < max_retries:
            wait = delays[attempt - 1]
            logger.warning(
                "Analysis failed (attempt %d). Retrying in %ds…", attempt, wait
            )
            time.sleep(wait)

    logger.error(
        "All %d analysis attempts failed for '%s'. "
        "File added to pending queue for manual reprocessing.",
        max_retries,
        md_path,
    )
    return False


def run_batch_process() -> None:
    """
    Process all pending TXT files in SOURCE_DIR.

    Converts them to Markdown via processor.py then triggers Gemini analysis.
    """
    try:
        txt_files = get_files(config.SOURCE_DIR)
        if not txt_files:
            logger.info("No pending transcript files found in SOURCE_DIR.")
            return

        logger.info("Processing batch of %d file(s)…", len(txt_files))

        # Convert TXT → MD via processor
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

        # Trigger Gemini analysis for today's new MD files
        today_str = datetime.now().strftime("%Y-%m-%d")
        try:
            md_files = [f for f in os.listdir(config.CAPTIONS_DIR) if f.endswith(".md")]
        except Exception as exc:
            logger.error("Cannot list CAPTIONS_DIR: %s", exc)
            return

        for md in md_files:
            if md.startswith(today_str):
                md_path = os.path.join(config.CAPTIONS_DIR, md)
                analyze_file_with_retry(md_path)

        # Retry previously queued pending files (gemini may now be available)
        _retry_pending_analysis()

    except Exception as exc:
        logger.error("Unexpected error in run_batch_process: %s", exc, exc_info=True)


def _retry_pending_analysis() -> None:
    """Attempt to re-analyse files queued when Gemini was unavailable."""
    if not _pending_analysis:
        return

    if not shutil.which("gemini"):
        logger.warning(
            "%d file(s) still pending analysis — Gemini CLI not yet available.",
            len(_pending_analysis),
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

    # Warn if Gemini is absent — but keep running
    if not shutil.which("gemini"):
        logger.warning(
            "Gemini CLI not found in PATH. "
            "Analysis will be skipped until installed."
        )

    logger.info("👁️  O.C.U.L.U.S. Watcher Active. Monitoring: %s", config.SOURCE_DIR)

    # Process any files already waiting
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
