# O.C.U.L.U.S.
**Omniscient Captions Universal Logging & Understanding System**

Automatically turns your Google Meet transcripts into structured, AI-analyzed notes in your Obsidian vault.

![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue) ![Cross-platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey) ![Gemini CLI](https://img.shields.io/badge/AI-Gemini%20CLI-orange) ![Obsidian](https://img.shields.io/badge/notes-Obsidian-purple)

---

## How it works

```
Google Meet → TranscripTonic → watcher.py → processor.py → Gemini CLI (V9.2) → Obsidian vault
```

| Step | What happens |
|------|-------------|
| **Google Meet** | You have your meeting normally |
| **TranscripTonic** | Chrome extension captures captions and saves a `.txt` to your Downloads |
| **watcher.py** | Real-time file monitor (watchdog) detects the new transcript instantly |
| **processor.py** | Converts raw `.txt` into structured Markdown, organized by speaker and timestamp |
| **Gemini CLI (V9.2)** | AI skill queries your Obsidian vault via RAG, then generates the final note |
| **Obsidian vault** | Structured `.md` note lands in your Meetings folder + daily log updated |

---

## Prerequisites *(manual steps — only these two)*

1. Install [TranscripTonic](https://chromewebstore.google.com/detail/transcriptonic/ciepnfnceimjehngolkijpnbappkkiag) Chrome extension — enable **Auto Mode**
2. Have **Python 3.11+** installed

Everything else is handled automatically by the installer.

---

## Installation

```bash
git clone https://github.com/amarinhodev/oculus
cd oculus
python install.py
```

That's it. OCULUS will run automatically every time you log in.

**What `install.py` does behind the scenes:**
- Creates a Python virtual environment
- Installs dependencies (`watchdog`, etc.)
- Installs Gemini CLI if not present
- Installs the `oculus-analyzer` skill (V9.2) into Gemini
- Walks you through minimal config (name, vault path, language)
- Registers the watcher as a background service (macOS LaunchAgent / Linux systemd / Windows Task Scheduler)

---

## Configuration

`install.py` creates `config.py` from `config.example.py` during setup. You can edit it at any time.

| Setting | Description | Example |
|---------|-------------|---------|
| `USER_NAME` | Your name as it appears in transcripts | `"John Smith"` |
| `PREFERRED_LANGUAGE` | Language for AI-generated notes | `"English"`, `"Brazilian Portuguese"`, `"Spanish"` |
| `OBSIDIAN_VAULT` | Path to your Obsidian vault | `"~/Documents/MyVault"` |

---

## What gets generated

After each meeting, a structured note appears in your Obsidian vault:

- **Structured `.md` note** in your `Meetings/` folder
- **YAML frontmatter:** title, date, participants, meeting type
- **Executive summary** — key topics covered
- **Decisions** — what was decided
- **Action items** — who does what, by when
- **Insights** — patterns and observations from the conversation
- **WikiLinks** to related projects, people, and tools discovered in your vault
- **Entry in the daily log** (`daily/YYYY-MM-DD.md`)

---

## Project structure

```
oculus/
├── watcher.py              # Real-time file monitor (watchdog) + AI trigger
├── processor.py            # TranscripTonic → structured Markdown converter
├── install.py              # Cross-platform installer (macOS/Linux/Windows)
├── uninstall.py            # Clean uninstaller
├── config.example.py       # Configuration template
├── requirements.txt        # Python dependencies
├── skills/
│   └── oculus-analyzer/
│       └── SKILL.md        # Gemini CLI skill (V9.2 — RAG-native)
└── tests/
    └── test_processor.py   # Automated test suite (22 tests)
```

---

## Uninstall

```bash
python uninstall.py
```

Removes the background service, virtual environment, and optionally the config file. Your Obsidian notes are never deleted.

---

## How the AI analysis works

The `oculus-analyzer` skill (V9.2) is RAG-native — it reads your vault before writing anything:

- **Before analyzing your transcript**, the AI queries your Obsidian vault to discover your projects, people, and tools
- **Queries are executed in your `PREFERRED_LANGUAGE`** for maximum accuracy
- **Links mentioned topics** to existing notes in your vault automatically
- **No hardcoded knowledge** — works for any user, any vault structure

---

## Multilingual support

OCULUS itself is in English, but the notes it generates follow your `PREFERRED_LANGUAGE` setting.

Supported: any language Gemini CLI supports (English, Brazilian Portuguese, Spanish, French, German, and more).

---

## License / Contributing

MIT License. Contributions welcome — open an issue or submit a PR.
