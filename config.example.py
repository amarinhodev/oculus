import os

# General Settings
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DEBUG_MODE = True

# Directories
CAPTIONS_DIR = os.path.join(PROJECT_ROOT, "Captions")
SOURCE_DIR = os.path.expanduser("~/Downloads/TranscripTonic")
ARCHIVE_DIR = os.path.join(SOURCE_DIR, "Processed")

# Identity and Language
USER_NAME = "Your Name"  # Name displayed in transcripts when it is "You"
PREFERRED_LANGUAGE = "English"  # Language for AI summaries and notes (e.g., English, Brazilian Portuguese, Spanish)

# Transcript prefix — used by both watcher.py and processor.py
TRANSCRIPT_PREFIX = "Google Meet transcript"

# Logs
LOG_FILE = os.path.join(PROJECT_ROOT, "watcher.log")          # Main rotating log (watcher + analysis)
LOG_ANALYSIS = os.path.join(PROJECT_ROOT, "analysis.log")
LOG_ANALYSIS_ERROR = os.path.join(PROJECT_ROOT, "analysis_error.log")
LOG_WATCHER = os.path.join(PROJECT_ROOT, "watcher.log")       # Legacy alias — same as LOG_FILE
LOG_WATCHER_ERROR = os.path.join(PROJECT_ROOT, "watcher_error.log")

# Scripts and Binaries
PROCESSOR_SCRIPT = os.path.join(PROJECT_ROOT, "processor.py")
# Try to find python in venv, otherwise use default
PYTHON_BIN = os.path.join(PROJECT_ROOT, ".venv", "bin", "python3")
if not os.path.exists(PYTHON_BIN):
    PYTHON_BIN = "python3"

# Create required directories if they don't exist
for directory in [CAPTIONS_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)
