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
