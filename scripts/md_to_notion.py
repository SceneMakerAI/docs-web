"""
md_to_notion.py — docs/*.md 변경 감지 → Notion DB 업로드

Env vars (필수):
  NOTION_TOKEN          Notion API 토큰

Env vars (선택):
  SAVE_DIR              처리할 섹션 경로 (기본: 모든 섹션)

사용법:
  source .env && python3 scripts/md_to_notion.py
  source .env && SAVE_DIR=docs/about python3 scripts/md_to_notion.py
"""
import json
import os
import re
import subprocess
import time
from pathlib import Path

import requests

REPO_DIR = Path(__file__).parent.parent

# .env 파일 자동 로드 (미설정 키만 주입)
_env_file = REPO_DIR / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _v = _line.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip())

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

SECTION_DIRS = [
    "docs/about",
    "docs/architecture",
    "docs/blog",
    "docs/contribute",
    "docs/guide",
    "docs/install",
    "docs/poc",
    "docs/release-notes",
]

SECTION_DB_MAP = {
    "docs/about":         os.environ.get("NOTION_ABOUT", ""),
    "docs/architecture":  os.environ.get("NOTION_ARCHITECTURE", ""),
    "docs/blog":          os.environ.get("NOTION_BLOG", ""),
    "docs/contribute":    os.environ.get("NOTION_CONTRIBUTE", ""),
    "docs/guide":         os.environ.get("NOTION_DOCS", ""),
    "docs/install":       os.environ.get("NOTION_INSTALL", ""),
    "docs/poc":           os.environ.get("NOTION_POC", ""),
    "docs/release-notes": os.environ.get("NOTION_RELEASE", ""),
}

_LANG_MAP = {
    "text": "plain text", "txt": "plain text",
    "cpp": "c++", "csharp": "c#", "fsharp": "f#",
}


def log(msg: str):
    print(f"[md_to_notion] {msg}", flush=True)


# ── Frontmatter ──────────────────────────────────────────────────────────────

def parse_frontmatter(text: str) -> tuple[dict, str]:
    """YAML frontmatter 분리. (fm_dict, body) 반환."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        return {}, text
    fm: dict = {}
    for line in m.group(1).splitlines():
        kv = line.split(":", 1)
        if len(kv) == 2:
            k, v = kv[0].strip(), kv[1].strip().strip('"')
            fm[k] = v
    body = text[m.end():]
    return fm, body


# ── Inline MD → Notion rich_text ─────────────────────────────────────────────

def _make_rt(text: str, bold=False, italic=False, code=False, href=None) -> dict:
    rt: dict = {
        "type": "text",
        "text": {"content": text},
        "annotations": {
            "bold": bold, "italic": italic, "code": code,
            "strikethrough": False, "underline": False, "color": "default",
        },
    }
    if href:
        rt["text"]["link"] = {"url": href}
    return rt


_INLINE_RE = re.compile(
    r"(\*\*(.+?)\*\*)"        # bold
    r"|(\*(.+?)\*)"            # italic
    r"|(`(.+?)`)"              # code
    r"|(\[(.+?)\]\((.+?)\))"  # link
)


def inline_md_to_rich_text(text: str) -> list:
    """인라인 MD 패턴 → Notion rich_text 객체 배열."""
    result = []
    last = 0
    for m in _INLINE_RE.finditer(text):
        if m.start() > last:
            result.append(_make_rt(text[last:m.start()]))
        if m.group(1):   # bold
            result.append(_make_rt(m.group(2), bold=True))
        elif m.group(3): # italic
            result.append(_make_rt(m.group(4), italic=True))
        elif m.group(5): # code
            result.append(_make_rt(m.group(6), code=True))
        elif m.group(7): # link
            result.append(_make_rt(m.group(8), href=m.group(9)))
        last = m.end()
    if last < len(text):
        result.append(_make_rt(text[last:]))
    return result or [_make_rt("")]


# ── MD body → Notion blocks ───────────────────────────────────────────────────

def _block(btype: str, **kwargs) -> dict:
    return {"object": "block", "type": btype, btype: kwargs}


def _rich_block(btype: str, text: str, **kwargs) -> dict:
    return _block(btype, rich_text=inline_md_to_rich_text(text), **kwargs)


def md_body_to_blocks(body: str) -> list:
    """MD 본문 → Notion block objects 배열 (라인 기반 파싱)."""
    blocks: list = []
    lines = body.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]

        # 코드 펜스
        if line.startswith("```"):
            lang = line[3:].strip() or "plain text"
            lang = _LANG_MAP.get(lang, lang)
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code_lines.append(lines[i])
                i += 1
            blocks.append(_block("code",
                rich_text=[_make_rt("\n".join(code_lines))],
                language=lang,
            ))
            i += 1
            continue

        # 헤딩
        if line.startswith("#### "):
            blocks.append(_rich_block("heading_3", line[5:]))
        elif line.startswith("### "):
            blocks.append(_rich_block("heading_3", line[4:]))
        elif line.startswith("## "):
            blocks.append(_rich_block("heading_2", line[3:]))
        elif line.startswith("# "):
            blocks.append(_rich_block("heading_1", line[2:]))

        # 인용
        elif line.startswith("> "):
            blocks.append(_rich_block("quote", line[2:]))

        # 구분선
        elif re.match(r"^-{3,}$|^\*{3,}$", line.strip()):
            blocks.append(_block("divider"))

        # 이미지
        elif m := re.match(r"^!\[.*?\]\((.+?)\)$", line):
            blocks.append(_block("image",
                type="external", external={"url": m.group(1)}
            ))

        # 불릿 리스트
        elif m := re.match(r"^(\s*)[-*] (.+)", line):
            indent = len(m.group(1))
            text = m.group(2)
            blk = _rich_block("bulleted_list_item", text)
            if indent > 0 and blocks and blocks[-1]["type"] == "bulleted_list_item":
                blocks[-1]["bulleted_list_item"].setdefault("children", []).append(blk)
            else:
                blocks.append(blk)

        # 번호 리스트
        elif m := re.match(r"^(\s*)\d+\. (.+)", line):
            indent = len(m.group(1))
            text = m.group(2)
            blk = _rich_block("numbered_list_item", text)
            if indent > 0 and blocks and blocks[-1]["type"] == "numbered_list_item":
                blocks[-1]["numbered_list_item"].setdefault("children", []).append(blk)
            else:
                blocks.append(blk)

        # 빈 줄 스킵
        elif line.strip() == "":
            pass

        # 일반 단락
        else:
            blocks.append(_rich_block("paragraph", line))

        i += 1

    return blocks


# ── Notion API ────────────────────────────────────────────────────────────────

def _api(method: str, path: str, **kwargs):
    url = f"https://api.notion.com/v1{path}"
    headers = {**HEADERS, "Authorization": f"Bearer {NOTION_TOKEN}"}
    r = getattr(requests, method)(url, headers=headers, **kwargs)
    if r.status_code not in (200, 204):
        log(f"  API 오류 {r.status_code}: {path} — {r.text[:200]}")
    return r


def get_child_block_ids(page_id: str) -> list[str]:
    """페이지의 최상위 블록 ID 목록 조회 (페이징)."""
    ids = []
    params: dict = {}
    while True:
        r = _api("get", f"/blocks/{page_id}/children", params=params)
        data = r.json()
        for b in data.get("results", []):
            ids.append(b["id"])
        if not data.get("has_more"):
            break
        params = {"start_cursor": data["next_cursor"]}
    return ids


def delete_block(block_id: str):
    _api("delete", f"/blocks/{block_id}")
    time.sleep(0.35)  # Notion 레이트 리밋 (3 req/s)


def append_blocks(page_id: str, blocks: list):
    """blocks를 100개 단위로 나눠 페이지에 추가."""
    for i in range(0, len(blocks), 100):
        chunk = blocks[i:i + 100]
        _api("patch", f"/blocks/{page_id}/children", json={"children": chunk})


def get_page_last_edited(page_id: str) -> str:
    r = _api("get", f"/pages/{page_id}")
    return r.json().get("last_edited_time", "")


def update_page_title(page_id: str, title: str):
    _api("patch", f"/pages/{page_id}", json={
        "properties": {"제목": {"title": [{"text": {"content": title}}]}}
    })


def update_page_content(page_id: str, blocks: list):
    """기존 블록 전체 삭제 후 새 블록 추가."""
    for bid in get_child_block_ids(page_id):
        delete_block(bid)
    if blocks:
        append_blocks(page_id, blocks)


def create_page(database_id: str, title: str, order: int, blocks: list) -> str:
    """Notion DB에 새 페이지 생성. page_id 반환."""
    payload = {
        "parent": {"database_id": database_id},
        "properties": {
            "제목": {"title": [{"text": {"content": title}}]},
        },
        "children": blocks[:100],
    }
    r = _api("post", "/pages", json=payload)
    page_id = r.json().get("id", "")
    if page_id and len(blocks) > 100:
        append_blocks(page_id, blocks[100:])
    return page_id


def archive_page(page_id: str):
    _api("patch", f"/pages/{page_id}", json={"archived": True})


# ── Sync map ──────────────────────────────────────────────────────────────────

def load_sync_map(section_dir: str) -> dict:
    sync_file = REPO_DIR / section_dir / ".notion-sync.json"
    if not sync_file.exists():
        return {}
    with open(sync_file, encoding="utf-8") as f:
        return json.load(f)


def save_sync_map(section_dir: str, sync_map: dict):
    sync_file = REPO_DIR / section_dir / ".notion-sync.json"
    with open(sync_file, "w", encoding="utf-8") as f:
        json.dump(sync_map, f, ensure_ascii=False, indent=2)


def file_to_page_id(sync_map: dict, filepath: str) -> str | None:
    for page_id, entry in sync_map.items():
        if entry.get("file") == filepath:
            return page_id
    return None


# ── Git diff ──────────────────────────────────────────────────────────────────

def get_changed_files(section_dir: str) -> dict[str, list[str]]:
    result = {"modified": [], "added": [], "deleted": []}
    before = os.environ.get("GIT_BEFORE", "")
    after  = os.environ.get("GIT_AFTER", "HEAD")
    if not before or before == "0" * 40:
        before = "HEAD~1"
    try:
        out = subprocess.check_output(
            ["git", "-c", "core.quotepath=false", "diff", "--name-status",
             before, after, "--", section_dir],
            cwd=REPO_DIR, text=True,
        )
    except subprocess.CalledProcessError:
        log(f"git diff 실패 — {section_dir} 스킵")
        return result

    for line in out.strip().splitlines():
        if not line:
            continue
        parts = line.split("\t", 1)
        if len(parts) < 2:
            continue
        status, filepath = parts[0][0], parts[1]
        if not filepath.endswith(".md"):
            continue
        if status == "M":
            result["modified"].append(filepath)
        elif status == "A":
            result["added"].append(filepath)
        elif status == "D":
            result["deleted"].append(filepath)
    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def process_section(section_dir: str):
    sync_map = load_sync_map(section_dir)
    changed = get_changed_files(section_dir)
    total = sum(len(v) for v in changed.values())
    if total == 0:
        log(f"{section_dir}: 변경 없음")
        return

    log(f"{section_dir}: 수정 {len(changed['modified'])}개 / 신규 {len(changed['added'])}개 / 삭제 {len(changed['deleted'])}개")
    sync_dirty = False

    # 수정
    for filepath in changed["modified"]:
        page_id = file_to_page_id(sync_map, filepath)
        if not page_id:
            log(f"  [수정] {filepath} → sync_map 미등록, 스킵")
            continue
        text = (REPO_DIR / filepath).read_text(encoding="utf-8")
        fm, body = parse_frontmatter(text)
        title = fm.get("title", Path(filepath).stem)
        blocks = md_body_to_blocks(body)
        log(f"  [수정] {filepath} → {len(blocks)}개 블록 업로드 중...")
        update_page_title(page_id, title)
        update_page_content(page_id, blocks)
        sync_map[page_id]["last_edited"] = get_page_last_edited(page_id)
        sync_dirty = True
        log(f"  [수정] 완료: {filepath}")

    # 신규
    for filepath in changed["added"]:
        db_id = SECTION_DB_MAP.get(section_dir, "")
        if not db_id:
            log(f"  [신규] {filepath} → DATABASE_ID 없음, 스킵")
            continue
        text = (REPO_DIR / filepath).read_text(encoding="utf-8")
        fm, body = parse_frontmatter(text)
        title = fm.get("title", Path(filepath).stem)
        order = int(fm.get("sidebar_position", 99))
        blocks = md_body_to_blocks(body)
        log(f"  [신규] {filepath} → '{title}' 페이지 생성 중...")
        page_id = create_page(db_id, title, order, blocks)
        if page_id:
            sync_map[page_id] = {
                "file": filepath,
                "last_edited": get_page_last_edited(page_id),
                "order": order,
                "parent_id": None,
            }
            sync_dirty = True
            log(f"  [신규] 완료: page_id={page_id}")
        else:
            log(f"  [신규] 실패: {filepath}")

    # 삭제
    for filepath in changed["deleted"]:
        page_id = file_to_page_id(sync_map, filepath)
        if not page_id:
            log(f"  [삭제] {filepath} → sync_map 미등록, 스킵")
            continue
        # index.md가 삭제됐어도 해당 디렉토리가 여전히 존재하면 Notion 카테고리 페이지를 보존
        # (슬러그 수정 등 로컬 구조 변경이 원인인 경우 Notion 페이지를 실수로 archive하는 것을 방지)
        if Path(filepath).name == "index.md" and (REPO_DIR / Path(filepath).parent).is_dir():
            log(f"  [삭제] {filepath} → 카테고리 디렉토리 존재, Notion 페이지 보존")
            del sync_map[page_id]
            sync_dirty = True
            continue
        log(f"  [삭제] {filepath} → 아카이브 중...")
        archive_page(page_id)
        del sync_map[page_id]
        sync_dirty = True
        log(f"  [삭제] 완료: {filepath}")

    if sync_dirty:
        save_sync_map(section_dir, sync_map)


def main():
    if not NOTION_TOKEN:
        log("오류: NOTION_TOKEN 미설정")
        return

    save_dir = os.environ.get("SAVE_DIR", "")
    sections = [save_dir] if save_dir else SECTION_DIRS

    for section in sections:
        process_section(section)


if __name__ == "__main__":
    main()
