"""
notion_to_docs_generic.py — Notion DB → Docusaurus docs 섹션 동기화

Env vars (필수):
  NOTION_TOKEN          Notion API 토큰
  NOTION_DATABASE_ID    동기화할 Notion DB ID

Env vars (선택):
  SAVE_DIR              저장 경로 (기본: docs/guide)
  STATIC_IMG_DIR        이미지 저장 경로 (기본: static/img/<SAVE_DIR 마지막 세그먼트>)
  NOTION_PROPERTY_TITLE 제목 속성명 (기본: 제목)
  NOTION_PROPERTY_ORDER 순서 속성명, Number 타입 (기본: 순서)
  NOTION_PROPERTY_DATE  날짜 속성명, DAILY 모드용 (기본: 날짜)
  FETCH_MODE            ALL | DAILY (기본: ALL)
"""
import os
import re
import sys
import json
import requests
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DATABASE_ID_RAW = os.environ["NOTION_DATABASE_ID"]
SAVE_DIR = os.environ.get("SAVE_DIR", "docs/guide")
_last_seg = SAVE_DIR.rstrip("/").split("/")[-1]
STATIC_IMG_DIR = os.environ.get("STATIC_IMG_DIR", f"static/img/{_last_seg}")
NOTION_PROPERTY_TITLE = os.environ.get("NOTION_PROPERTY_TITLE", "제목")
NOTION_PROPERTY_ORDER = os.environ.get("NOTION_PROPERTY_ORDER", "순서")
NOTION_PROPERTY_DATE = os.environ.get("NOTION_PROPERTY_DATE", "날짜")
FETCH_MODE = os.environ.get("FETCH_MODE", "ALL")
TIMEZONE_HOURS = 9

SYNC_MAP_FILE = f"{SAVE_DIR}/.notion-sync.json"
# 수동 작성 구조 파일 — sync가 절대 삭제하지 않음
SKIP_FILES = {"_category_.json", "overview.mdx", "intro.mdx"}


def normalize_notion_database_id(raw):
    raw = (raw or "").strip()
    if not raw:
        return raw
    if raw.lower().startswith(("http://", "https://")):
        path = urlparse(raw).path.strip("/")
        blob = "/".join(path.split("/")[-2:]) if path else ""
    else:
        blob = raw.split("?")[0]
    found = re.findall(r"[0-9a-fA-F]{32}", blob.replace("-", ""))
    if not found:
        compact = re.sub(r"[^0-9a-fA-F]", "", blob)
        if len(compact) >= 32:
            found = [compact[:32]]
    if not found:
        return raw
    h = found[0].lower()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"


DATABASE_ID = normalize_notion_database_id(DATABASE_ID_RAW)

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}


def log(msg):
    print(f"[{SAVE_DIR}] {msg}")


def verify_database_access():
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}"
    r = requests.get(url, headers=headers)
    data = r.json()
    log(f"GET /databases/{{id}} → HTTP {r.status_code}")
    if r.status_code != 200 or data.get("object") == "error":
        log(f"ERROR: {data.get('message', data)}")
        return False
    names = list(data.get("properties", {}).keys())
    log(f"DB 속성 ({len(names)}개): {names}")
    return True


def read_title_plain(props, prop_name):
    p = props.get(prop_name, {})
    if p.get("type") != "title":
        return None
    inner = p.get("title", [])
    try:
        return inner[0]["plain_text"]
    except (IndexError, KeyError, TypeError):
        return None


def read_number(props, prop_name):
    p = props.get(prop_name, {})
    if p.get("type") != "number":
        return None
    return p.get("number")


def read_date_start(props, prop_name):
    p = props.get(prop_name, {})
    if p.get("type") != "date":
        return None
    inner = p.get("date")
    if not inner:
        return None
    start = inner.get("start", "")
    return start[:10] if len(start) >= 10 else None


def get_page_blocks(page_id):
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    blocks = []
    params = {}
    while True:
        data = requests.get(url, headers=headers, params=params).json()
        results = data.get("results", [])
        for block in results:
            if block.get("has_children"):
                block["_children"] = get_page_blocks(block["id"])
        blocks.extend(results)
        if not data.get("has_more"):
            break
        params = {"start_cursor": data["next_cursor"]}
    return blocks


def extract_text_from_rich_text(rich_text_list):
    parts = []
    for text in rich_text_list:
        plain = text["plain_text"]
        ann = text.get("annotations", {})
        href = text.get("href")

        if ann.get("code"):
            formatted = f"`{plain}`" if plain.strip() else plain
        else:
            formatted = plain
            if plain.strip():
                if ann.get("bold") and ann.get("italic"):
                    formatted = f"***{formatted}***"
                elif ann.get("bold"):
                    formatted = f"**{formatted}**"
                elif ann.get("italic"):
                    formatted = f"*{formatted}*"
                if ann.get("strikethrough"):
                    formatted = f"~~{formatted}~~"

        parts.append(f"[{formatted}]({href})" if href else formatted)

    result = ""
    for part in parts:
        if result and result[-1] not in (" ", "\n") and part and part[0] not in (" ", "\n"):
            if result.endswith(")") or result[-1].isalnum() or result[-1] in ("`", "*", "~"):
                result += " "
        result += part
    return result


def download_image(url: str, slug: str, index: int) -> str:
    save_dir = f"{STATIC_IMG_DIR}/{slug}"
    os.makedirs(save_dir, exist_ok=True)
    parsed = urlparse(url)
    ext = os.path.splitext(parsed.path)[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"):
        ext = ".jpg"
    filename = f"img-{index:02d}{ext}"
    filepath = f"{save_dir}/{filename}"
    if not os.path.exists(filepath):
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        with open(filepath, "wb") as f:
            f.write(r.content)
        log(f"이미지 저장: {filepath}")
    else:
        log(f"이미지 캐시: {filepath}")
    return f"/img/{_last_seg}/{slug}/{filename}"


def block_to_markdown(block, slug, image_counter):
    b_type = block["type"]
    children = block.get("_children", [])

    def render_children():
        return "".join(block_to_markdown(c, slug, image_counter) for c in children)

    if b_type == "table":
        if not children:
            return ""
        lines = []
        for i, row in enumerate(children):
            cells = row.get("table_row", {}).get("cells", [])
            row_text = " | ".join(extract_text_from_rich_text(cell) for cell in cells)
            lines.append(f"| {row_text} |")
            if i == 0:
                sep = " | ".join("---" for _ in cells)
                lines.append(f"| {sep} |")
        return "\n".join(lines) + "\n\n"

    elif b_type in ("column_list", "column"):
        return render_children()

    elif b_type in (
        "paragraph", "heading_1", "heading_2", "heading_3",
        "bulleted_list_item", "numbered_list_item", "to_do",
        "toggle", "quote", "callout",
    ):
        rich_text = block[b_type].get("rich_text", [])
        content = extract_text_from_rich_text(rich_text)
        child_md = render_children()
        if b_type == "paragraph":
            return (content + "\n\n" if content else "<br />\n\n") + child_md
        elif b_type == "heading_1":
            return f"## {content}\n\n" + child_md
        elif b_type == "heading_2":
            return f"### {content}\n\n" + child_md
        elif b_type == "heading_3":
            return f"#### {content}\n\n" + child_md
        elif b_type == "bulleted_list_item":
            return f"- {content}\n\n" + child_md
        elif b_type == "numbered_list_item":
            return f"1. {content}\n\n" + child_md
        elif b_type == "to_do":
            checked = "[x]" if block["to_do"]["checked"] else "[ ]"
            return f"- {checked} {content}\n\n" + child_md
        elif b_type in ("quote", "callout"):
            icon = ""
            if b_type == "callout":
                icon_data = block.get("callout", {}).get("icon", {})
                icon = icon_data.get("emoji", "")
            prefix = f"{icon} " if icon else ""
            if child_md:
                child_quoted = "\n".join(
                    f"> {line}" if line.strip() else ">"
                    for line in child_md.rstrip("\n").splitlines()
                )
                return f"> {prefix}{content}\n>\n{child_quoted}\n\n"
            return f"> {prefix}{content}\n\n"
        elif b_type == "toggle":
            if child_md:
                return f"<details>\n<summary>{content}</summary>\n\n{child_md}\n</details>\n\n"
            return f"- {content}\n"

    elif b_type == "table_row":
        return ""  # table 블록 내부에서만 처리

    elif b_type == "code":
        language = block["code"].get("language", "text")
        content = extract_text_from_rich_text(block["code"].get("rich_text", []))
        return f"```{language}\n{content}\n```\n\n"

    elif b_type == "image":
        url = (
            block["image"].get("file", {}).get("url")
            or block["image"].get("external", {}).get("url")
            or ""
        )
        if not url:
            return ""
        try:
            local_path = download_image(url, slug, image_counter[0])
            image_counter[0] += 1
            return f"![image]({local_path})\n\n"
        except Exception as e:
            log(f"WARN: 이미지 다운로드 실패 ({url[:60]}...): {e}")
            return f"![image]({url})\n\n"

    elif b_type == "divider":
        return "---\n\n"

    return ""


def escape_mdx_angle_brackets(text):
    """<한글> 같이 비 ASCII를 포함한 꺾쇠 패턴을 MDX가 태그로 해석하지 않도록 이스케이프."""
    return re.sub(r'<([^>]*[^\x00-\x7F][^>]*)>', r'&lt;\1&gt;', text)


def blocks_to_markdown(blocks, slug):
    image_counter = [0]
    body = "".join(block_to_markdown(b, slug, image_counter) for b in blocks)
    return escape_mdx_angle_brackets(body)


def slugify(title):
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    return slug or "page"


def load_sync_map():
    if not os.path.exists(SYNC_MAP_FILE):
        return {}
    with open(SYNC_MAP_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_sync_map(mapping):
    os.makedirs(SAVE_DIR, exist_ok=True)
    with open(SYNC_MAP_FILE, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)


def save_doc_page(page, position, existing_map):
    page_id = page["id"]
    props = page.get("properties", {})
    title = read_title_plain(props, NOTION_PROPERTY_TITLE) or "제목없음"
    order = read_number(props, NOTION_PROPERTY_ORDER)
    if order is None:
        order = position  # Notion DB 순서를 그대로 사용

    slug = slugify(title)
    new_filename = f"{SAVE_DIR}/{slug}.md"

    old_filename = existing_map.get(page_id)
    if old_filename and old_filename != new_filename:
        for candidate in [old_filename, old_filename.replace(".md", ".mdx")]:
            if os.path.exists(candidate):
                os.remove(candidate)
                log(f"이름 변경으로 기존 파일 삭제: {candidate}")

    blocks = get_page_blocks(page_id)
    body = blocks_to_markdown(blocks, slug)

    safe_title = title.replace('"', '\\"')
    frontmatter = (
        f"---\n"
        f"id: {slug}\n"
        f'title: "{safe_title}"\n'
        f"sidebar_position: {order}\n"
        f"---\n\n"
    )

    os.makedirs(SAVE_DIR, exist_ok=True)
    with open(new_filename, "w", encoding="utf-8") as f:
        f.write(frontmatter + body)

    return title, new_filename


def remove_orphans(synced_files, previously_tracked):
    """이전 sync에서 Notion이 만든 파일 중 이번에 사라진 것만 삭제.
    수동 작성 파일(sync map에 없던 파일)은 건드리지 않는다."""
    if not os.path.isdir(SAVE_DIR):
        return
    for fname in os.listdir(SAVE_DIR):
        if fname in SKIP_FILES or fname.startswith("."):
            continue
        if not (fname.endswith(".md") or fname.endswith(".mdx")):
            continue
        fpath = os.path.join(SAVE_DIR, fname)
        if fpath in previously_tracked and fpath not in synced_files:
            os.remove(fpath)
            log(f"미추적 파일 삭제: {fpath}")


def main():
    if not verify_database_access():
        sys.exit(1)

    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    payload = {}

    if FETCH_MODE == "DAILY":
        kst = timezone(timedelta(hours=TIMEZONE_HOURS))
        target_date = (datetime.now(kst) - timedelta(days=1)).strftime("%Y-%m-%d")
        log(f"[모드: 일간] {target_date} 조회")
        payload["filter"] = {
            "property": NOTION_PROPERTY_DATE,
            "date": {"equals": target_date},
        }
    else:
        log("[모드: 전체] 모든 페이지 조회")

    existing_map = load_sync_map()
    log(f"기존 파일 {len(existing_map)}개 추적 중")

    has_more = True
    next_cursor = None
    saved = 0
    position = 1
    synced_files = set()

    while has_more:
        if next_cursor:
            payload["start_cursor"] = next_cursor
        res = requests.post(url, headers=headers, json=payload)
        data = res.json()
        if res.status_code != 200 or data.get("object") == "error":
            log(f"ERROR: {data.get('message', data)}")
            sys.exit(1)

        pages = data.get("results", [])
        log(f"페이지 수: {len(pages)}")

        for page in pages:
            title, filepath = save_doc_page(page, position, existing_map)
            existing_map[page["id"]] = filepath
            synced_files.add(filepath)
            log(f"저장: {filepath} ({title})")
            saved += 1
            position += 1

        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor")

    if FETCH_MODE != "DAILY":
        previously_tracked = set(existing_map.values())
        remove_orphans(synced_files, previously_tracked)
        existing_map = {k: v for k, v in existing_map.items() if v in synced_files}

    save_sync_map(existing_map)
    log(f"완료: {saved}개 저장")


if __name__ == "__main__":
    main()
