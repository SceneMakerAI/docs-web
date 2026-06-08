"""
TC-4: Notion 페이지 삭제 → 로컬 파일 제거 (수동 파일 보호)
TC-5: last_edited 기반 스킵 (불필요한 파일 덮어쓰기 방지)
"""
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import scripts.notion_to_md as n


# ── TC-4: Notion 삭제 → 로컬 파일 제거, 수동 파일 보호 ───────────────────────

class TestRemoveOrphans:

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _create_file(self, name: str, content: str = "# test") -> str:
        path = os.path.join(self.tmpdir, name)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(content)
        return path

    def test_synced_file_deleted_when_absent_from_notion(self):
        """Notion에서 삭제된 페이지에 해당하는 .md 파일이 로컬에서 제거됨."""
        synced_path = self._create_file("synced.md")
        previously_tracked = {synced_path}
        synced_files = set()  # Notion에 페이지 없음

        with patch.object(n, "SAVE_DIR", self.tmpdir):
            n.remove_orphans(synced_files, previously_tracked)

        assert not os.path.exists(synced_path), "Notion에서 삭제된 파일이 로컬에 남아 있음"

    def test_manual_file_preserved(self):
        """sync_map에 없는 수동 작성 파일은 삭제되지 않음."""
        manual_path = self._create_file("manual.md")
        previously_tracked = set()  # sync가 만든 파일이 아님
        synced_files = set()

        with patch.object(n, "SAVE_DIR", self.tmpdir):
            n.remove_orphans(synced_files, previously_tracked)

        assert os.path.exists(manual_path), "수동 파일이 삭제됨"

    def test_skip_files_preserved(self):
        """SKIP_FILES에 포함된 파일(overview.mdx)은 삭제되지 않음."""
        skip_path = self._create_file("overview.mdx")
        previously_tracked = {skip_path}
        synced_files = set()

        with patch.object(n, "SAVE_DIR", self.tmpdir):
            n.remove_orphans(synced_files, previously_tracked)

        assert os.path.exists(skip_path), "SKIP_FILES 파일이 삭제됨"

    def test_still_synced_file_not_deleted(self):
        """Notion에 여전히 존재하는 파일은 삭제되지 않음."""
        active_path = self._create_file("active.md")
        previously_tracked = {active_path}
        synced_files = {active_path}  # Notion에도 있음

        with patch.object(n, "SAVE_DIR", self.tmpdir):
            n.remove_orphans(synced_files, previously_tracked)

        assert os.path.exists(active_path), "현재 동기화된 파일이 삭제됨"

    def test_multiple_files_partial_delete(self):
        """일부만 Notion에서 삭제된 경우 해당 파일만 제거."""
        deleted_path = self._create_file("deleted.md")
        kept_path = self._create_file("kept.md")
        previously_tracked = {deleted_path, kept_path}
        synced_files = {kept_path}  # kept.md만 Notion에 있음

        with patch.object(n, "SAVE_DIR", self.tmpdir):
            n.remove_orphans(synced_files, previously_tracked)

        assert not os.path.exists(deleted_path), "삭제 대상 파일이 남아 있음"
        assert os.path.exists(kept_path), "보존 대상 파일이 삭제됨"


# ── TC-5: last_edited 기반 스킵 ───────────────────────────────────────────────

class TestSaveDocPageSkip:

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_page(self, page_id: str, title: str, last_edited: str) -> dict:
        return {
            "id": page_id,
            "last_edited_time": last_edited,
            "properties": {
                "이름": {
                    "type": "title",
                    "title": [{"plain_text": title}],
                }
            },
        }

    def _content_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()

    def _write_md(self, filename: str, content: str) -> str:
        path = os.path.join(self.tmpdir, filename)
        Path(path).write_text(content, encoding="utf-8")
        return path

    def test_skip_when_last_edited_unchanged(self):
        """last_edited, 파일경로, 순서, 해시 모두 동일 → 파일 write 없음."""
        last_edited = "2026-05-27T10:00:00.000Z"
        slug = "테스트"
        filename = os.path.join(self.tmpdir, f"{slug}.md")
        content = "---\ntitle: 테스트\nsidebar_position: 1\nslug: '1'\n---\n\n## 내용\n"
        self._write_md(f"{slug}.md", content)
        content_hash = self._content_hash(content)

        existing_map = {
            "page-1": {
                "file": filename,
                "last_edited": last_edited,
                "content_hash": content_hash,
                "order": 1,
                "parent_id": None,
            }
        }

        page = self._make_page("page-1", "테스트", last_edited)

        written_files = []
        original_open = open

        def tracking_open(path, mode="r", **kwargs):
            if "w" in mode and self.tmpdir in str(path):
                written_files.append(path)
            return original_open(path, mode, **kwargs)

        with patch.object(n, "SAVE_DIR", self.tmpdir), \
             patch.object(n, "NOTION_PROPERTY_TITLE", "이름"), \
             patch("builtins.open", side_effect=tracking_open):
            n.save_doc_page(page, 1, existing_map)

        assert written_files == [], f"불필요한 파일 write 발생: {written_files}"

    def test_write_when_last_edited_changed(self):
        """last_edited가 달라졌으면 파일을 덮어씀."""
        old_last_edited = "2026-05-27T09:00:00.000Z"
        new_last_edited = "2026-05-27T10:00:00.000Z"
        slug = "테스트"
        filename = os.path.join(self.tmpdir, f"{slug}.md")
        content = "---\ntitle: 테스트\nsidebar_position: 1\nslug: '1'\n---\n\n## 내용\n"
        self._write_md(f"{slug}.md", content)

        existing_map = {
            "page-1": {
                "file": filename,
                "last_edited": old_last_edited,  # 오래된 시각
                "content_hash": self._content_hash(content),
                "order": 1,
                "parent_id": None,
            }
        }

        page = self._make_page("page-1", "테스트", new_last_edited)

        written_files = []
        original_open = open

        def tracking_open(path, mode="r", **kwargs):
            if "w" in mode and self.tmpdir in str(path):
                written_files.append(str(path))
            return original_open(path, mode, **kwargs)

        def fake_get_blocks(page_id):
            return []

        with patch.object(n, "SAVE_DIR", self.tmpdir), \
             patch.object(n, "NOTION_PROPERTY_TITLE", "이름"), \
             patch.object(n, "get_page_blocks", side_effect=fake_get_blocks), \
             patch.object(n, "blocks_to_markdown", return_value=""), \
             patch("builtins.open", side_effect=tracking_open):
            n.save_doc_page(page, 1, existing_map)

        assert any(slug in f for f in written_files), \
            f"last_edited 변경 후 파일 write 없음 (written: {written_files})"


# ── TC-6: HTML 엔티티 이중 인코딩 복원 ───────────────────────────────────────

class TestHtmlEntityDecode:
    """Notion API가 &amp;gt; / &amp;lt; 형태로 이중 인코딩해 반환할 때
    extract_text_from_rich_text가 온전히 복원하는지 검증."""

    def _rt(self, plain: str, code: bool = False) -> list:
        return [{"plain_text": plain, "annotations": {"code": code, "bold": False, "italic": False, "strikethrough": False}, "href": None}]

    def test_single_encoded_gt_decoded(self):
        """`&gt;` (단일 인코딩) → `>`"""
        result = n.extract_text_from_rich_text(self._rt("&gt;=1.0"))
        assert result == ">=1.0"

    def test_double_encoded_gt_decoded(self):
        """`&amp;gt;` (이중 인코딩) → `>` — 현재 버그 재현."""
        result = n.extract_text_from_rich_text(self._rt("&amp;gt;=1.0"))
        assert result == ">=1.0"

    def test_double_encoded_lt_decoded(self):
        """`&amp;lt;` (이중 인코딩) → `<`"""
        result = n.extract_text_from_rich_text(self._rt("&amp;lt;3.12"))
        assert result == "<3.12"

    def test_mixed_double_encoded(self):
        """`&amp;gt;=2.4,&amp;lt;2.9` → `>=2.4,<2.9`"""
        result = n.extract_text_from_rich_text(self._rt("&amp;gt;=2.4,&amp;lt;2.9"))
        assert result == ">=2.4,<2.9"

    def test_inline_code_double_encoded(self):
        """인라인 코드 스팬 내부도 이중 인코딩 복원."""
        result = n.extract_text_from_rich_text(self._rt("&amp;gt;=1.0", code=True))
        assert result == "`>=1.0`"

    def test_plain_text_unchanged(self):
        """이미 올바른 텍스트는 변경 없음."""
        result = n.extract_text_from_rich_text(self._rt(">=1.0"))
        assert result == ">=1.0"


# ── TC-7: _rich_text_to_html HTML 테이블 엔티티 이중 인코딩 복원 ──────────────

class TestHtmlEntityHtmlTable:
    """HTML 테이블 경로(_rich_text_to_html)에서 Notion이 &amp;gt; / &amp;lt; 형태로
    이중 인코딩해 반환할 때 렌더링 가능한 HTML로 올바르게 변환하는지 검증."""

    def _rt(self, plain: str, code: bool = False) -> list:
        return [{"plain_text": plain, "annotations": {"code": code, "bold": False, "italic": False, "strikethrough": False}, "href": None}]

    def test_single_encoded_gt_in_html_table(self):
        """`&gt;` (단일 인코딩) → HTML에서 `>` 로 렌더링 가능한 `&gt;` 출력."""
        result = n._rich_text_to_html(self._rt("&gt;=1.0"))
        assert result == "&gt;=1.0"

    def test_double_encoded_gt_in_html_table(self):
        """`&amp;gt;` (이중 인코딩) → 루프 unescape 후 `&gt;` 출력 (not `&amp;gt;`)."""
        result = n._rich_text_to_html(self._rt("&amp;gt;=1.0"))
        assert result == "&gt;=1.0"

    def test_double_encoded_lt_in_html_table(self):
        """`&amp;lt;2.9` → `&lt;2.9`"""
        result = n._rich_text_to_html(self._rt("&amp;lt;2.9"))
        assert result == "&lt;2.9"

    def test_mixed_double_encoded_in_html_table(self):
        """`&amp;gt;=2.4,&amp;lt;2.9` → `&gt;=2.4,&lt;2.9`"""
        result = n._rich_text_to_html(self._rt("&amp;gt;=2.4,&amp;lt;2.9"))
        assert result == "&gt;=2.4,&lt;2.9"

    def test_code_span_double_encoded(self):
        """인라인 코드 내 이중 인코딩 → `<code>&gt;=1.0</code>`"""
        result = n._rich_text_to_html(self._rt("&amp;gt;=1.0", code=True))
        assert result == "<code>&gt;=1.0</code>"

    def test_plain_text_unchanged_in_html_table(self):
        """이미 올바른 텍스트는 변경 없음."""
        result = n._rich_text_to_html(self._rt(">=1.0"))
        assert result == "&gt;=1.0"


# ── TC-8: callout → Markdown blockquote 변환 ─────────────────────────────────

class TestCalloutAdmonition:
    """callout 블록이 이모지와 함께 blockquote(>)로 변환되는지 검증."""

    def _block(self, emoji: str, text: str) -> dict:
        return {
            "type": "callout",
            "callout": {
                "rich_text": [{"plain_text": text, "annotations": {"code": False, "bold": False, "italic": False, "strikethrough": False}, "href": None}],
                "icon": {"type": "emoji", "emoji": emoji},
            },
            "has_children": False,
        }

    def _render(self, block: dict) -> str:
        return n.block_to_markdown(block, lambda: "", lambda: 1)

    def test_warning_emoji(self):
        """⚠️ callout → > ⚠️ content (blockquote, no admonition)"""
        result = self._render(self._block("⚠️", "주의사항"))
        assert result.startswith("> ⚠️ 주의사항")
        assert ":::" not in result

    def test_tip_emoji(self):
        """💡 callout → > 💡 content"""
        result = self._render(self._block("💡", "팁 내용"))
        assert result.startswith("> 💡 팁 내용")
        assert ":::" not in result

    def test_info_emoji(self):
        """📍 callout → > 📍 content"""
        result = self._render(self._block("📍", "위치 정보"))
        assert result.startswith("> 📍 위치 정보")
        assert ":::" not in result

    def test_unknown_emoji(self):
        """매핑에 없는 이모지도 동일하게 blockquote"""
        result = self._render(self._block("🐍", "파이썬 관련"))
        assert result.startswith("> 🐍 파이썬 관련")
        assert ":::" not in result

    def test_no_emoji(self):
        """이모지 없는 callout → > content (prefix 없음)"""
        block = {
            "type": "callout",
            "callout": {
                "rich_text": [{"plain_text": "일반 메모", "annotations": {"code": False, "bold": False, "italic": False, "strikethrough": False}, "href": None}],
                "icon": {},
            },
            "has_children": False,
        }
        result = self._render(block)
        assert result.startswith("> 일반 메모")
        assert ":::" not in result


# ── TC-9: quote → Markdown blockquote 변환 ───────────────────────────────────

class TestQuoteBlockquote:
    """quote 블록이 표준 Markdown blockquote(>)로 변환되는지 검증."""

    def _block(self, text: str) -> dict:
        return {
            "type": "quote",
            "quote": {
                "rich_text": [{"plain_text": text, "annotations": {"code": False, "bold": False, "italic": False, "strikethrough": False}, "href": None}],
            },
            "has_children": False,
        }

    def _render(self, block: dict) -> str:
        return n.block_to_markdown(block, lambda: "", lambda: 1)

    def test_quote_uses_blockquote(self):
        """quote → > 마크다운 blockquote"""
        result = self._render(self._block("인용 내용"))
        assert result.startswith("> ")
        assert "인용 내용" in result

    def test_quote_not_admonition(self):
        """quote는 ::: 어드모니션이 아님"""
        result = self._render(self._block("인용 내용"))
        assert ":::" not in result

# ── TC-10: 멀티라인 인라인 코드 → fenced code block 변환 ──────────────────────

class TestMultilineInlineCodeToFenced:
    """paragraph 블록에서 단일 멀티라인 인라인 코드가 fenced code block으로 변환되는지 검증."""

    def _block(self, text: str, code: bool = True) -> dict:
        return {
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"plain_text": text, "annotations": {"code": code, "bold": False, "italic": False, "strikethrough": False}, "href": None}],
            },
            "has_children": False,
        }

    def _render(self, block: dict) -> str:
        return n.block_to_markdown(block, lambda: "", lambda: 1)

    def test_multiline_code_becomes_fenced(self):
        """멀티라인 인라인 코드 → ``` fenced block"""
        result = self._render(self._block("line1\nline2\nline3"))
        assert result.startswith("```\n")
        assert "line1\nline2\nline3" in result
        assert result.strip().endswith("```")

    def test_single_line_code_stays_inline(self):
        """단일 줄 인라인 코드 → 그대로 인라인 코드"""
        result = self._render(self._block("single line"))
        assert "`single line`" in result
        assert "```" not in result

    def test_flowchart_pattern(self):
        """파이프라인 플로우차트 패턴 → fenced block으로 변환"""
        flowchart = "원본 wav\n   │\n   ▼\n[1] denoise\n   ↳ output/"
        result = self._render(self._block(flowchart))
        assert result.startswith("```\n")
        assert "원본 wav" in result
        assert "│" in result


# ── TC-11: Notion 페이지 링크 → 내부 docs URL 변환 ───────────────────────────

class TestNotionPageLinkConversion:
    """_build_page_link_map / _resolve_notion_href / extract_text_from_rich_text
    연동으로 Notion 페이지 링크가 내부 docs 경로로 변환되는지 검증."""

    def setup_method(self):
        n._page_id_to_internal_url.clear()

    def teardown_method(self):
        n._page_id_to_internal_url.clear()

    def _make_sync_map(self):
        return {
            "368e15b4-0359-81cb-9b9b-d555dbfd19e3": {
                "file": "docs/poc/vision-bench/1편-...md",
                "last_edited": "2026-06-01T00:00:00.000Z",
                "content_hash": "abc",
                "order": 1,
                "parent_id": "vision-bench",
            },
            "365e15b4-0359-804b-87c8-f1acee149564": {  # 인덱스 페이지 — parent_id 없음
                "file": "docs/poc/vision-bench/index.md",
                "last_edited": "2026-06-01T00:00:00.000Z",
                "content_hash": "def",
                "order": 2,
                "parent_id": None,
            },
        }

    def test_build_page_link_map_child_page(self):
        """자식 페이지(parent_id 있음)는 /save_dir/parent/order 경로로 매핑."""
        with patch.object(n, "SAVE_DIR", "docs/poc"):
            n._build_page_link_map(self._make_sync_map())
        assert n._page_id_to_internal_url["368e15b4-0359-81cb-9b9b-d555dbfd19e3"] == "/docs/poc/vision-bench/1"

    def test_build_page_link_map_index_page_skipped(self):
        """parent_id 가 None 인 인덱스 페이지는 매핑에 포함하지 않음."""
        with patch.object(n, "SAVE_DIR", "docs/poc"):
            n._build_page_link_map(self._make_sync_map())
        assert "365e15b4-0359-804b-87c8-f1acee149564" not in n._page_id_to_internal_url

    def test_resolve_notion_href_known_page(self):
        """Notion 페이지 URL → 내부 경로 변환."""
        n._page_id_to_internal_url["368e15b4-0359-81cb-9b9b-d555dbfd19e3"] = "/docs/poc/vision-bench/1"
        result = n._resolve_notion_href("https://www.notion.so/368e15b4035981cb9b9bd555dbfd19e3")
        assert result == "/docs/poc/vision-bench/1"

    def test_resolve_notion_href_unknown_page_returns_original(self):
        """매핑에 없는 Notion URL은 그대로 반환."""
        result = n._resolve_notion_href("https://www.notion.so/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        assert result == "https://www.notion.so/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

    def test_resolve_non_notion_href_unchanged(self):
        """Notion URL 이 아닌 링크는 변환하지 않음."""
        result = n._resolve_notion_href("https://github.com/example")
        assert result == "https://github.com/example"

    def test_extract_text_converts_notion_link(self):
        """extract_text_from_rich_text 가 Notion href 를 내부 경로로 변환."""
        n._page_id_to_internal_url["368e15b4-0359-81cb-9b9b-d555dbfd19e3"] = "/docs/poc/vision-bench/1"
        rt = [{"plain_text": "1편 문서", "annotations": {"code": False, "bold": False, "italic": False, "strikethrough": False},
                "href": "https://www.notion.so/368e15b4035981cb9b9bd555dbfd19e3"}]
        result = n.extract_text_from_rich_text(rt)
        assert result == "[1편 문서](/docs/poc/vision-bench/1)"

    def test_extract_text_unknown_notion_link_kept(self):
        """매핑에 없는 Notion 링크는 원본 URL 유지."""
        rt = [{"plain_text": "외부 페이지", "annotations": {"code": False, "bold": False, "italic": False, "strikethrough": False},
                "href": "https://www.notion.so/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]
        result = n.extract_text_from_rich_text(rt)
        assert result == "[외부 페이지](https://www.notion.so/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa)"


# ── TC-12: 테이블 has_column_header / has_row_header 반영 ─────────────────────

def _make_table_block(has_column_header, has_row_header, rows):
    """rows: [["셀1", "셀2"], ...] 형태의 문자열 리스트."""
    def _rt(text):
        return [{"plain_text": text, "href": None,
                 "annotations": {"bold": False, "italic": False, "strikethrough": False,
                                 "underline": False, "code": False, "color": "default"}}]
    children = [
        {"type": "table_row", "table_row": {"cells": [_rt(c) for c in row]}}
        for row in rows
    ]
    return (
        {"type": "table", "table": {"has_column_header": has_column_header,
                                    "has_row_header": has_row_header}},
        children,
    )


class TestTableHeaders:

    def _render(self, has_col, has_row, rows):
        block, children = _make_table_block(has_col, has_row, rows)
        block["_children"] = children
        return n.block_to_markdown(block, lambda: "", lambda: 1)

    def test_column_header_only_uses_plain_markdown(self):
        """has_column_header=True만 있을 때 → plain markdown (| --- | 구분자)."""
        out = self._render(True, False, [["헤더A", "헤더B"], ["값1", "값2"]])
        assert "<table>" not in out
        assert "| --- |" in out
        assert "| 헤더A | 헤더B |" in out

    def test_row_header_only_first_col_is_th(self):
        """has_row_header=True → 1열만 <th>, 나머지 <td>."""
        out = self._render(False, True, [["레이블1", "값1"], ["레이블2", "값2"]])
        assert "<th>" in out
        # 두 번째 열은 td
        assert "<td>" in out
        # thead 없음 (열 헤더가 없으므로)
        assert "<thead>" not in out

    def test_both_headers(self):
        """has_column_header=True, has_row_header=True → 1행+1열 모두 <th>."""
        out = self._render(True, True, [["구분", "A", "B"], ["X", "1", "2"]])
        assert "<thead>" in out
        assert "<th>" in out
        assert "<td>" in out

    def test_no_header_plain_markdown(self):
        """헤더 없고 색 없으면 plain markdown."""
        out = self._render(False, False, [["a", "b"], ["c", "d"]])
        assert "<table>" not in out
        assert "| a | b |" in out

    def test_pipe_in_cell_forces_html(self):
        """셀 내용에 | 포함 시 HTML 테이블로 전환 — markdown 테이블 파싱 깨짐 방지."""
        out = self._render(True, False, [["단계", "명령"], ["evaluate", ".venv/bin/python evaluate.py [whisper|qwen|all]"]])
        assert "<table>" in out
        assert "whisper|qwen|all" in out
        # markdown 파이프 구분자로 쪼개지지 않음
        assert "| .venv" not in out


# ── TC-13: Shift+Enter (단락 내 줄바꿈) ──────────────────────────────────────

def _make_paragraph_block(text: str):
    """plain_text로 paragraph 블록 생성. \n은 Shift+Enter를 시뮬레이션."""
    return {
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"plain_text": text, "href": None,
                           "annotations": {"bold": False, "italic": False,
                                           "strikethrough": False, "underline": False,
                                           "code": False, "color": "default"}}]
        },
        "_children": [],
    }


class TestShiftEnterLineBreak:
    def _render(self, text):
        block = _make_paragraph_block(text)
        return n.block_to_markdown(block, lambda: "", lambda: 1)

    def test_shift_enter_becomes_hard_break(self):
        """Shift+Enter(\n) → CommonMark hard line break (두 스페이스 + \n)."""
        out = self._render("첫 줄\n둘째 줄")
        assert "첫 줄  \n둘째 줄" in out

    def test_plain_paragraph_no_break(self):
        """일반 단락은 변환 없음."""
        out = self._render("일반 텍스트")
        assert "일반 텍스트\n\n" == out

    def test_multiple_shift_enters(self):
        """여러 Shift+Enter가 모두 hard break으로 변환."""
        out = self._render("A\nB\nC")
        assert "A  \nB  \nC" in out
