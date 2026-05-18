import os
import re
import sys
import requests
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta

SAVE_DIR = "docs/contribute"
STATIC_IMG_DIR = "static/img/contribute"
OVERVIEW_FILE = f"{SAVE_DIR}/overview.md"
SKIP_FILES = {"overview.md", "TEMPLATE.md"}

NOTION_PROPERTY_TITLE = os.environ.get("NOTION_PROPERTY_TITLE", "제목")
NOTION_PROPERTY_DATE = os.environ.get("NOTION_PROPERTY_DATE", "날짜")
NOTION_PROPERTY_PROJECT = os.environ.get("NOTION_PROPERTY_PROJECT", "프로젝트")
NOTION_PROPERTY_TYPE = os.environ.get("NOTION_PROPERTY_TYPE", "유형")
NOTION_PROPERTY_STATUS = os.environ.get("NOTION_PROPERTY_STATUS", "상태")
NOTION_PROPERTY_URL = os.environ.get("NOTION_PROPERTY_URL", "URL")
NOTION_PROPERTY_NUMBER = os.environ.get("NOTION_PROPERTY_NUMBER", "번호")


def normalize_notion_database_id(raw):
    raw = (raw or "").strip()
    if not raw:
        return raw
    if raw.lower().startswith(("http://", "https://")):
        from urllib.parse import urlparse as _up
        path = _up(raw).path.strip("/")
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


NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DATABASE_ID = normalize_notion_database_id(os.environ["NOTION_CONTRIBUTE_DATABASE_ID"])

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}


def verify_database_access():
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}"
    r = requests.get(url, headers=headers)
    data = r.json()
    print(f">> GET /databases/{{id}} → HTTP {r.status_code}")
    if r.status_code != 200 or data.get("object") == "error":
        print(f">> ERROR: {data.get('message', data)}")
        return False
    names = list(data.get("properties", {}).keys())
    print(f">> DB 속성 ({len(names)}개): {names}")
    return True


def read_select(props, prop_name):
    p = props.get(prop_name, {})
    ptype = p.get("type")
    if ptype == "select":
        s = p.get("select")
        return s["name"] if s else ""
    return ""


def read_url(props, prop_name):
    p = props.get(prop_name, {})
    return p.get("url") or ""


def read_number(props, prop_name):
    p = props.get(prop_name, {})
    if p.get("type") == "number":
        n = p.get("number")
        return int(n) if n is not None else None
    return None


def read_title_plain(props, prop_name):
    p = props.get(prop_name, {})
    if p.get("type") != "title":
        return None
    inner = p.get("title", [])
    try:
        return inner[0]["plain_text"]
    except (IndexError, KeyError, TypeError):
        return None


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
    return requests.get(url, headers=headers).json().get("results", [])


def extract_text(rich_text_list):
    parts = []
    for text in rich_text_list:
        plain = text["plain_text"]
        href = text.get("href")
        parts.append(f"[{plain}]({href})" if href else plain)
    return " ".join(parts)


def download_image(url, slug, index):
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
        print(f">> 이미지 저장: {filepath}")
    return f"/img/contribute/{slug}/{filename}"


def blocks_to_markdown(blocks, slug):
    image_counter = [0]
    parts = []
    for block in blocks:
        b_type = block["type"]
        if b_type in ("paragraph", "heading_1", "heading_2", "heading_3",
                      "bulleted_list_item", "numbered_list_item", "quote", "callout"):
            content = extract_text(block[b_type].get("rich_text", []))
            if not content:
                continue
            if b_type == "paragraph":
                parts.append(content + "\n\n")
            elif b_type == "heading_1":
                parts.append(f"## {content}\n\n")
            elif b_type == "heading_2":
                parts.append(f"## {content}\n\n")
            elif b_type == "heading_3":
                parts.append(f"### {content}\n\n")
            elif b_type == "bulleted_list_item":
                parts.append(f"- {content}\n")
            elif b_type == "numbered_list_item":
                parts.append(f"1. {content}\n")
            elif b_type in ("quote", "callout"):
                parts.append(f"> {content}\n\n")
        elif b_type == "code":
            lang = block["code"].get("language", "text")
            content = extract_text(block["code"].get("rich_text", []))
            parts.append(f"```{lang}\n{content}\n```\n\n")
        elif b_type == "image":
            url = (block["image"].get("file", {}).get("url")
                   or block["image"].get("external", {}).get("url") or "")
            if url:
                try:
                    local = download_image(url, slug, image_counter[0])
                    image_counter[0] += 1
                    parts.append(f"![image]({local})\n\n")
                except Exception as e:
                    print(f">> WARN: 이미지 다운로드 실패: {e}")
        elif b_type == "divider":
            parts.append("---\n\n")
    return "".join(parts)


def slugify(text):
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    return slug or "contribution"


SYNC_MAP_FILE = f"{SAVE_DIR}/.contribute-sync.json"


def load_sync_map():
    if not os.path.exists(SYNC_MAP_FILE):
        return {}
    import json
    with open(SYNC_MAP_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_sync_map(mapping):
    import json
    with open(SYNC_MAP_FILE, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)


def update_overview_count(count):
    """overview.md의 '현재: X건' 숫자를 갱신."""
    if not os.path.exists(OVERVIEW_FILE):
        return
    with open(OVERVIEW_FILE, encoding="utf-8") as f:
        content = f.read()
    updated = re.sub(r"현재: \d+건", f"현재: {count}건", content)
    if updated != content:
        with open(OVERVIEW_FILE, "w", encoding="utf-8") as f:
            f.write(updated)
        print(f">> overview.md 카운트 갱신: {count}건")


def save_contribution(page, date_str, existing_map):
    if len(date_str) > 10:
        date_str = date_str[:10]

    page_id = page["id"]
    props = page.get("properties", {})

    title = read_title_plain(props, NOTION_PROPERTY_TITLE) or "제목없음"
    project = read_select(props, NOTION_PROPERTY_PROJECT)
    contrib_type = read_select(props, NOTION_PROPERTY_TYPE)
    status = read_select(props, NOTION_PROPERTY_STATUS)
    upstream_url = read_url(props, NOTION_PROPERTY_URL)
    number = read_number(props, NOTION_PROPERTY_NUMBER)

    slug = slugify(f"{project}-{title}" if project else title)
    slug_url = f"/contribute/overview/{number}" if number is not None else f"/contribute/{slug}"
    new_filename = f"{SAVE_DIR}/{date_str}-{slug}.md"

    # 파일명 변경 처리
    old_filename = existing_map.get(page_id)
    if old_filename and old_filename != new_filename and os.path.exists(old_filename):
        os.remove(old_filename)
        print(f">> 이름 변경으로 기존 파일 삭제: {old_filename}")

    # 기여 정보 표 생성
    display_title = f"[{project}] {title}" if project else title
    url_cell = f"[링크]({upstream_url})" if upstream_url else "—"

    info_table = (
        "## 기여 정보\n\n"
        "| 항목 | 내용 |\n"
        "|------|------|\n"
        f"| 프로젝트 | {project or '—'} |\n"
        f"| 유형 | {contrib_type or '—'} |\n"
        f"| 날짜 | {date_str} |\n"
        f"| 상태 | `{status}` |\n"
        f"| 링크 | {url_cell} |\n\n"
    )

    blocks = get_page_blocks(page_id)
    body = blocks_to_markdown(blocks, slug)

    safe_title = display_title.replace('"', '\\"')
    frontmatter = (
        f"---\n"
        f"id: {slug}\n"
        f'title: "{safe_title}"\n'
        f"slug: {slug_url}\n"
        f"description: \"{title} ({date_str}, {status})\"\n"
        f"---\n\n"
    )

    os.makedirs(SAVE_DIR, exist_ok=True)
    with open(new_filename, "w", encoding="utf-8") as f:
        f.write(frontmatter + info_table + body)

    return title, new_filename


def remove_orphans(synced_files):
    if not os.path.isdir(SAVE_DIR):
        return
    for fname in os.listdir(SAVE_DIR):
        if fname in SKIP_FILES or not fname.endswith(".md"):
            continue
        fpath = os.path.join(SAVE_DIR, fname)
        if fpath not in synced_files:
            os.remove(fpath)
            print(f">> 미추적 파일 삭제: {fpath}")


def main():
    if not verify_database_access():
        sys.exit(1)

    fetch_mode = os.environ.get("CONTRIBUTE_FETCH_MODE", "ALL")  # 블로그 FETCH_MODE와 분리
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    payload = {}

    if fetch_mode == "DAILY":
        kst = timezone(timedelta(hours=9))
        target_date = (datetime.now(kst) - timedelta(days=1)).strftime("%Y-%m-%d")
        print(f">> [모드: 일간] {target_date} 조회")
        payload["filter"] = {
            "property": NOTION_PROPERTY_DATE,
            "date": {"equals": target_date},
        }
    else:
        print(">> [모드: 전체] 모든 기여 조회")

    existing_map = load_sync_map()
    has_more = True
    next_cursor = None
    saved = 0
    synced_files = set()

    while has_more:
        if next_cursor:
            payload["start_cursor"] = next_cursor
        res = requests.post(url, headers=headers, json=payload)
        data = res.json()
        if res.status_code != 200 or data.get("object") == "error":
            print(f">> ERROR: {data.get('message', data)}")
            sys.exit(1)

        pages = data.get("results", [])
        print(f">> 페이지 수: {len(pages)}")

        for page in pages:
            props = page.get("properties", {})
            page_date = read_date_start(props, NOTION_PROPERTY_DATE)
            if not page_date:
                print(">> WARN: 날짜 없음, 건너뜀")
                continue
            title, filepath = save_contribution(page, page_date, existing_map)
            existing_map[page["id"]] = filepath
            synced_files.add(filepath)
            print(f">> 저장: {filepath} ({title})")
            saved += 1

        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor")

    if fetch_mode != "DAILY":
        remove_orphans(synced_files)
        existing_map = {k: v for k, v in existing_map.items() if v in synced_files}

    save_sync_map(existing_map)

    # overview.md 카운트 갱신 (전체 추적 파일 수 기준)
    total = len(existing_map)
    update_overview_count(total)

    print(f">> 완료: {saved}개 저장, 누적 {total}건")


if __name__ == "__main__":
    main()
