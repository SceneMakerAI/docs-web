"""
TC-1: 멀티 커밋 push 범위 감지
TC-2: 로컬 .md 삭제 → Notion 아카이브
TC-3: 제목+내용 수정 → Notion 제목 및 블록 업데이트
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import scripts.md_to_notion as m


# ── TC-1: 멀티 커밋 push 범위 감지 ────────────────────────────────────────────

class TestMultiCommitRange:

    def _fake_diff(self, lines: str):
        """subprocess.check_output mock: 지정한 diff 출력 반환."""
        return lines

    def test_two_commits_both_detected(self):
        """커밋 A, B에 각각 다른 파일 변경 → 둘 다 감지."""
        fake = "A\tdocs/guide/page1.md\nA\tdocs/guide/page2.md\n"
        with patch.dict(os.environ, {"GIT_BEFORE": "aaa111", "GIT_AFTER": "bbb222"}):
            with patch("subprocess.check_output", return_value=fake):
                result = m.get_changed_files("docs/guide")
        assert "docs/guide/page1.md" in result["added"]
        assert "docs/guide/page2.md" in result["added"]

    def test_zero_sha_uses_head1_fallback(self):
        """GIT_BEFORE=0000...00 (신규 브랜치) → HEAD~1 폴백."""
        zero_sha = "0" * 40
        captured = {}

        def capture(args, **kwargs):
            # ["git", "-c", "core.quotepath=false", "diff", "--name-status", before, after, ...]
            captured["before"] = args[5]
            return ""

        with patch.dict(os.environ, {"GIT_BEFORE": zero_sha, "GIT_AFTER": "bbb222"}):
            with patch("subprocess.check_output", side_effect=capture):
                m.get_changed_files("docs/guide")

        assert captured["before"] == "HEAD~1"

    def test_empty_before_uses_head1_fallback(self):
        """GIT_BEFORE 미설정 → HEAD~1 폴백."""
        captured = {}

        def capture(args, **kwargs):
            captured["before"] = args[5]
            return ""

        env = {k: v for k, v in os.environ.items() if k != "GIT_BEFORE"}
        env.pop("GIT_BEFORE", None)
        with patch.dict(os.environ, env, clear=True):
            with patch("subprocess.check_output", side_effect=capture):
                m.get_changed_files("docs/guide")

        assert captured["before"] == "HEAD~1"

    def test_non_md_files_ignored(self):
        """yml, json 파일은 결과에 포함되지 않음."""
        fake = "A\tdocs/guide/config.yml\nM\tdocs/guide/page.md\n"
        with patch.dict(os.environ, {"GIT_BEFORE": "aaa", "GIT_AFTER": "bbb"}):
            with patch("subprocess.check_output", return_value=fake):
                result = m.get_changed_files("docs/guide")
        assert result["added"] == []
        assert result["modified"] == ["docs/guide/page.md"]


# ── TC-2: 로컬 .md 삭제 → Notion 아카이브 ────────────────────────────────────

class TestLocalDeleteArchivesNotion:

    def _make_response(self, status=200, body=None):
        r = MagicMock()
        r.status_code = status
        r.json.return_value = body or {}
        return r

    def test_deleted_file_archives_page(self):
        """git 삭제된 파일이 sync_map에 있으면 Notion 아카이브 호출."""
        sync_map = {
            "page-abc": {"file": "docs/guide/old.md", "last_edited": "2026-01-01T00:00:00.000Z", "order": 1, "parent_id": None}
        }
        changed = {"modified": [], "added": [], "deleted": ["docs/guide/old.md"]}

        with patch.object(m, "load_sync_map", return_value=sync_map), \
             patch.object(m, "get_changed_files", return_value=changed), \
             patch.object(m, "save_sync_map") as mock_save, \
             patch("requests.patch", return_value=self._make_response()) as mock_patch, \
             patch("requests.get", return_value=self._make_response()):

            m.process_section("docs/guide")

        # archive_page는 PATCH /pages/{page_id} with archived=True
        patch_calls = mock_patch.call_args_list
        archive_call = next(
            (c for c in patch_calls if f"/pages/page-abc" in c.args[0]),
            None,
        )
        assert archive_call is not None, "archive_page 호출 없음"
        assert archive_call.kwargs["json"] == {"archived": True}

        # sync_map에서 제거됨
        saved_map = mock_save.call_args[0][1]
        assert "page-abc" not in saved_map

    def test_untracked_file_delete_skipped(self):
        """sync_map에 없는 파일 삭제 → Notion 호출 없음 (수동 파일 안전)."""
        sync_map = {}
        changed = {"modified": [], "added": [], "deleted": ["docs/guide/manual.md"]}

        with patch.object(m, "load_sync_map", return_value=sync_map), \
             patch.object(m, "get_changed_files", return_value=changed), \
             patch.object(m, "save_sync_map") as mock_save, \
             patch("requests.patch") as mock_patch:

            m.process_section("docs/guide")

        mock_patch.assert_not_called()
        mock_save.assert_not_called()  # 변경 없으면 저장 안 함


# ── TC-3: 제목+내용 수정 → Notion 업데이트 ───────────────────────────────────

class TestModifyUpdatesNotion:

    def _make_response(self, status=200, body=None):
        r = MagicMock()
        r.status_code = status
        r.json.return_value = body or {}
        return r

    def test_title_and_content_both_updated(self):
        """수정 파일의 title, 내용 블록 모두 Notion에 반영."""
        md_content = "---\ntitle: 새 제목\nsidebar_position: 1\n---\n\n## 새 내용\n"
        sync_map = {
            "page-xyz": {"file": "docs/guide/doc.md", "last_edited": "2026-01-01T00:00:00.000Z", "order": 1, "parent_id": None}
        }
        changed = {"modified": ["docs/guide/doc.md"], "added": [], "deleted": []}

        block_list_resp = self._make_response(body={"results": [{"id": "blk-old"}], "has_more": False})
        last_edited_resp = self._make_response(body={"last_edited_time": "2026-01-02T00:00:00.000Z"})

        patch_calls = []

        def fake_patch(url, **kwargs):
            patch_calls.append((url, kwargs))
            return self._make_response()

        with patch.object(m, "load_sync_map", return_value=sync_map), \
             patch.object(m, "get_changed_files", return_value=changed), \
             patch.object(m, "save_sync_map"), \
             patch.object(m.REPO_DIR / "docs/guide/doc.md", "read_text",
                          create=True, return_value=md_content) if False else \
             patch("builtins.open", create=True), \
             patch.object(Path, "read_text", return_value=md_content), \
             patch("requests.patch", side_effect=fake_patch), \
             patch("requests.get", return_value=block_list_resp) as mock_get, \
             patch("requests.delete", return_value=self._make_response()) as mock_delete, \
             patch("time.sleep"):

            # get_page_last_edited도 requests.get 사용 — 별도 응답 필요
            mock_get.side_effect = [block_list_resp, last_edited_resp]
            m.process_section("docs/guide")

        urls = [c[0] for c in patch_calls]

        title_call = next((c for c in patch_calls if "/pages/page-xyz" in c[0] and "제목" in str(c[1])), None)
        assert title_call is not None, "update_page_title 호출 없음"
        title_val = title_call[1]["json"]["properties"]["제목"]["title"][0]["text"]["content"]
        assert title_val == "새 제목"

        children_call = next((c for c in patch_calls if "/blocks/page-xyz/children" in c[0]), None)
        assert children_call is not None, "append_blocks 호출 없음"
        blocks = children_call[1]["json"]["children"]
        assert any(b["type"] == "heading_2" for b in blocks), "heading_2 블록 없음"

        mock_delete.assert_called()  # 기존 블록 삭제 확인
