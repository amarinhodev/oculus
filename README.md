# 👁️ O.C.U.L.U.S.
**Omniscient Captions Universal Logging & Understanding System**

> Turn raw Google Meet live captions into structured, executive-ready **Obsidian** meeting notes automatically — 100% locally orchestrated via **Antigravity CLI (`agy`)** or **Gemini CLI**.

![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey)
![AI Engine](https://img.shields.io/badge/AI-Antigravity%20(agy)%20%7C%20Gemini%20CLI-orange)
![Obsidian](https://img.shields.io/badge/notes-Obsidian%20Vault-purple)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)

---

## ⚡ Why O.C.U.L.U.S.?

Most AI meeting recorders require inviting an intrusive bot (`"Otter.ai joined the meeting"`) or uploading corporate audio to third-party SaaS clouds.

**O.C.U.L.U.S.** takes a zero-bot, local-first approach:
1. **No meeting bots:** Uses [TranscripTonic](https://chromewebstore.google.com/detail/transcriptonic/ciepnfnceimjehngolkijpnbappkkiag) to passively capture Google Meet closed captions in your browser and save a plain `.txt` transcript locally.
2. **Instant filesystem detection:** `watcher.py` (`watchdog` FSEvents/inotify) detects new transcripts the second your call ends.
3. **Smart Markdown & Date Disambiguation (V10.0):** `processor.py` merges incremental caption fragments, normalizes speaker aliases (`You` / `Você` → your name), and automatically disambiguates `DD-MM-YYYY` vs `MM-DD-YYYY` filenames using file modification metadata (`mtime`).
4. **Empty-Call Protection:** Automatically skips aborted or empty meeting rooms (`< 1` dialogue turn) so your Vault stays noise-free.
5. **Vault-Aware AI Synthesis (V10.0):** Invokes the `oculus-analyzer` skill via `agy` or `gemini` to discover existing projects in your Obsidian Vault (`[[Wikilinks]]`), extract decisions and action items, write the structured meeting note, and append a 1-line summary to your Daily Note (`daily/YYYY-MM-DD.md`).

---

## 🏗️ Architecture & Pipeline

```text
Google Meet (Captions ON)
   └──► TranscripTonic (.txt in ~/Downloads/TranscripTonic)
           └──► watcher.py (Watchdog FSEvents + Empty-Call Guard + Retry Queue)
                   └──► processor.py (Fragment Merger + mtime Date Disambiguator)
                           └──► Captions/YYYY-MM-DD_HH-MM_<Title>.md
                                   └──► Antigravity CLI (agy) / Gemini CLI + oculus-analyzer (V10.0)
                                           ├──► Vault/Meetings/YYYY-MM-DD_HH-MM_<Title>.md
                                           └──► Vault/daily/YYYY-MM-DD.md (Append-only)
```

---

## 🚀 Quickstart

### Prerequisites
1. Install the [TranscripTonic](https://chromewebstore.google.com/detail/transcriptonic/ciepnfnceimjehngolkijpnbappkkiag) Chrome extension and enable **Auto Mode**.
2. **Python 3.11+** and either **Antigravity CLI (`agy`)** or **Gemini CLI (`gemini`)** installed.

### One-Command Installation

```bash
git clone https://github.com/amarinhodev/oculus.git
cd oculus
python3 install.py
```

**What `install.py` configures automatically:**
- Installs Python dependencies (`requirements.txt`).
- Detects `agy` (Antigravity CLI) or `gemini` CLI in your `PATH`.
- Installs the `oculus-analyzer` skill into `~/.gemini/skills/oculus-analyzer/`.
- Generates your local `config.py` (git-ignored) from `config.example.py`.
- Scaffolds `Meetings/`, `daily/`, and `_Templates/` in your Obsidian Vault if missing.
- Registers `com.oculus.watcher` as a native background LaunchAgent on macOS.

---

## ⚙️ Configuration (`config.py`)

`config.py` is git-ignored so your personal paths and vault taxonomy never leak into version control.

| Setting | Description | Default / Example |
|---------|-------------|-------------------|
| `USER_NAME` | Your full name (replaces `"You"` / `"Você"` in transcripts) | `"Jane Doe"` |
| `LOCAL_USER_ALIASES` | Labels used by Google Meet for the local speaker | `["You", "Você"]` |
| `PREFERRED_LANGUAGE` | Output language for AI executive summaries and notes | `"English"`, `"Brazilian Portuguese"` |
| `VAULT_PATH` | Absolute path to your Obsidian Vault | `"~/Documents/ObsidianVault"` |
| `MEETINGS_PATH` | Target directory for generated meeting notes | `os.path.join(VAULT_PATH, "Meetings")` |
| `DAILY_PATH` | Target directory for daily notes (`YYYY-MM-DD.md`) | `os.path.join(VAULT_PATH, "daily")` |
| `AGY_BIN` | Path to `agy` or `gemini` executable | `"agy"` |
| `CUSTOM_PROMPT_INSTRUCTIONS` | Optional vault-specific frontmatter or closed-tag rules | `""` |

> **Advanced Vault Customization (`LOCAL_CONTEXT.md`):**
> Need custom tag taxonomies, specific MOC paths, or local issue-tracker CLI enrichment (such as Jira)? Create a git-ignored `skills/oculus-analyzer/LOCAL_CONTEXT.md` file — `SKILL.md` automatically loads it as an authoritative override without touching tracked files.

---

## 📂 Project Structure

```text
oculus/
├── watcher.py                      # Real-time file monitor (watchdog), retry queue & CLI runner
├── processor.py                    # TranscripTonic .txt → structured Markdown + YAML converter
├── install.py                      # Cross-platform native installer & LaunchAgent setup
├── uninstall.py                    # Clean uninstaller (preserves your Obsidian notes)
├── config.example.py               # Public configuration template
├── requirements.txt                # Python dependencies
├── skills/
│   └── oculus-analyzer/
│       └── SKILL.md                # V10.0 AI skill (RAG + deterministic MOC discovery)
└── tests/
    └── test_processor.py           # Automated pytest suite (24 unit tests)
```

---

## 🧪 Running Tests

All unit tests run in complete isolation using a mocked `config` module and temporary fixtures:

```bash
pytest tests/ -v
```

---

## 🧹 Uninstall

```bash
python3 uninstall.py
```

Stops and removes the background service, cleans up the skill installation, and optionally removes `config.py`. Your Obsidian vault notes are never modified or deleted.

---

## 📄 License

Released under the [MIT License](./LICENSE). Contributions, issues, and feature requests are welcome.
