# O.C.U.L.U.S. (Google Meet Transcriber)

## 1. Overview
**O.C.U.L.U.S.** stands for **O**mniscient **C**aptions **U**niversal **L**ogging & **U**nderstanding **S**ystem.

It provides automated capture and processing of Google Meet transcriptions using the TranscripTonic extension and Python-based automation.

**Key Technologies:**
- Python 3.11+
- [TranscripTonic](https://chromewebstore.google.com/detail/transcriptonic/ciepnfnceimjehngolkijpnbappkkiag) Extension
- [Gemini CLI](https://github.com/google/gemini-cli) (AI Engine & Automation)
- [Obsidian](https://obsidian.md/) (Note organization and visualization)

## 2. Workflow
1. **Capture:** The [TranscripTonic](https://chromewebstore.google.com/detail/transcriptonic/ciepnfnceimjehngolkijpnbappkkiag) extension captures Google Meet captions and chat in real-time.
2. **Export:** Upon ending the meeting, the extension automatically saves the transcript as a `.txt` file in your Downloads folder.
3. **Monitoring:** The `watcher.py` service instantly detects the new file.
4. **Processing:** The `processor.py` script converts the raw `.txt` into organized Markdown (.md), categorized by speaker and timestamp.
5. **Intelligence:** The system optionally triggers AI analysis to extract tasks, decisions, and insights via Gemini CLI.

## 3. Project Structure
```text
/
├── processor.py        # Specialized processor for TranscripTonic files.
├── watcher.py          # File monitor and AI automation trigger.
├── config.py           # Centralized configuration and paths.
├── requirements.txt    # Python dependencies.
├── .gitignore          # Sensitive data protection.
├── README.md           # This documentation.
└── Captions/           # Local destination for Markdown transcripts.
```

## 4. Setup and Installation

### 4.1. Data Source (Browser)
1. Install the [TranscripTonic](https://chromewebstore.google.com/detail/transcriptonic/ciepnfnceimjehngolkijpnbappkkiag) extension.
2. Enable "Auto Mode" in the extension to automatically save transcripts at the end of meetings.

### 4.2. AI Engine (Gemini CLI)
1. Install **Gemini CLI** (follow official repository instructions).
2. Install the Obsidian integration extension:
   ```bash
   gemini extensions install https://github.com/thoreinstein/gemini-obsidian
   ```
3. Set your Obsidian vault path in Gemini CLI:
   ```bash
   gemini obsidian set-vault /path/to/your/vault
   ```

### 4.3. Python Environment
1. Create and activate a virtual environment (recommended):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
2. Create your local config from the example: `cp config.example.py config.py`.
3. Edit `config.py` with your download directories, username, and **preferred language** for AI notes.
4. Install dependencies: `pip install -r requirements.txt`

### 4.4. Running the Automation
Start the watcher to automatically process and analyze downloaded files:
```bash
python3 watcher.py
```

## 5. How Automation Works
The `watcher.py` service uses the `gemini` CLI to trigger intelligent analysis. The project includes a skill definition in `/skills/oculus-analyzer`.

### 5.1. Installing the Skill
Register the skill in your Gemini environment:
```bash
gemini skill add ./skills/oculus-analyzer
```

### 5.2. Skill Features
The `oculus-analyzer` (V8) is responsible for:
- Detecting context via semantic search (RAG).
- Extracting tasks and decisions.
- Organizing notes into structured folders (e.g., `Meetings/`).
- Recording progress in the Daily Log (`daily/`).
- **Multilingual Support:** Generates all summaries and notes in the language defined in your `config.py` (e.g., Portuguese, English, Spanish).

> **Note:** This skill is designed to work within an Obsidian vault. It will automatically detect or create your organizational structure (Folders like `Meetings/` and `daily/`).

---
