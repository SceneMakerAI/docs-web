"""
contrib_sync.py — GitHub 기여(PR·Issue·Discussion) ↔ Notion '오픈소스 생태계 기여' 페이지의 표

표는 NOTION_DISCUSSION DB 의 페이지 본문에 있고 열은 고정이다:
  번호 | 유형 | 리포 | 제목(GitHub 링크) | 작성자 | 참여자 | 상태

Env vars (필수):
  NOTION_TOKEN          Notion API 토큰
  NOTION_DISCUSSION     표가 들어 있는 페이지의 DB ID

Env vars (선택):
  NOTION_CONTRIBUTE     기여 상세 글 DB ID (--body-file 사용 시 필수)
  GITHUB_TOKEN          GitHub 토큰 (없으면 `gh auth token`)

사용법:
  python3 scripts/contrib_sync.py status [--dry-run]
      제목에 GitHub 링크가 있는 행의 상태 칸을 GitHub 현재 값으로 맞춘다
      (server-sync.sh 가 6시간마다 실행).
  python3 scripts/contrib_sync.py add <GitHub URL> [--title 제목] [--body-file 글.md]
      PR·Issue·Discussion 을 올린 직후 표에 행으로 등록한다. 같은 링크의 행이 있으면 갱신한다.
      --body-file 을 주면 상세 글도 올린다.
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts import md_to_notion as notion  # noqa: E402  (.env 로드 포함)

COL_TITLE, COL_STATUS = 3, 6

_URL_KINDS = {"pull": "PR", "issues": "Issue", "discussions": "Discussion"}
_API_PATHS = {"PR": "pulls", "Issue": "issues", "Discussion": "discussions"}
_GITHUB_URL = re.compile(r"^https://github\.com/([^/]+)/([^/]+)/(pull|issues|discussions)/(\d+)")


def log(msg: str):
    print(msg, flush=True)


# ── 순수 변환 ─────────────────────────────────────────────────────────────────

def parse_github_url(url):
    """GitHub 기여 URL → (owner, repo, 유형, 번호). 기여 URL 이 아니면 None."""
    m = _GITHUB_URL.match(url or "")
    if not m:
        return None
    owner, repo, kind, number = m.groups()
    return owner, repo, _URL_KINDS[kind], int(number)


def status_label(kind: str, gh: dict) -> str:
    """GitHub 응답 → 표의 상태 칸 값."""
    if kind == "Discussion":
        return "Posted"
    if kind == "PR" and gh.get("merged_at"):
        return "Merged"
    return "Open" if gh.get("state") == "open" else "Closed"


def participants(author: str, users) -> str:
    """(login, type) 목록 → 작성자·봇을 뺀 참여자를 처음 나온 순서로."""
    seen = []
    for login, user_type in users:
        if login != author and user_type != "Bot" and login not in seen:
            seen.append(login)
    return ", ".join(seen)


def _cell(text, url=None):
    if not text:
        return []
    return [{"type": "text", "text": {"content": text, "link": {"url": url} if url else None}}]


def row_cells(number, kind, repo, title, url, author, participants, status) -> list:
    """표 한 행의 칸 7개. number 는 표 안의 일련번호."""
    return [_cell(str(number)), _cell(kind), _cell(repo), _cell(title, url),
            _cell(author), _cell(participants), _cell(status)]


def _writable(cell):
    """조회 응답의 rich_text → 다시 써넣을 수 있는 모양 (링크·서식 유지)."""
    return [{"type": "text",
             "text": {"content": t["plain_text"], "link": {"url": t["href"]} if t.get("href") else None},
             "annotations": t["annotations"]} for t in cell]


def _cell_text(cell):
    return "".join(t["plain_text"] for t in cell)


def _written_text(cell):
    return "".join(t["text"]["content"] for t in cell)


def _row_url(row):
    for t in row["table_row"]["cells"][COL_TITLE]:
        if t.get("href"):
            return t["href"]
    return None


def plan_status_updates(rows, fetch) -> list:
    """상태가 달라진 행만 (block_id, 새 칸 목록, 이전, 이후) 로 돌려준다. 조회 실패한 행은 건너뛴다."""
    updates = []
    for row in rows:
        parsed = parse_github_url(_row_url(row))
        if not parsed:
            continue
        owner, repo, kind, number = parsed
        try:
            new = status_label(kind, fetch(owner, repo, kind, number))
        except Exception as e:
            log(f"  조회 실패 {owner}/{repo}#{number}: {e}")
            continue
        cells = row["table_row"]["cells"]
        old = _cell_text(cells[COL_STATUS])
        if new != old:
            new_cells = [_writable(c) for c in cells]
            new_cells[COL_STATUS] = _cell(new)
            updates.append((row["id"], new_cells, old, new))
    return updates


def next_number(rows) -> int:
    """새 행에 줄 일련번호 — 표에 있는 가장 큰 번호 다음."""
    numbers = [int(text) for row in rows
               if (text := _cell_text(row["table_row"]["cells"][0])).isdigit()]
    return max(numbers, default=0) + 1


def find_row(rows, url):
    """같은 GitHub 링크를 가진 행의 block_id. 없으면 None."""
    for row in rows:
        if _row_url(row) == url:
            return row["id"]
    return None


# ── GitHub ────────────────────────────────────────────────────────────────────

def github_token() -> str:
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        token = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True).stdout.strip()
    return token


def _github_get(path: str, params=None):
    headers = {"Accept": "application/vnd.github+json"}
    token = github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.get(f"https://api.github.com{path}", headers=headers, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_github(owner, repo, kind, number) -> dict:
    return _github_get(f"/repos/{owner}/{repo}/{_API_PATHS[kind]}/{number}")


def fetch_participants(owner, repo, kind, number, gh) -> str:
    """댓글·리뷰를 남긴 사람과 머지·종료한 사람."""
    base = f"/repos/{owner}/{repo}"
    thread = "discussions" if kind == "Discussion" else "issues"
    people = _github_get(f"{base}/{thread}/{number}/comments", {"per_page": 100})
    if kind == "PR":
        people += _github_get(f"{base}/pulls/{number}/reviews", {"per_page": 100})
    users = [p["user"] for p in people] + [gh.get("merged_by"), gh.get("closed_by")]
    return participants(gh["user"]["login"], [(u["login"], u["type"]) for u in users if u])


# ── Notion ────────────────────────────────────────────────────────────────────

def _children(block_id: str) -> list:
    results, params = [], {"page_size": 100}
    while True:
        r = notion._api("get", f"/blocks/{block_id}/children", params=params)
        r.raise_for_status()
        data = r.json()
        results += data["results"]
        if not data.get("has_more"):
            return results
        params["start_cursor"] = data["next_cursor"]


def load_table(database_id: str):
    """DB 의 페이지들에서 첫 표를 찾아 (table_id, 머리행을 뺀 행 목록) 을 돌려준다."""
    r = notion._api("post", f"/databases/{database_id}/query", json={"page_size": 100})
    r.raise_for_status()
    for page in r.json()["results"]:
        for block in _children(page["id"]):
            if block["type"] == "table":
                return block["id"], _children(block["id"])[1:]
    sys.exit("기여 표를 찾지 못함 — NOTION_DISCUSSION 페이지에 표가 있는지 확인")


def update_row(block_id: str, cells: list):
    notion._api("patch", f"/blocks/{block_id}", json={"table_row": {"cells": cells}}).raise_for_status()


def append_row(table_id: str, cells: list):
    notion._api("patch", f"/blocks/{table_id}/children", json={
        "children": [{"type": "table_row", "table_row": {"cells": cells}}]}).raise_for_status()


def create_article(database_id: str, title: str, kind: str, body_md: str) -> str:
    """기여 상세 글 DB 에 본문 페이지를 만든다."""
    blocks = notion.md_body_to_blocks(body_md)
    r = notion._api("post", "/pages", json={
        "parent": {"database_id": database_id},
        "properties": {
            "제목": {"title": [{"text": {"content": title}}]},
            "tags": {"multi_select": [{"name": kind}]},
        },
        "children": blocks[:100],
    })
    r.raise_for_status()
    page_id = r.json()["id"]
    if len(blocks) > 100:
        notion.append_blocks(page_id, blocks[100:])
    return page_id


# ── 명령 ──────────────────────────────────────────────────────────────────────

def cmd_status(args):
    _, rows = load_table(os.environ["NOTION_DISCUSSION"])
    updates = plan_status_updates(rows, fetch_github)
    for block_id, cells, old, new in updates:
        log(f"  {_written_text(cells[COL_TITLE])}: {old} → {new}")
        if not args.dry_run:
            update_row(block_id, cells)
    log(f"[기여 상태] {len(rows)}행 중 {len(updates)}건 변경" + (" (dry-run)" if args.dry_run else ""))


def cmd_add(args):
    parsed = parse_github_url(args.url)
    if not parsed:
        sys.exit(f"GitHub PR·Issue·Discussion URL 이 아님: {args.url}")
    owner, repo, kind, number = parsed
    gh = fetch_github(owner, repo, kind, number)
    table_id, rows = load_table(os.environ["NOTION_DISCUSSION"])
    existing = find_row(rows, gh["html_url"])
    title = args.title or gh["title"]
    number = next_number(rows)
    if existing:
        row = next(r for r in rows if r["id"] == existing)
        number = _cell_text(row["table_row"]["cells"][0]) or number
        if not args.title:
            title = _cell_text(row["table_row"]["cells"][COL_TITLE])
    cells = row_cells(number=number, kind=kind, repo=repo, title=title, url=gh["html_url"],
                      author=gh["user"]["login"],
                      participants=fetch_participants(owner, repo, kind, number, gh),
                      status=status_label(kind, gh))
    if existing:
        update_row(existing, cells)
    else:
        append_row(table_id, cells)
    log(f"[기여 등록] {'갱신' if existing else '추가'}: {' | '.join(_written_text(c) for c in cells)}")
    if args.body_file:
        article_id = create_article(os.environ["NOTION_CONTRIBUTE"], title, kind,
                                    Path(args.body_file).read_text(encoding="utf-8"))
        log(f"[기여 글] 추가: {article_id[:8]}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    sub = parser.add_subparsers(dest="command", required=True)
    p_status = sub.add_parser("status")
    p_status.add_argument("--dry-run", action="store_true")
    p_status.set_defaults(func=cmd_status)
    p_add = sub.add_parser("add")
    p_add.add_argument("url")
    p_add.add_argument("--title")
    p_add.add_argument("--body-file")
    p_add.set_defaults(func=cmd_add)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
