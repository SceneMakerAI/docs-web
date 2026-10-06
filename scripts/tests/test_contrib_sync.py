"""
contrib_sync.py — GitHub 기여(PR·Issue·Discussion) ↔ Notion '오픈소스 생태계 기여' 페이지의 표
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import scripts.contrib_sync as c


def _text(content, href=None):
    """Notion 이 조회 응답으로 돌려주는 rich_text 조각."""
    return {
        "type": "text",
        "text": {"content": content, "link": {"url": href} if href else None},
        "annotations": {"bold": False, "italic": False, "strikethrough": False,
                        "underline": False, "code": False, "color": "default"},
        "plain_text": content,
        "href": href,
    }


def _table_row(block_id, number, kind, repo, title, url, author, participants, status):
    cells = [[_text(number)], [_text(kind)], [_text(repo)], [_text(title, url)],
             [_text(author)], [_text(participants)] if participants else [], [_text(status)]]
    return {"id": block_id, "type": "table_row", "table_row": {"cells": cells}}


HEADER = {"id": "h", "type": "table_row", "table_row": {"cells": [
    [_text(x)] for x in ("번호", "유형", "리포", "제목", "작성자", "참여자", "상태")]}}


def _plain(cells):
    return ["".join(t["text"]["content"] for t in cell) for cell in cells]


class TestParseGithubUrl:

    def test_pull_request(self):
        assert c.parse_github_url("https://github.com/vllm-project/vllm/pull/48084") == (
            "vllm-project", "vllm", "PR", 48084)

    def test_issue(self):
        assert c.parse_github_url("https://github.com/vllm-project/vllm/issues/44538") == (
            "vllm-project", "vllm", "Issue", 44538)

    def test_discussion(self):
        assert c.parse_github_url("https://github.com/SceneMakerAI/docs-web/discussions/31") == (
            "SceneMakerAI", "docs-web", "Discussion", 31)

    def test_trailing_fragment_and_path_are_ignored(self):
        assert c.parse_github_url(
            "https://github.com/vllm-project/vllm/pull/48084/files#issuecomment-1") == (
            "vllm-project", "vllm", "PR", 48084)

    def test_non_contribution_url_is_none(self):
        assert c.parse_github_url("https://github.com/vllm-project/vllm") is None
        assert c.parse_github_url("https://www.notion.so/abc") is None
        assert c.parse_github_url(None) is None


class TestStatusLabel:

    def test_open_pr(self):
        assert c.status_label("PR", {"state": "open", "merged_at": None}) == "Open"

    def test_merged_pr(self):
        gh = {"state": "closed", "merged_at": "2026-07-08T03:12:45Z"}
        assert c.status_label("PR", gh) == "Merged"

    def test_closed_unmerged_pr(self):
        assert c.status_label("PR", {"state": "closed", "merged_at": None}) == "Closed"

    def test_open_issue(self):
        assert c.status_label("Issue", {"state": "open"}) == "Open"

    def test_closed_issue(self):
        assert c.status_label("Issue", {"state": "closed", "state_reason": "not_planned"}) == "Closed"

    def test_discussion_is_posted(self):
        assert c.status_label("Discussion", {"state": "open"}) == "Posted"


class TestParticipants:

    def test_author_and_bots_are_excluded(self):
        users = [("sungbin1015", "User"), ("mergify[bot]", "Bot"), ("DarkLight1337", "User"),
                 ("github-actions[bot]", "Bot")]
        assert c.participants("sungbin1015", users) == "DarkLight1337"

    def test_each_person_listed_once_in_first_seen_order(self):
        users = [("b", "User"), ("a", "User"), ("b", "User")]
        assert c.participants("me", users) == "b, a"

    def test_nobody_else_is_empty(self):
        assert c.participants("me", [("me", "User")]) == ""


class TestRowCells:

    def test_cells_follow_the_page_table_columns(self):
        cells = c.row_cells(number=8, kind="PR", repo="vllm",
                            title="Responses API 에 min_p 지원",
                            url="https://github.com/vllm-project/vllm/pull/48084",
                            author="sungbin1015", participants="", status="Open")
        assert _plain(cells) == ["8", "PR", "vllm", "Responses API 에 min_p 지원",
                                 "sungbin1015", "", "Open"]

    def test_only_the_title_links_to_github(self):
        cells = c.row_cells(number=8, kind="PR", repo="vllm", title="제목",
                            url="https://github.com/vllm-project/vllm/pull/48084",
                            author="a", participants="b", status="Open")
        links = [[t["text"].get("link") for t in cell] for cell in cells]
        assert links[3] == [{"url": "https://github.com/vllm-project/vllm/pull/48084"}]
        assert all(link is None for i, cell in enumerate(links) if i != 3 for link in cell)


class TestPlanStatusUpdates:

    def test_changed_status_rewrites_only_the_status_cell(self):
        row = _table_row("r1", "06.26", "PR", "vllm", "CLI 인자 검증 테스트 수정",
                         "https://github.com/vllm-project/vllm/pull/46779",
                         "sungbin1015", "DarkLight1337", "Open")
        updates = c.plan_status_updates(
            [HEADER, row], lambda *a: {"state": "closed", "merged_at": "2026-10-06T01:00:00Z"})
        assert [(u[0], u[2], u[3]) for u in updates] == [("r1", "Open", "Merged")]
        new_cells = updates[0][1]
        assert _plain(new_cells) == ["06.26", "PR", "vllm", "CLI 인자 검증 테스트 수정",
                                     "sungbin1015", "DarkLight1337", "Merged"]
        assert new_cells[3][0]["text"]["link"] == {
            "url": "https://github.com/vllm-project/vllm/pull/46779"}

    def test_unchanged_status_is_skipped(self):
        row = _table_row("r1", "07.09", "PR", "vllm", "글",
                         "https://github.com/vllm-project/vllm/pull/48084", "a", "", "Open")
        assert c.plan_status_updates([HEADER, row], lambda *a: {"state": "open", "merged_at": None}) == []

    def test_row_without_github_link_is_never_fetched(self):
        row = _table_row("r1", "10.06", "Report", "docs-web", "최종 보고서", None, "a", "", "예정")
        calls = []
        assert c.plan_status_updates([HEADER, row], lambda *a: calls.append(a)) == []
        assert calls == []

    def test_one_failing_row_does_not_block_the_rest(self):
        rows = [
            HEADER,
            _table_row("r1", "01.01", "PR", "r", "가", "https://github.com/o/r/pull/1", "a", "", "Open"),
            _table_row("r2", "01.02", "Issue", "r", "나", "https://github.com/o/r/issues/2", "a", "", "Open"),
        ]

        def fetch(owner, repo, kind, number):
            if number == 1:
                raise RuntimeError("GitHub 404")
            return {"state": "closed"}

        assert [(u[0], u[3]) for u in c.plan_status_updates(rows, fetch)] == [("r2", "Closed")]


class TestFindRow:

    def test_row_with_same_link_is_found(self):
        rows = [HEADER, _table_row("r1", "01.01", "PR", "r", "가",
                                   "https://github.com/o/r/pull/1", "a", "", "Open")]
        assert c.find_row(rows, "https://github.com/o/r/pull/1") == "r1"

    def test_unknown_link_means_new_row(self):
        assert c.find_row([HEADER], "https://github.com/o/r/pull/1") is None


class TestNextNumber:

    def test_follows_the_largest_number_in_the_table(self):
        rows = [HEADER, _table_row("r1", "1", "PR", "vllm", "a", None, "x", "", "Open"),
                _table_row("r2", "2", "Issue", "sm_db", "b", None, "x", "", "Open")]
        assert c.next_number(rows) == 3

    def test_empty_table_starts_at_one(self):
        assert c.next_number([HEADER]) == 1

    def test_non_numeric_first_cells_are_ignored(self):
        rows = [HEADER, _table_row("r1", "06.04", "PR", "vllm", "a", None, "x", "", "Open"),
                _table_row("r2", "5", "PR", "vllm", "b", None, "x", "", "Open")]
        assert c.next_number(rows) == 6
