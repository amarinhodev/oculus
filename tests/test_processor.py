"""
OCULUS — test_processor.py
Suite de testes automatizados para as funções core do processor.py.

Importa diretamente as funções via mock de config para isolamento total.
Roda com: pytest data/oculus/tests/
"""

import sys
import os
import types
import yaml
import pytest
from datetime import datetime
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Bootstrap: injetar mock de config ANTES de importar processor
# ---------------------------------------------------------------------------

# Cria um módulo 'config' falso no sys.modules para que o processor.py
# possa importá-lo mesmo sem um config.py real.
_mock_config = types.ModuleType("config")
_mock_config.USER_NAME = "Anderson Silva"
_mock_config.SOURCE_DIR = "/tmp/oculus_test_source"
_mock_config.CAPTIONS_DIR = "/tmp/oculus_test_captions"
_mock_config.ARCHIVE_DIR = "/tmp/oculus_test_archive"
_mock_config.TRANSCRIPT_PREFIX = "Google Meet transcript"
_mock_config.DEBUG_MODE = False

sys.modules.setdefault("config", _mock_config)

# Garante que o diretório do processor.py esteja no path
_OCULUS_DIR = os.path.join(os.path.dirname(__file__), "..")
if _OCULUS_DIR not in sys.path:
    sys.path.insert(0, _OCULUS_DIR)

from processor import (  # noqa: E402 — import após bootstrap de config
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
        """Lista com 1 item retorna o item (sem trailing space)."""
        result = merge_fragments(["Olá, mundo!"])
        assert result == "Olá, mundo!"

    def test_merge_identical_fragments(self):
        """Duplicatas exatas são removidas — apenas uma cópia permanece."""
        result = merge_fragments(["hello world", "hello world", "hello world"])
        assert result == "hello world"

    def test_merge_incremental_fragments(self):
        """Fragmento B que começa igual a A mas é maior substitui A."""
        fragments = ["Bom dia", "Bom dia pessoal, vamos começar"]
        result = merge_fragments(fragments)
        assert result == "Bom dia pessoal, vamos começar"

    def test_merge_empty_list(self):
        """Lista vazia retorna string vazia."""
        result = merge_fragments([])
        assert result == ""

    def test_merge_whitespace_fragments(self):
        """Fragmentos contendo apenas espaço são ignorados."""
        result = merge_fragments(["   ", "\t", "texto real", "  "])
        assert result == "texto real"


# ===========================================================================
# process_section()
# ===========================================================================

class TestProcessSection:

    def test_process_basic_speakers(self):
        """Múltiplos speakers geram turnos com timestamps corretos."""
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
        """'Você' e 'You' são substituídos por config.USER_NAME."""
        lines_voce = [
            "Você (01/06/2025, 09:30 AM)",
            "Estou presente.",
        ]
        turns_v, participants_v = process_section(lines_voce)
        assert _mock_config.USER_NAME in turns_v[0]
        assert "Você" not in turns_v[0]

        lines_you = [
            "You (01/06/2025, 09:30 AM)",
            "I am here.",
        ]
        turns_y, participants_y = process_section(lines_you)
        assert _mock_config.USER_NAME in turns_y[0]
        assert "You" not in turns_y[0]

    def test_process_empty_lines_ignored(self):
        """Linhas vazias não geram turnos extras."""
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
        """Linhas com 'Transcript saved using' são ignoradas."""
        lines = [
            "Anderson Silva (01/06/2025, 09:30 AM)",
            "Mensagem válida.",
            "Transcript saved using TranscripTonic",
        ]
        turns, _ = process_section(lines)
        assert len(turns) == 1
        assert "Transcript saved" not in turns[0]

    def test_process_same_speaker_consecutive(self):
        """Falas consecutivas do mesmo speaker no mesmo timestamp são agrupadas."""
        lines = [
            "Maria Oliveira (01/06/2025, 09:30 AM)",
            "Primeira frase.",
            "Maria Oliveira (01/06/2025, 09:30 AM)",
            "Segunda frase do mesmo turno.",
        ]
        turns, _ = process_section(lines)
        # Deve resultar em apenas 1 turno (mesmo speaker, mesmo timestamp)
        assert len(turns) == 1
        assert "Primeira frase" in turns[0]
        assert "Segunda frase" in turns[0]


# ===========================================================================
# parse_filename() — parser de nome de arquivo
# ===========================================================================

class TestParseFilename:

    def test_parse_simple_title(self):
        """Filename padrão simples: extrai título, data ISO e hora."""
        filename = "Google Meet transcript-Weekly at 27-05-2026, 09-30 AM on.txt"
        title, date_iso, time_hhmm = parse_filename(filename)
        assert title == "Weekly"
        assert date_iso == "2026-05-27"
        assert time_hhmm == "09-30"

    def test_parse_title_with_at(self):
        """Título contém ' at ' — a regex não deve cortar o título cedo.
        'Reunião at Scale' deve ser preservado integralmente.
        """
        filename = "Google Meet transcript-Reunião at Scale at 27-05-2026, 04-57 PM on.txt"
        title, date_iso, time_hhmm = parse_filename(filename)
        assert title == "Reunião at Scale"
        assert date_iso == "2026-05-27"
        # 04:57 PM → 16:57
        assert time_hhmm == "16-57"

    def test_parse_title_with_multiple_at(self):
        """Título com múltiplos 'at' — apenas o último sufixo de data é o delimitador."""
        filename = "Google Meet transcript-Sync at Scale at Speed at 10-06-2026, 11-00 AM on.txt"
        title, date_iso, time_hhmm = parse_filename(filename)
        assert title == "Sync at Scale at Speed"
        assert date_iso == "2026-06-10"
        assert time_hhmm == "11-00"

    def test_parse_fallback_on_bad_filename(self):
        """Nome que não bate com o padrão → usa data de hoje sem lançar exceção."""
        filename = "arquivo_completamente_errado.txt"
        today = datetime.now().strftime("%Y-%m-%d")
        title, date_iso, time_hhmm = parse_filename(filename)
        assert date_iso == today
        assert time_hhmm == "00-00"
        # Não deve lançar exceção — chegou até aqui significa que passou


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
        """Título sem keyword reconhecida → 'meeting'."""
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
        """title, date, time, type, participants, source, tags estão presentes."""
        fm = self._make_frontmatter()
        for field in ("title", "date", "time", "type", "participants", "source", "tags"):
            assert field in fm, f"Campo '{field}' ausente no frontmatter"

    def test_frontmatter_participants_excludes_user(self):
        """config.USER_NAME NÃO deve aparecer na lista de participants."""
        participants_with_user = [
            _mock_config.USER_NAME,
            "Maria Oliveira",
            "Carlos Souza",
        ]
        # build_frontmatter recebe a lista já filtrada por process_files()
        # Testamos que se passarmos sem o user, ele não aparece
        participants_clean = [
            p for p in participants_with_user if p != _mock_config.USER_NAME
        ]
        fm = self._make_frontmatter(participants=participants_clean)
        assert _mock_config.USER_NAME not in fm

    def test_frontmatter_valid_yaml(self):
        """O bloco frontmatter é YAML válido (yaml.safe_load não levanta exceção)."""
        fm = self._make_frontmatter()
        # Extrai o conteúdo entre os delimitadores ---
        inner = fm.strip()
        if inner.startswith("---"):
            inner = inner[3:]
        if inner.endswith("---"):
            inner = inner[:-3]
        # Não deve lançar exceção
        parsed = yaml.safe_load(inner)
        assert isinstance(parsed, dict)
        assert parsed["title"] == "Daily ITOps"
        assert parsed["date"] == "2026-05-27"
        assert parsed["type"] == "daily"
