import os

# General Settings
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DEBUG_MODE = True

# Directories
CAPTIONS_DIR = os.path.join(PROJECT_ROOT, "Captions")
SOURCE_DIR = os.path.expanduser("~/Downloads/TranscripTonic")
ARCHIVE_DIR = os.path.join(SOURCE_DIR, "Processed")
VAULT_PATH = os.path.expanduser("~/Documents/ObsidianVault")
DAILY_PATH = os.path.join(VAULT_PATH, "daily")
MEETINGS_PATH = os.path.join(VAULT_PATH, "Meetings")
TEMPLATE_DAILY = os.path.join(VAULT_PATH, "_Templates", "Daily_Template.md")
STATE_FILE = os.path.join(PROJECT_ROOT, ".analyzed_captions.json")

# Identity and Language
USER_NAME = "Your Name"  # Name displayed in transcripts when it is "You"
PREFERRED_LANGUAGE = "English"  # Language for AI summaries and notes (e.g., English, Brazilian Portuguese, Spanish)

# Aliases used by TranscripTonic for the local user in different languages.
# Add the alias for your language if not listed.
# Common values: "You" (EN), "Você" (PT-BR), "Vous" (FR), "Usted" (ES), "Sie" (DE), "Lei" (IT)
LOCAL_USER_ALIASES = ["You", "Você"]

# Transcript prefix — used by both watcher.py and processor.py
TRANSCRIPT_PREFIX = "Google Meet transcript"

# Logs
LOG_FILE = os.path.join(PROJECT_ROOT, "watcher.log")          # Main rotating log (watcher + analysis)
LOG_ANALYSIS = os.path.join(PROJECT_ROOT, "analysis.log")
LOG_ANALYSIS_ERROR = os.path.join(PROJECT_ROOT, "analysis_error.log")
LOG_WATCHER = os.path.join(PROJECT_ROOT, "watcher.log")       # Legacy alias — same as LOG_FILE
LOG_WATCHER_ERROR = os.path.join(PROJECT_ROOT, "watcher_error.log")

# Scripts, Skills, and Optional Cloud Settings
AGY_BIN = "agy"       # Path or command for Antigravity CLI (`agy`) or Gemini CLI (`gemini`)
GEMINI_BIN = AGY_BIN  # Backward-compatibility alias
SKILL_PATH = os.path.join(PROJECT_ROOT, "skills", "oculus-analyzer", "SKILL.md")
GCP_PROJECT = ""      # Optional: GCP project ID when using Vertex AI / Enterprise auth
GCP_LOCATION = "global"
CUSTOM_PROMPT_INSTRUCTIONS = ""  # Optional: Vault-specific frontmatter or tag contract instructions
PROCESSOR_SCRIPT = os.path.join(PROJECT_ROOT, "processor.py")

# Try to find python in venv, otherwise use default
PYTHON_BIN = os.path.join(PROJECT_ROOT, ".venv", "bin", "python3")
if not os.path.exists(PYTHON_BIN):
    PYTHON_BIN = "python3"

# Create required directories if they don't exist
for directory in [CAPTIONS_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
