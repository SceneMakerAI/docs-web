import os
import re
import sys
import requests
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta

SAVE_DIR_ROOT = "blog"
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


def block_to_markdown(block):
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
            return f"# {content}\n\n"
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
        return f"![image]({url})\n\n"
    elif b_type == "divider":
        return "---\n\n"
    return ""


def slugify(title):
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    return slug or "post"


def page_id_short(page_id):
    return page_id.replace("-", "")[:8]


def build_body_with_truncate(blocks):
    parts = []
    truncated = False
    for block in blocks:
        md = block_to_markdown(block)
        if not md:
            continue
        parts.append(md)
        if not truncated and block["type"] == "paragraph" and md.strip():
            parts.append("<!-- truncate -->\n\n")
            truncated = True
    return "".join(parts)


def extract_description(blocks):
    for block in blocks:
        if block["type"] == "paragraph":
            rich_text = block["paragraph"].get("rich_text", [])
            text = extract_text_from_rich_text(rich_text).strip()
            if text:
                return text[:150]
    return ""


def save_as_blog_post(page, date_str, tags):
    if len(date_str) > 10:
        date_str = date_str[:10]

    page_id = page["id"]
    title = read_title_plain(page["properties"], NOTION_PROPERTY_TITLE) or "제목없음"
    slug = slugify(title)
    short_id = page_id_short(page_id)
    filename = f"{SAVE_DIR_ROOT}/{date_str}-{short_id}.md"

    blocks = get_page_blocks(page_id)
    description = extract_description(blocks)

    tags_line = (
        "\ntags: [" + ", ".join(f'"{t}"' for t in tags) + "]"
        if tags
        else ""
    )
    desc_line = f'\ndescription: "{description}"' if description else ""
    frontmatter = (
        f"---\n"
        f'title: "{title}"\n'
        f"date: {date_str}\n"
        f"slug: {slug}\n"
        f"authors: [{DEFAULT_AUTHOR}]{tags_line}{desc_line}\n"
        f"---\n\n"
    )

    body = build_body_with_truncate(blocks)
    notion_link = f"\n---\n\n> 원본: [Notion에서 보기]({page['url']})\n"

    os.makedirs(SAVE_DIR_ROOT, exist_ok=True)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(frontmatter + body + notion_link)

    return title, filename


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

    has_more = True
    next_cursor = None
    saved = 0

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
            tags = read_tags(props, NOTION_PROPERTY_TAGS)
            title, filepath = save_as_blog_post(page, page_date, tags)
            print(f">> 저장: {filepath} ({title})")
            saved += 1

        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor")

    print(f">> 완료: {saved}개 저장")


if __name__ == "__main__":
    main()
