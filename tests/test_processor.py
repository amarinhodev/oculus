"""
OCULUS — test_processor.py
Automated test suite for core processor.py functions.

Imports functions directly via config mock for full isolation.
Runs with: pytest data/oculus/tests/
"""

import sys
import os
import types
import yaml
import pytest
from datetime import datetime
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Bootstrap: inject config mock BEFORE importing processor
# ---------------------------------------------------------------------------

# Creates a fake 'config' module in sys.modules so that processor.py
# can import it even without a real config.py.
_mock_config = types.ModuleType("config")
_mock_config.USER_NAME = "Anderson Silva"
_mock_config.SOURCE_DIR = "/tmp/oculus_test_source"
_mock_config.CAPTIONS_DIR = "/tmp/oculus_test_captions"
_mock_config.ARCHIVE_DIR = "/tmp/oculus_test_archive"
_mock_config.TRANSCRIPT_PREFIX = "Google Meet transcript"
_mock_config.DEBUG_MODE = False

sys.modules.setdefault("config", _mock_config)

# Ensures the processor.py directory is on the path
_OCULUS_DIR = os.path.join(os.path.dirname(__file__), "..")
if _OCULUS_DIR not in sys.path:
    sys.path.insert(0, _OCULUS_DIR)

from processor import (  # noqa: E402 — import after config bootstrap
    merge_fragments,
    process_section,
    detect_meeting_type,
    parse_filename,
    build_frontmatter,
)


# ===========================================================================
# merge_fragments()
# ===========================================================================

class TestMergeFragments:

    def test_merge_single_fragment(self):
        """List with 1 item returns the item (no trailing space)."""
        result = merge_fragments(["Hello, world!"])
        assert result == "Hello, world!"

    def test_merge_identical_fragments(self):
        """Exact duplicates are removed — only one copy remains."""
        result = merge_fragments(["hello world", "hello world", "hello world"])
        assert result == "hello world"

    def test_merge_incremental_fragments(self):
        """Fragment B that starts like A but is longer replaces A."""
        fragments = ["Good morning", "Good morning everyone, let's get started"]
        result = merge_fragments(fragments)
        assert result == "Good morning everyone, let's get started"

    def test_merge_empty_list(self):
        """Empty list returns empty string."""
        result = merge_fragments([])
        assert result == ""

    def test_merge_whitespace_fragments(self):
        """Fragments containing only whitespace are ignored."""
        result = merge_fragments(["   ", "\t", "texto real", "  "])
        assert result == "texto real"


# ===========================================================================
# process_section()
# ===========================================================================

class TestProcessSection:

    def test_process_basic_speakers(self):
        """Multiple speakers generate turns with correct timestamps."""
        lines = [
            "Maria Oliveira (01/06/2025, 09:30 AM)",
            "Bom dia a todos.",
            "Carlos Souza (01/06/2025, 09:31 AM)",
            "Bom dia, Maria!",
        ]
        turns, participants = process_section(lines)
        assert len(turns) == 2
        assert "09:30 AM" in turns[0]
        assert "Maria Oliveira" in turns[0]
        assert "09:31 AM" in turns[1]
        assert "Carlos Souza" in turns[1]

    def test_process_user_name_substitution(self):
        """'Você' and 'You' are replaced by config.USER_NAME."""
        lines_voce = [
            "Você (01/06/2025, 09:30 AM)",  # TranscripTonic uses "Você" in PT-BR — intentional
            "Estou presente.",
        ]
        turns_v, participants_v = process_section(lines_voce)
        assert _mock_config.USER_NAME in turns_v[0]
        assert "Você" not in turns_v[0]  # TranscripTonic uses "Você" in PT-BR — intentional

        lines_you = [
            "You (01/06/2025, 09:30 AM)",
            "I am here.",
        ]
        turns_y, participants_y = process_section(lines_you)
        assert _mock_config.USER_NAME in turns_y[0]
        assert "You" not in turns_y[0]

    def test_process_empty_lines_ignored(self):
        """Empty lines do not generate extra turns."""
        lines = [
            "",
            "Maria Oliveira (01/06/2025, 09:30 AM)",
            "",
            "Mensagem da Maria.",
            "",
        ]
        turns, _ = process_section(lines)
        assert len(turns) == 1

    def test_process_system_lines_ignored(self):
        """Lines containing 'Transcript saved using' are ignored."""
        lines = [
            "Anderson Silva (01/06/2025, 09:30 AM)",
            "Valid message.",
            "Transcript saved using TranscripTonic",
        ]
        turns, _ = process_section(lines)
        assert len(turns) == 1
        assert "Transcript saved" not in turns[0]

    def test_process_same_speaker_consecutive(self):
        """Consecutive lines from same speaker at same timestamp are merged."""
        lines = [
            "Maria Oliveira (01/06/2025, 09:30 AM)",
            "Primeira frase.",
            "Maria Oliveira (01/06/2025, 09:30 AM)",
            "Segunda frase do mesmo turno.",
        ]
        turns, _ = process_section(lines)
        # Should result in only 1 turn (same speaker, same timestamp)
        assert len(turns) == 1
        assert "Primeira frase" in turns[0]
        assert "Segunda frase" in turns[0]


# ===========================================================================
# parse_filename() — filename parser
# ===========================================================================

class TestParseFilename:

    def test_parse_simple_title(self):
        """Simple standard filename: extracts title, ISO date and time."""
        filename = "Google Meet transcript-Weekly at 27-05-2026, 09-30 AM on.txt"
        title, date_iso, time_hhmm = parse_filename(filename)
        assert title == "Weekly"
        assert date_iso == "2026-05-27"
        assert time_hhmm == "09-30"

    def test_parse_title_with_at(self):
        """Title contains ' at ' — regex must not cut the title early.
        'Reunião at Scale' must be preserved in full.
        """
        filename = "Google Meet transcript-Reunião at Scale at 27-05-2026, 04-57 PM on.txt"  # PT-BR meeting title — tests the ' at ' edge case in filename parsing
        title, date_iso, time_hhmm = parse_filename(filename)
        assert title == "Reunião at Scale"  # PT-BR meeting title — tests the ' at ' edge case in filename parsing
        assert date_iso == "2026-05-27"
        # 04:57 PM → 16:57
        assert time_hhmm == "16-57"

    def test_parse_title_with_multiple_at(self):
        """Title with multiple 'at' — only the last date suffix is the delimiter."""
        filename = "Google Meet transcript-Sync at Scale at Speed at 10-06-2026, 11-00 AM on.txt"
        title, date_iso, time_hhmm = parse_filename(filename)
        assert title == "Sync at Scale at Speed"
        assert date_iso == "2026-06-10"
        assert time_hhmm == "11-00"

    def test_parse_fallback_on_bad_filename(self):
        """Filename not matching pattern → falls back to today's date without raising."""
        filename = "arquivo_completamente_errado.txt"
        today = datetime.now().strftime("%Y-%m-%d")
        title, date_iso, time_hhmm = parse_filename(filename)
        assert date_iso == today
        assert time_hhmm == "00-00"
        # Must not raise an exception — reaching here means it passed


# ===========================================================================
# detect_meeting_type()
# ===========================================================================

class TestDetectMeetingType:

    def test_type_daily(self):
        assert detect_meeting_type("Daily ITOps") == "daily"

    def test_type_weekly(self):
        assert detect_meeting_type("Weekly Infra Core") == "weekly"

    def test_type_1on1(self):
        assert detect_meeting_type("1:1 Anderson e Maria") == "1:1"

    def test_type_followup(self):
        assert detect_meeting_type("FUP Projeto X") == "follow-up"

    def test_type_default(self):
        """Title with no recognized keyword → 'meeting'."""
        assert detect_meeting_type("Brainstorm") == "meeting"


# ===========================================================================
# build_frontmatter()
# ===========================================================================

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


class TestBuildFrontmatter:

    def _make_frontmatter(self, **kwargs):
        defaults = dict(
            meeting_title="Daily ITOps",
            date_iso="2026-05-27",
            time_hhmm="09-30",
            meeting_type="daily",
            participants=["Maria Oliveira", "Carlos Souza"],
        )
        defaults.update(kwargs)
        return build_frontmatter(**defaults)

    def test_frontmatter_has_required_fields(self):
        """title, date, time, type, participants, source, tags are present."""
        fm = self._make_frontmatter()
        for field in ("title", "date", "time", "type", "participants", "source", "tags"):
            assert field in fm, f"Field '{field}' missing from frontmatter"

    def test_frontmatter_participants_excludes_user(self):
        """config.USER_NAME must NOT appear in the participants list."""
        participants_with_user = [
            _mock_config.USER_NAME,
            "Maria Oliveira",
            "Carlos Souza",
        ]
        # build_frontmatter receives the list already filtered by process_files()
        # We test that if we pass without the user, they do not appear
        participants_clean = [
            p for p in participants_with_user if p != _mock_config.USER_NAME
        ]
        fm = self._make_frontmatter(participants=participants_clean)
        assert _mock_config.USER_NAME not in fm

    def test_frontmatter_valid_yaml(self):
        """The frontmatter block is valid YAML (yaml.safe_load does not raise)."""
        fm = self._make_frontmatter()
        # Extract content between --- delimiters
        inner = fm.strip()
        if inner.startswith("---"):
            inner = inner[3:]
        if inner.endswith("---"):
            inner = inner[:-3]
        # Must not raise an exception
        parsed = yaml.safe_load(inner)
        assert isinstance(parsed, dict)
        assert parsed["title"] == "Daily ITOps"
        assert parsed["date"] == "2026-05-27"
        assert parsed["type"] == "daily"
