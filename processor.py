"""
OCULUS — processor.py
Converts TranscripTonic .txt transcripts into structured Markdown files with YAML frontmatter.

Improvements (2025-01):
  - Structured logging via logging module (oculus.processor logger)
  - Robust filename parser using regex (handles meeting titles containing " at ")
  - Rich YAML frontmatter: title, date, time, type, participants, source, tags
  - Uses config.TRANSCRIPT_PREFIX instead of hardcoded string
  - No bare except: all errors logged with details
"""

import logging
import os
import re
import shutil
import config
from datetime import datetime

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------
logger = logging.getLogger("oculus.processor")

if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter("%(asctime)s [%(name)s] %(levelname)s — %(message)s")
    )
    logger.addHandler(_handler)
    logger.setLevel(logging.DEBUG if getattr(config, "DEBUG_MODE", False) else logging.INFO)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def merge_fragments(fragments):
    """Merges text fragments by removing incremental overlaps."""
    if not fragments:
        return ""
    unique_fragments = []
    for f in fragments:
        f = f.strip()
        if not f:
            continue
        if unique_fragments and f.lower().startswith(unique_fragments[-1].lower()):
            unique_fragments[-1] = f
        elif f not in unique_fragments:
            unique_fragments.append(f)
    return " ".join(unique_fragments)


def process_section(lines):
    """Processes a section (audio or chat) grouping by speaker and keeping timestamps.

    Returns:
        tuple[list[str], list[str]]: (formatted_turns, participant_names)
    """
    processed_turns = []
    participants = set()
    current_speaker = None
    current_time = None
    current_fragments = []

    for line in lines:
        line = line.strip()
        if (
            not line
            or "Transcript saved using" in line
            or "ciepnfnceimjehngolkijpnbappkkiag" in line
        ):
            continue

        speaker_match = re.match(
            r"^(.*?) \(\d{2}/\d{2}/\d{4}, (\d{2}:\d{2} [AP]M)\)$", line
        )

        if speaker_match:
            speaker = speaker_match.group(1)
            time_str = speaker_match.group(2)

            # Normalise local-user aliases to the configured username
            if speaker in config.LOCAL_USER_ALIASES:
                speaker = config.USER_NAME

            # Track participants (will be filtered for non-user later)
            participants.add(speaker)

            if (speaker != current_speaker or time_str != current_time) and current_fragments:
                text = merge_fragments(current_fragments)
                if text:
                    processed_turns.append(f"**[{current_time}] {current_speaker}:** {text}")
                current_fragments = []

            current_speaker = speaker
            current_time = time_str
        else:
            current_fragments.append(line)

    if current_speaker and current_fragments:
        text = merge_fragments(current_fragments)
        if text:
            processed_turns.append(f"**[{current_time}] {current_speaker}:** {text}")

    return processed_turns, list(participants)


def detect_meeting_type(title: str) -> str:
    """Classify meeting based on keywords in the title."""
    lower = title.lower()
    if any(k in lower for k in ("daily", "standup", "stand-up")):
        return "daily"
    if any(k in lower for k in ("weekly", "semanal")):
        return "weekly"
    if any(k in lower for k in ("1:1", "one on one", "one-on-one")):
        return "1:1"
    if any(k in lower for k in ("fup", "follow-up", "follow up")):
        return "follow-up"
    if "planning" in lower:
        return "planning"
    return "meeting"


def parse_filename(filename: str):
    """Extract meeting_title, date_iso, time_hhmm from a TranscripTonic filename.

    TranscripTonic always ends with: <title> at DD-MM-YYYY, HH-MM AM/PM on.txt
    Using regex anchored at the end avoids false positives when the title
    itself contains " at ".

    Returns:
        tuple[str, str, str]: (meeting_title, date_iso, time_hh_mm)
            date_iso  — "YYYY-MM-DD"
            time_hh_mm — "HH-MM" (24h, dash-separated for safe filenames)
    """
    # Pattern anchored to the known TranscripTonic suffix
    pattern = r' at (\d{2}-\d{2}-\d{4}), (\d{2}-\d{2} [AP]M) on\.txt$'
    match = re.search(pattern, filename)

    if not match:
        logger.warning(
            "Cannot parse date/time from filename '%s' — using today as fallback.", filename
        )
        # Best-effort title extraction
        if f"{config.TRANSCRIPT_PREFIX}-" in filename:
            meeting_title = filename.split(f"{config.TRANSCRIPT_PREFIX}-", 1)[1].replace(".txt", "").strip()
        else:
            meeting_title = filename.replace(".txt", "").strip()
        return meeting_title, datetime.now().strftime("%Y-%m-%d"), "00-00"

    date_raw = match.group(1)   # DD-MM-YYYY
    time_raw = match.group(2)   # HH-MM AM/PM

    datetime_str = f"{date_raw}, {time_raw}"
    try:
        # strptime with %I (12h) and %p (AM/PM); minutes separator in source is "-"
        dt_obj = datetime.strptime(datetime_str, "%d-%m-%Y, %I-%M %p")
        date_iso = dt_obj.strftime("%Y-%m-%d")
        time_hhmm = dt_obj.strftime("%H-%M")
        time_display = dt_obj.strftime("%H:%M")
    except ValueError as exc:
        logger.warning(
            "Datetime parse failed for '%s' (%s) — using today as fallback.", filename, exc
        )
        date_iso = datetime.now().strftime("%Y-%m-%d")
        time_hhmm = "00-00"
        time_display = "00:00"
    else:
        time_display = dt_obj.strftime("%H:%M")

    # Extract title: everything after "transcript-" up to " at <date>" suffix
    # We know the match starts with " at DD-MM-YYYY, ..."
    match_start = match.start()
    after_prefix = filename.split(f"{config.TRANSCRIPT_PREFIX}-", 1)
    if len(after_prefix) > 1:
        # after_prefix[1] is "<title> at DD-MM-YYYY, HH-MM AM/PM on.txt"
        # match_start is relative to `filename`; compute relative to after_prefix[1]
        prefix_offset = len(f"{config.TRANSCRIPT_PREFIX}-")
        title_end = match_start - prefix_offset
        meeting_title = after_prefix[1][:title_end].strip()
    else:
        meeting_title = "Meeting"

    return meeting_title, date_iso, time_hhmm


def build_frontmatter(
    meeting_title: str,
    date_iso: str,
    time_hhmm: str,
    meeting_type: str,
    participants: list,
) -> str:
    """Build a YAML frontmatter block."""
    time_display = time_hhmm.replace("-", ":")
    # Render participants as YAML list
    participants_yaml = "\n".join(f'  - "{p}"' for p in sorted(participants))
    if not participants_yaml:
        participants_yaml = ""
        participants_block = "participants: []"
    else:
        participants_block = f"participants:\n{participants_yaml}"

    frontmatter = (
        "---\n"
        f'title: "{meeting_title}"\n'
        f'date: "{date_iso}"\n'
        f'time: "{time_display}"\n'
        f'type: "{meeting_type}"\n'
        f"{participants_block}\n"
        'source: "Google Meet / TranscripTonic"\n'
        "tags: [meeting, transcription]\n"
        "---\n"
    )
    return frontmatter


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------

def process_files():
    """Scan SOURCE_DIR, convert all TranscripTonic .txt files to Markdown."""
    if not os.path.exists(config.CAPTIONS_DIR):
        os.makedirs(config.CAPTIONS_DIR)
    if not os.path.exists(config.ARCHIVE_DIR):
        os.makedirs(config.ARCHIVE_DIR)

    files = [
        f
        for f in os.listdir(config.SOURCE_DIR)
        if f.startswith(config.TRANSCRIPT_PREFIX) and f.endswith(".txt")
    ]

    if not files:
        logger.info("No TranscripTonic files found in %s.", config.SOURCE_DIR)
        return

    logger.info("Found %d file(s) to process.", len(files))

    for filename in files:
        logger.info("Processing: %s", filename)
        source_path = os.path.join(config.SOURCE_DIR, filename)

        try:
            with open(source_path, "r", encoding="utf-8") as fh:
                content = fh.read()
        except OSError as exc:
            logger.error("Failed to read '%s': %s", source_path, exc)
            continue

        # Split audio / chat sections
        parts = content.split("---------------")
        audio_lines = []
        chat_lines = []
        current_section = "audio"

        for part in parts:
            if "CHAT MESSAGES" in part:
                current_section = "chat"
                continue
            lines = part.strip().split("\n")
            if current_section == "audio":
                audio_lines.extend(lines)
            else:
                chat_lines.extend(lines)

        audio_processed, audio_participants = process_section(audio_lines)
        chat_processed, chat_participants = process_section(chat_lines)

        # Merge participant lists, exclude the configured user
        all_participants = (set(audio_participants) | set(chat_participants)) - {config.USER_NAME}
        participants_list = sorted(all_participants)

        # Parse filename robustly
        meeting_title, date_iso, time_hhmm = parse_filename(filename)

        # Classify meeting type
        meeting_type = detect_meeting_type(meeting_title)

        # Build output filename
        safe_title = "".join(
            c for c in meeting_title if c.isalnum() or c in (" ", "-", "_")
        ).replace(" ", "_")
        new_filename = f"{date_iso}_{time_hhmm}_{safe_title}.md"
        dest_path = os.path.join(config.CAPTIONS_DIR, new_filename)

        # Build Markdown content
        time_display = time_hhmm.replace("-", ":")
        frontmatter = build_frontmatter(
            meeting_title, date_iso, time_hhmm, meeting_type, participants_list
        )

        md_content = frontmatter
        md_content += f"\n# 🎙️ Transcription: {meeting_title}\n"
        md_content += f"**Date:** {date_iso.replace('-', '/')} | **Time:** {time_display}\n---\n\n"
        md_content += "## 🔊 Audio Transcription\n\n"
        md_content += "\n\n".join(audio_processed)

        if chat_processed:
            md_content += "\n\n---\n## 💬 Chat Messages\n\n"
            md_content += "\n\n".join(chat_processed)

        try:
            with open(dest_path, "w", encoding="utf-8") as fh:
                fh.write(md_content)
        except OSError as exc:
            logger.error("Failed to write '%s': %s", dest_path, exc)
            continue

        logger.info("✅ Generated: %s (type=%s, participants=%d)", new_filename, meeting_type, len(participants_list))

        # Archive original
        try:
            shutil.move(source_path, os.path.join(config.ARCHIVE_DIR, filename))
        except OSError as exc:
            logger.warning("Could not archive '%s': %s", filename, exc)


if __name__ == "__main__":
    process_files()
