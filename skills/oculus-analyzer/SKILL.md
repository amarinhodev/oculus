---
name: oculus-analyzer
description: Analyzes meetings, extracts tasks and tags, generates Canvas diagrams, and autonomously records progress in the Daily Log.
---

# OCULUS Analyzer Workflow (V8 - Fully Autonomous)

## 1. 🔍 Environment Discovery and Decision (DO NOT ASK)
As you are operating in the background, you must make immediate executive decisions without interacting with the user:
- **Mapping:** List the current Vault directories to understand the user's organization pattern.
- **Meetings Folder:** 
    1. Prioritize existing folders like `Meetings/`, `Reunioes/`, or `Engineering/Meetings/`.
    2. If multiple exist, use the one containing the most recent notes.
    3. If NONE exist, automatically create a `Meetings/` folder in the Vault root.
- **Daily Log:** 
    1. Look for a `daily/` or `diario/` folder. 
    2. If it doesn't exist, create a `daily/` folder in the root.

## 2. Research and Metadata (Vertical YAML)
- **Frontmatter:** Use vertical YAML lists.
- **Context:** Link via RAG to projects and modules identified in the transcript.
- **Language:** Perform all analysis and writing in the language specified in the user's prompt (Default to English if not specified).

## 3. 🧠 Analysis Guidelines (Mandatory)
Generate a structured Markdown document with:
- **Executive Summary:** Concise objective and main outcome.
- **Decisions Made:** List of confirmed definitions and approvals.
- **Action Items (Task List):** Format `- [ ] Task (@owner)`.
- **Technical/Business Insights:** Crucial points from the conversation.

## 4. 📂 Note Recording
- **Filename:** `YYYY-MM-DD_HH-MM_[Title].md`.
- **Action:** Save the file in the meetings folder decided in Step 1.

## 5. 🗓️ Daily Log Entry
- **Action:** Locate or create the `daily/YYYY-MM-DD.md` file.
- **Content:** Append (at the end of the file) the link to the new note and a brief description of the meeting's impact.

## 6. Finalization
- Index created files (`obsidian_rag_index`).
- **IMPORTANT:** Execute all steps silently. Do not ask for confirmation or suggestions. Decide and execute.
