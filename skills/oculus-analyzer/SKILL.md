---
name: oculus-analyzer
version: "10.0"
description: >
  Analyzes meeting transcriptions using Antigravity (agy) or Gemini CLI,
  discovers related projects and notes in the user's Obsidian vault (via RAG or MOCs),
  optionally enriches issue tracker tickets, generates structured meeting notes,
  and appends a summary link to the daily log.
---

# OCULUS Analyzer Workflow (V10.0 — RAG + Deterministic Vault Discovery)

> **Core principle:** This skill transforms raw Google Meet transcriptions (`Captions/YYYY-MM-DD_HH-MM_*.md`) into structured, executive Obsidian Meeting Notes in your configured `MEETINGS_PATH` and registers the meeting in your daily log (`DAILY_PATH/YYYY-MM-DD.md`).
>
> **Local Vault Override (`LOCAL_CONTEXT.md`):** Before starting, check if `LOCAL_CONTEXT.md` exists in the same directory as this `SKILL.md`. If present, read it immediately and apply its vault-specific paths, tag taxonomy, project indices, and local CLI integrations (such as Jira/issue-tracker enrichment) as authoritative rules.

---

## Step 0 — Read Transcription Frontmatter & Body

Read the input transcription `.md` file passed in the prompt:

```yaml
title: "Meeting title"
date: "YYYY-MM-DD"
time: "HH:MM"
type: "daily | weekly | meeting | fup | one-on-one"
participants: ["Name1", "Name2"]
tags: [meeting, transcription]
```

1. **Sanitize Title & Prefix:** Strip noisy Google Meet prefixes such as `"Meet - "`, `"Meet_ "`, or `"Google Meet"` when building the human-readable title (or infer a clear thematic title from the conversation if the title is just a random Meet room code like `abc-defg-hij`).
2. **Validate Minimum Content:** If the audio transcription has fewer than 3 meaningful lines (e.g., an empty/aborted room), create a minimal stub note or log it cleanly without inventing content.
3. **Normalize `type`:**
   The `type` field in the output frontmatter MUST be one of:
   `daily | weekly | meeting | fup | one-on-one`
   *(Never use `1:1`, `follow-up`, `planning`, `meeting-note`, or quotes around the value).*

---

## Step 1 — Fast Vault Discovery & Optional Ticket Enrichment

To link projects, modules, people, and tasks accurately without slow full-directory scans:

### 1.1 — Vault Project Discovery
1. **Local Context Check:** If `LOCAL_CONTEXT.md` exists alongside this `SKILL.md`, read it first for exact project MOC paths and custom CLI tools.
2. **Semantic RAG (when available):** If an Obsidian RAG MCP tool (`obsidian_rag_index` or similar) is available in the current harness, query it in the user's `PREFERRED_LANGUAGE` for active projects and topics mentioned in the meeting.
3. **Fast Deterministic Discovery:** Check the vault's project index (e.g., `Projects_MOC.md` or `Projects/` folder inside the target vault) using targeted `grep -i` or `read_file` to resolve exact `[[Wikilinks]]` for systems and initiatives discussed in the transcript.

### 1.2 — Optional Issue Tracker / Ticket Enrichment
If the transcript mentions explicit ticket keys (e.g. `PROJ-123`, `ENG-456`) and a local issue-tracker CLI is configured in `LOCAL_CONTEXT.md`:
1. Query the ticket key to fetch its real summary and current status.
2. Enrich the **Action Items** and **Executive Summary** with the verified ticket key and status. If no CLI is configured or offline, proceed gracefully without blocking.

---

## Step 2 — Generate Structured Meeting Note

Save the analyzed note at the exact output path requested in the prompt (or `<MEETINGS_PATH>/YYYY-MM-DD_HH-MM_<Sanitized_Title>.md`).
*(Keep the exact `YYYY-MM-DD_HH-MM_` prefix from the input caption filename so `watcher.py` can track 1:1 completion).*

Write all section headings and content in the user's configured `PREFERRED_LANGUAGE` (below shown in English / Portuguese equivalents):

```markdown
---
type: <daily | weekly | meeting | fup | one-on-one>
date: YYYY-MM-DD
time: "HH:MM"
project: <Primary Project or Team Stream>
participants:
  - <Configured User Name>
  - <Participant 1>
  - <Participant 2>
related_projects:
  - "[[<PathToProjectNote>|<ProjectNote>]]"
tags:
  - meeting
  - <Tag1>
  - <Tag2>
---

# 🎙️ <Clean Descriptive Meeting Title>

## 📋 Executive Summary / Resumo Executivo
<2 to 4 direct lines synthesizing the goal of the conversation, key numbers/metrics discussed, and main outcome.>

## ✅ Decisions Made / Decisões Tomadas
- **<Topic>:** <Objective decision reached by the group.>

## 📌 Action Items / Ações e Itens de Trabalho
- [ ] <Actionable task with context and optional ticket key [PROJ-XXXX]> (@<Owner>)

## 💡 Technical & Business Insights / Insights Técnicos e de Negócio
- **<Architecture / Cost / Risk / Opportunity>:** <Key insight extracted from the discussion.>

## 🔗 Related Projects & Context / Projetos e Contextos Relacionados
- [[<PathToProjectNote>|<ProjectNote>]] — <How it relates to the agenda>

## 👥 Participants / Participantes
- <Configured User Name>
- <Participant 1>
```

---

## Step 3 — Daily Log Integration (Anti-Overwrite)

> **ABSOLUTE RULE:** Always READ and APPEND (`edit_file` or `>>`) — **NEVER** overwrite existing content in the daily note (`<DAILY_PATH>/YYYY-MM-DD.md`).

1. Target file: `<DAILY_PATH>/YYYY-MM-DD.md` (matching the meeting's `date`).
2. If the file does not exist, create it using the vault's daily template (or a standard daily frontmatter with `## 🗓️ Meetings`).
3. Check if a link to `YYYY-MM-DD_HH-MM_` is already present in `<DAILY_PATH>/YYYY-MM-DD.md`.
4. If not present, append under `## 🗓️ Meetings`:
   ```markdown
   - **[[<RelativePathToMeetingNote>|<Clean Meeting Title>]]** (`HH:MM`) — <1-line summary of outcome/decisions> *(Participants: <N>)*
   ```

---

## Absolute Rules

| Rule | Description |
|------|-------------|
| 🚫 Never ask | NEVER ask confirmation questions — execute end-to-end autonomously |
| ✅ Exact Vault Paths | Always write meeting notes and daily logs to the exact paths provided in the prompt or `LOCAL_CONTEXT.md` |
| ✅ Append-only Daily | Never overwrite existing entries in `daily/YYYY-MM-DD.md` |
| ✅ Normalized `type:` | `type:` must be `daily \| weekly \| meeting \| fup \| one-on-one`; `date:` must be `YYYY-MM-DD` |
| ✅ Clean Tag Hygiene | Follow the prompt's or `LOCAL_CONTEXT.md`'s tag contract; use `[[Wikilinks]]` for specific projects |
