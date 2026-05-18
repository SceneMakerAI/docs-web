import os
import re
import sys
import requests
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta

SAVE_DIR_ROOT = "blog"
STATIC_IMG_DIR = "static/img/blog"
NOTION_PROPERTY_TITLE = os.environ.get("NOTION_PROPERTY_TITLE", "제목")
NOTION_PROPERTY_DATE = os.environ.get("NOTION_PROPERTY_DATE", "날짜")
NOTION_PROPERTY_TAGS = os.environ.get("NOTION_PROPERTY_TAGS", "")
DEFAULT_AUTHOR = os.environ.get("BLOG_DEFAULT_AUTHOR", "minsung")
TIMEZONE_HOURS = 9


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


NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DATABASE_ID = normalize_notion_database_id(os.environ["NOTION_DATABASE_ID"])

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}


def load_valid_tags():
    """tags.yml에 정의된 태그 키 목록을 반환."""
    tags_file = f"{SAVE_DIR_ROOT}/tags.yml"
    if not os.path.exists(tags_file):
        return set()
    valid = set()
    with open(tags_file, encoding="utf-8") as f:
        for line in f:
            m = re.match(r'^([a-zA-Z0-9_-]+):', line)
            if m:
                valid.add(m.group(1))
    return valid


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


def read_notion_property_value(props, prop_name):
    p = props.get(prop_name)
    if not isinstance(p, dict):
        return None, None
    ptype = p.get("type")
    return ptype, p.get(ptype) if ptype else (None, None)


def read_date_start(props, prop_name):
    ptype, inner = read_notion_property_value(props, prop_name)
    if ptype != "date":
        return None, ptype
    if not inner or not isinstance(inner, dict):
        return None, ptype
    start = inner.get("start")
    if start and len(start) >= 10:
        return start[:10], ptype
    return None, ptype


def read_title_plain(props, prop_name):
    ptype, inner = read_notion_property_value(props, prop_name)
    if ptype != "title" or not inner:
        return None
    try:
        return inner[0]["plain_text"]
    except (IndexError, KeyError, TypeError):
        return None


def read_tags(props, prop_name):
    if not prop_name:
        return []
    p = props.get(prop_name)
    if not isinstance(p, dict):
        return []
    ptype = p.get("type")
    if ptype == "multi_select":
        return [item["name"] for item in (p.get("multi_select") or [])]
    if ptype == "select":
        s = p.get("select")
        return [s["name"]] if s else []
    return []


def get_page_blocks(page_id):
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    return requests.get(url, headers=headers).json().get("results", [])


def extract_text_from_rich_text(rich_text_list):
    parts = []
    for text in rich_text_list:
        plain = text["plain_text"]
        href = text.get("href")
        parts.append(f"[{plain}]({href})" if href else plain)
    result = ""
    for part in parts:
        if result and result[-1] not in (" ", "\n") and part and part[0] not in (" ", "\n"):
            if result.endswith(")") or result[-1].isalnum():
                result += " "
        result += part
    return result


def download_image(url: str, slug: str, index: int) -> str:
    """Notion 이미지를 static/img/blog/{slug}/ 에 다운로드하고 로컬 경로를 반환."""
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
    else:
        print(f">> 이미지 캐시: {filepath}")

    return f"/img/blog/{slug}/{filename}"


def block_to_markdown(block, slug=None, image_counter=None):
    b_type = block["type"]
    if b_type in (
        "paragraph", "heading_1", "heading_2", "heading_3",
        "bulleted_list_item", "numbered_list_item", "to_do",
        "toggle", "quote", "callout",
    ):
        rich_text = block[b_type].get("rich_text", [])
        content = extract_text_from_rich_text(rich_text)
        if b_type == "paragraph":
            return content + "\n\n"
        elif b_type == "heading_1":
            return f"## {content}\n\n"  # h1 → h2 (frontmatter title이 h1)
        elif b_type == "heading_2":
            return f"## {content}\n\n"
        elif b_type == "heading_3":
            return f"### {content}\n\n"
        elif b_type == "bulleted_list_item":
            return f"- {content}\n"
        elif b_type == "numbered_list_item":
            return f"1. {content}\n"
        elif b_type == "to_do":
            checked = "[x]" if block["to_do"]["checked"] else "[ ]"
            return f"- {checked} {content}\n"
        elif b_type == "quote":
            return f"> {content}\n\n"
        elif b_type == "callout":
            return f"> {content}\n\n"
        elif b_type == "toggle":
            return f"- {content}\n"
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
        if slug is not None and image_counter is not None:
            try:
                local_path = download_image(url, slug, image_counter[0])
                image_counter[0] += 1
                return f"![image]({local_path})\n\n"
            except Exception as e:
                print(f">> WARN: 이미지 다운로드 실패 ({url[:60]}...): {e}")
        return f"![image]({url})\n\n"
    elif b_type == "divider":
        return "---\n\n"
    return ""


def build_body(blocks, slug):
    """블록을 MDX 본문으로 변환. 첫 번째 paragraph 뒤에 truncate 마커 삽입."""
    image_counter = [0]
    parts = []
    truncate_inserted = False

    for block in blocks:
        md = block_to_markdown(block, slug, image_counter)
        if not md:
            continue
        parts.append(md)
        if not truncate_inserted and block["type"] == "paragraph":
            parts.append("{/* truncate */}\n\n")
            truncate_inserted = True

    if not truncate_inserted and parts:
        parts.insert(1, "{/* truncate */}\n\n")

    return "".join(parts)


def make_frontmatter(title, slug, date_str, author, tags):
    valid_tags = load_valid_tags()
    if valid_tags:
        filtered = [t for t in tags if t in valid_tags]
        skipped = set(tags) - set(filtered)
        if skipped:
            print(f">> WARN: tags.yml에 없는 태그 제외: {skipped}")
        tags = filtered

    tags_str = ", ".join(tags)
    safe_title = title.replace('"', '\\"')
    return (
        f"---\n"
        f"slug: {slug}\n"
        f"title: \"{safe_title}\"\n"
        f"authors: [{author}]\n"
        f"tags: [{tags_str}]\n"
        f"date: {date_str}\n"
        f"---\n\n"
    )


def slugify(title):
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    return slug or "post"


SYNC_MAP_FILE = f"{SAVE_DIR_ROOT}/.notion-sync.json"


def load_sync_map():
    if not os.path.exists(SYNC_MAP_FILE):
        return {}
    import json
    with open(SYNC_MAP_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_sync_map(mapping):
    import json
    os.makedirs(SAVE_DIR_ROOT, exist_ok=True)
    with open(SYNC_MAP_FILE, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)


def scan_existing_posts():
    return load_sync_map()


def save_as_blog_post(page, date_str, existing_map):
    if len(date_str) > 10:
        date_str = date_str[:10]

    page_id = page["id"]
    title = read_title_plain(page["properties"], NOTION_PROPERTY_TITLE) or "제목없음"
    slug = slugify(title)
    new_filename = f"{SAVE_DIR_ROOT}/{date_str}-{slug}.mdx"

    old_filename = existing_map.get(page_id)
    if old_filename and old_filename != new_filename:
        # .md → .mdx 마이그레이션 케이스도 포함
        for candidate in [old_filename, old_filename.replace(".mdx", ".md")]:
            if os.path.exists(candidate):
                os.remove(candidate)
                print(f">> 이름 변경으로 기존 파일 삭제: {candidate}")

    tags = read_tags(page["properties"], NOTION_PROPERTY_TAGS)
    blocks = get_page_blocks(page_id)
    frontmatter = make_frontmatter(title, slug, date_str, DEFAULT_AUTHOR, tags)
    body = build_body(blocks, slug)

    os.makedirs(SAVE_DIR_ROOT, exist_ok=True)
    with open(new_filename, "w", encoding="utf-8") as f:
        f.write(frontmatter + body)

    return title, new_filename


def remove_orphans(synced_files):
    """ALL 모드에서 이번 동기화에 포함되지 않은 .mdx/.md 파일을 삭제."""
    if not os.path.isdir(SAVE_DIR_ROOT):
        return
    for fname in os.listdir(SAVE_DIR_ROOT):
        if not (fname.endswith(".mdx") or fname.endswith(".md")):
            continue
        fpath = os.path.join(SAVE_DIR_ROOT, fname)
        if fpath not in synced_files:
            os.remove(fpath)
            print(f">> 미추적 파일 삭제: {fpath}")


def main():
    if not verify_database_access():
        sys.exit(1)

    fetch_mode = os.environ.get("FETCH_MODE", "DAILY")
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    payload = {}

    if fetch_mode == "ALL":
        print(">> [모드: 전체] 모든 페이지 조회")
    else:
        kst = timezone(timedelta(hours=TIMEZONE_HOURS))
        target_date = (datetime.now(kst) - timedelta(days=1)).strftime("%Y-%m-%d")
        print(f">> [모드: 일간] {target_date} 조회")
        payload["filter"] = {
            "property": NOTION_PROPERTY_DATE,
            "date": {"equals": target_date},
        }

    existing_map = scan_existing_posts()
    print(f">> 기존 파일 {len(existing_map)}개 추적 중")

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
            props = page.get("properties") or {}
            page_date, dtype = read_date_start(props, NOTION_PROPERTY_DATE)
            if not page_date:
                print(f">> WARN: 날짜 읽기 실패 (type={dtype})")
                continue
            title, filepath = save_as_blog_post(page, page_date, existing_map)
            existing_map[page["id"]] = filepath
            synced_files.add(filepath)
            print(f">> 저장: {filepath} ({title})")
            saved += 1

        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor")

    if fetch_mode == "ALL":
        remove_orphans(synced_files)
        new_map = {k: v for k, v in existing_map.items() if v in synced_files}
        save_sync_map(new_map)
    else:
        save_sync_map(existing_map)

    print(f">> 완료: {saved}개 저장")


if __name__ == "__main__":
    main()
