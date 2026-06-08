"""
notion_to_md.py — Notion DB → Docusaurus docs 섹션 동기화

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
import hashlib
import html as _html
import os
import re
import sys
import json
import requests
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta

_NOTION_LANG_MAP = {
    "plain text":    "text",
    "c++":           "cpp",
    "c#":            "csharp",
    "f#":            "fsharp",
    "objective-c":   "objectivec",
    "vb.net":        "vbnet",
    "visual basic":  "vbnet",
    "java/c/c++/c#": "java",
}


_NOTION_BG_COLOR_NAMES = {
    "gray_background", "brown_background", "orange_background",
    "yellow_background", "green_background", "blue_background",
    "purple_background", "pink_background", "red_background",
}




def _get_cell_bg(cell_rich_text):
    """셀 rich_text 목록에서 Notion 배경색 이름 반환. 없으면 None."""
    for rt in cell_rich_text:
        color = rt.get("annotations", {}).get("color", "default")
        if color in _NOTION_BG_COLOR_NAMES:
            return color
    return None


def _rich_text_to_html(rich_text_list):
    """rich_text 목록 → HTML 문자열 변환 (HTML 테이블 셀 내용용)."""
    parts = []
    for text in rich_text_list:
        plain = text["plain_text"]
        while (unescaped := _html.unescape(plain)) != plain:
            plain = unescaped
        ann = text.get("annotations", {})
        href = text.get("href")
        escaped = _html.escape(plain)
        if ann.get("code"):
            content = f"<code>{escaped}</code>"
        else:
            content = escaped
            if ann.get("bold") and ann.get("italic"):
                content = f"<strong><em>{content}</em></strong>"
            elif ann.get("bold"):
                content = f"<strong>{content}</strong>"
            elif ann.get("italic"):
                content = f"<em>{content}</em>"
            if ann.get("strikethrough"):
                content = f"<del>{content}</del>"
        if href:
            content = f'<a href="{_html.escape(_resolve_notion_href(href))}">{content}</a>'
        parts.append(content)
    return "".join(parts)


# Notion page ID → 내부 docs URL 매핑 (sync 실행 시 _build_page_link_map 으로 채워짐)
_page_id_to_internal_url: dict = {}


def _build_page_link_map(sync_map: dict) -> None:
    """sync_map 에서 Notion page ID → 내부 docs URL 매핑을 구성한다.
    parent_id 가 있는 자식 페이지만 처리 (섹션 인덱스는 스킵)."""
    _page_id_to_internal_url.clear()
    url_base = "/" + SAVE_DIR  # "docs/poc" → "/docs/poc"
    for page_id, info in sync_map.items():
        if not isinstance(info, dict):
            continue
        parent_id = info.get("parent_id")
        order = info.get("order")
        if order is None or parent_id is None:
            continue
        _page_id_to_internal_url[page_id] = f"{url_base}/{parent_id}/{order}"


def _resolve_notion_href(href: str) -> str:
    """Notion 페이지 URL을 내부 docs 경로로 변환한다. 매핑 없으면 원본 반환."""
    if not href or not href.startswith("https://www.notion.so/"):
        return href
    raw = href.rstrip("/").split("/")[-1].split("?")[0]
    if len(raw) != 32:
        return href
    pid = f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"
    return _page_id_to_internal_url.get(pid, href)


NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DATABASE_ID_RAW = os.environ["NOTION_DATABASE_ID"]
SAVE_DIR = os.environ.get("SAVE_DIR", "docs/guide")
_last_seg = SAVE_DIR.rstrip("/").split("/")[-1]
STATIC_IMG_DIR = os.environ.get("STATIC_IMG_DIR", f"static/img/{_last_seg}")
NOTION_PROPERTY_TITLE = os.environ.get("NOTION_PROPERTY_TITLE", "제목")
NOTION_PROPERTY_ORDER = os.environ.get("NOTION_PROPERTY_ORDER", "순서")
NOTION_PROPERTY_DATE = os.environ.get("NOTION_PROPERTY_DATE", "날짜")
NOTION_PROPERTY_SUBITEM = os.environ.get("NOTION_PROPERTY_SUBITEM", "하위 항목")
NOTION_PROPERTY_PARENT = os.environ.get("NOTION_PROPERTY_PARENT", "상위 항목")
FETCH_MODE = os.environ.get("FETCH_MODE", "ALL")
TIMEZONE_HOURS = 9

# Blog mode: SAVE_DIR 가 'blog' 또는 'blog/'로 시작하면 blog 플러그인 frontmatter 생성
BLOG_MODE = SAVE_DIR.rstrip("/") == "blog" or SAVE_DIR.rstrip("/").startswith("blog/")
NOTION_PROPERTY_BLOG_CREATED     = os.environ.get("NOTION_PROPERTY_BLOG_CREATED", "생성 일시")
NOTION_PROPERTY_BLOG_LAST_EDITED = os.environ.get("NOTION_PROPERTY_BLOG_LAST_EDITED", "최종 편집 일시")
NOTION_PROPERTY_AUTHORS          = os.environ.get("NOTION_PROPERTY_AUTHORS", "authors")
NOTION_PROPERTY_DESCRIPTION      = os.environ.get("NOTION_PROPERTY_DESCRIPTION", "description")
NOTION_PROPERTY_TAGS             = os.environ.get("NOTION_PROPERTY_TAGS", "tags")
NOTION_PROPERTY_SLUG             = os.environ.get("NOTION_PROPERTY_SLUG", "slug")
# Docs mode 선택 속성 (없으면 frontmatter에서 생략)
NOTION_PROPERTY_DOCS_LAST_EDITED = os.environ.get("NOTION_PROPERTY_DOCS_LAST_EDITED", "최종 편집 일시")
NOTION_PROPERTY_KEYWORDS         = os.environ.get("NOTION_PROPERTY_KEYWORDS", "keywords")


SYNC_MAP_FILE = f"{SAVE_DIR}/.notion-sync.json"
# 수동 작성 구조 파일 — sync가 절대 삭제하지 않음
# _category_.json은 section root(SAVE_DIR 직하)만 보존, 하위 subdirectory는 sync가 관리
SKIP_FILES = {"overview.mdx"}


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
        # 속성명이 다른 DB에서도 동작하도록 title 타입 속성 자동 탐색
        for val in props.values():
            if val.get("type") == "title":
                p = val
                break
        else:
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


def read_relation(props, prop_name):
    p = props.get(prop_name, {})
    if p.get("type") != "relation":
        return []
    return [item["id"] for item in p.get("relation", [])]


def read_multi_select(props, prop_name):
    p = props.get(prop_name, {})
    if p.get("type") != "multi_select":
        return []
    return [item["name"] for item in p.get("multi_select", [])]


def read_people(props, prop_name):
    p = props.get(prop_name, {})
    if p.get("type") != "people":
        return []
    return [person.get("name", "") for person in p.get("people", []) if person.get("name")]


def read_rich_text_plain(props, prop_name):
    p = props.get(prop_name, {})
    if p.get("type") != "rich_text":
        return None
    return "".join(t["plain_text"] for t in p.get("rich_text", [])) or None


def read_files_url(props, prop_name):
    p = props.get(prop_name, {})
    if p.get("type") != "files":
        return None
    files = p.get("files", [])
    if not files:
        return None
    f = files[0]
    if f.get("type") == "external":
        return f.get("external", {}).get("url")
    if f.get("type") == "file":
        return f.get("file", {}).get("url")
    return None


def read_created_time_prop(props, name):
    """Notion created_time 타입 속성 → YYYY-MM-DD"""
    p = props.get(name, {})
    if p.get("type") == "created_time":
        val = p.get("created_time", "")
        return val[:10] if val else None
    return None


def read_last_edited_time_prop(props, name):
    """Notion last_edited_time 타입 속성 → YYYY-MM-DD"""
    p = props.get(name, {})
    if p.get("type") == "last_edited_time":
        val = p.get("last_edited_time", "")
        return val[:10] if val else None
    return None


def generate_category_json(dir_path, label, position):
    slug = os.path.basename(dir_path)
    parent = os.path.basename(os.path.dirname(dir_path))
    # generated-index + slug: /docs/{section}/{slug} URL 생성 (category/ 경로 방지)
    data = {"label": label, "position": position,
            "link": {"type": "generated-index", "slug": f"/{parent}/{slug}"}}
    os.makedirs(dir_path, exist_ok=True)
    with open(f"{dir_path}/_category_.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log(f"_category_.json 생성: {dir_path}/_category_.json")


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
        while (unescaped := _html.unescape(plain)) != plain:  # 이중 인코딩(&amp;gt; 등) 완전 복원
            plain = unescaped
        ann = text.get("annotations", {})
        href = text.get("href")

        if ann.get("code"):
            formatted = f"`{plain}`" if plain.strip() else plain
        else:
            formatted = plain
            if plain.strip():
                # 선행/후행 공백은 마커 밖으로 — '** text **' 방지
                leading = plain[:len(plain) - len(plain.lstrip())]
                trailing = plain[len(plain.rstrip()):]
                core = plain.strip()
                if ann.get("bold") and ann.get("italic"):
                    core = f"***{core}***"
                elif ann.get("bold"):
                    core = f"**{core}**"
                elif ann.get("italic"):
                    core = f"*{core}*"
                if ann.get("strikethrough"):
                    core = f"~~{core}~~"
                formatted = leading + core + trailing

        parts.append(f"[{formatted}]({_resolve_notion_href(href)})" if href else formatted)

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


def indent_md(text, prefix="  "):
    lines = text.rstrip("\n").splitlines()
    return "\n".join(prefix + line if line.strip() else line for line in lines) + "\n"


def block_to_markdown(block, slug, image_counter, item_num=1):
    b_type = block["type"]
    children = block.get("_children", [])

    def render_children():
        return "".join(block_to_markdown(c, slug, image_counter) for c in children)

    if b_type == "table":
        if not children:
            return ""
        tbl = block.get("table", {})
        col_header = tbl.get("has_column_header", False)  # 1행 헤더
        row_header = tbl.get("has_row_header", False)     # 1열 헤더
        has_color = any(
            _get_cell_bg(cell)
            for row in children
            for cell in row.get("table_row", {}).get("cells", [])
        )
        has_pipe = any(
            "|" in extract_text_from_rich_text(cell)
            for row in children
            for cell in row.get("table_row", {}).get("cells", [])
        )
        if has_color or row_header or has_pipe:
            lines = ["<table>"]
            in_tbody = False
            for i, row in enumerate(children):
                cells = row.get("table_row", {}).get("cells", [])
                is_col_header_row = col_header and i == 0
                if is_col_header_row:
                    lines.append("<thead><tr>")
                else:
                    if not in_tbody:
                        lines.append("<tbody>")
                        in_tbody = True
                    lines.append("<tr>")
                for j, cell in enumerate(cells):
                    is_th = is_col_header_row or (row_header and j == 0)
                    tag = "th" if is_th else "td"
                    bg = _get_cell_bg(cell)
                    text = _rich_text_to_html(cell)
                    attr = f' data-notion-bg="{bg}"' if bg else ""
                    lines.append(f"<{tag}{attr}>{text}</{tag}>")
                lines.append("</tr></thead>" if is_col_header_row else "</tr>")
            lines.append("</tbody></table>")
            return "\n".join(lines) + "\n\n"
        lines = []
        for i, row in enumerate(children):
            cells = row.get("table_row", {}).get("cells", [])
            row_text = " | ".join(
                extract_text_from_rich_text(cell).replace("\n", " ")
                for cell in cells
            )
            lines.append(f"| {row_text} |")
            if i == 0:  # GFM 테이블은 구분선 필수 — col_header 여부 무관
                sep = " | ".join("---" for _ in cells)
                lines.append(f"| {sep} |")
        return "\n".join(lines) + "\n\n"

    elif b_type in ("column_list", "column"):
        return render_children()

    elif b_type in (
        "paragraph", "heading_1", "heading_2", "heading_3", "heading_4",
        "bulleted_list_item", "numbered_list_item", "to_do",
        "toggle", "quote", "callout",
    ):  # callout은 아래 elif에서 별도 처리 — 이 tuple 포함은 rich_text 추출용
        rich_text = block[b_type].get("rich_text", [])
        content = extract_text_from_rich_text(rich_text)
        child_md = render_children()
        if b_type == "paragraph":
            # 단일 멀티라인 인라인 코드 (`...\n...`) → fenced code block
            # CommonMark 파서가 인라인 코드 내 \n을 공백으로 치환하므로 선변환 필요
            _m = re.match(r'^`([^`]+)`$', content)
            if _m and '\n' in _m.group(1):
                return f"```\n{_m.group(1)}\n```\n\n" + child_md
            # Shift+Enter → CommonMark hard line break (스페이스 2개 + \n)
            if '\n' in content:
                content = content.replace('\n', '  \n')
            return (content + "\n\n" if content else "\n") + child_md
        elif b_type == "heading_1":
            return f"## {content}\n\n" + child_md
        elif b_type == "heading_2":
            return f"### {content}\n\n" + child_md
        elif b_type == "heading_3":
            return f"#### {content}\n\n" + child_md
        elif b_type == "heading_4":
            return f"##### {content}\n\n" + child_md
        elif b_type == "bulleted_list_item":
            # "2. 내용" 같이 숫자+점으로 시작하면 GFM이 nested ordered list로 파싱 — 이스케이프
            safe = re.sub(r'^(\d+)\. ', r'\1\\. ', content)
            if child_md:
                return f"- {safe}\n{indent_md(child_md)}\n"
            return f"- {safe}\n\n"
        elif b_type == "numbered_list_item":
            if child_md:
                return f"{item_num}. {content}\n{indent_md(child_md, '   ')}\n"
            return f"{item_num}. {content}\n\n"
        elif b_type == "to_do":
            checked = "[x]" if block["to_do"]["checked"] else "[ ]"
            return f"- {checked} {content}\n\n" + child_md
        elif b_type == "quote":
            if child_md:
                child_quoted = "\n".join(
                    f"> {line}" if line.strip() else ">"
                    for line in child_md.rstrip("\n").splitlines()
                )
                return f"> {content}\n>\n{child_quoted}\n\n"
            return f"> {content}\n\n"
        elif b_type == "callout":
            icon_data = block.get("callout", {}).get("icon", {})
            emoji = icon_data.get("emoji", "")
            prefix = f"{emoji} " if emoji else ""
            inner = f"{prefix}{content}"
            if child_md:
                inner += "\n\n" + child_md.rstrip("\n")
            quoted = "\n".join(f"> {line}" if line else ">" for line in inner.split("\n"))
            return f"{quoted}\n\n"
        elif b_type == "toggle":
            if child_md:
                # <summary> 안에서는 마크다운이 처리되지 않으므로 HTML 태그로 변환
                summary = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
                summary = re.sub(r'\*(.+?)\*', r'<em>\1</em>', summary)
                return f"<details>\n<summary>{summary}</summary>\n\n{child_md}\n</details>\n\n"
            return f"- {content}\n"

    elif b_type == "table_row":
        return ""  # table 블록 내부에서만 처리

    elif b_type == "code":
        raw_lang = block["code"].get("language", "text")
        language = _NOTION_LANG_MAP.get(raw_lang.lower(), raw_lang)
        raw = extract_text_from_rich_text(block["code"].get("rich_text", []))
        content = _html.unescape(raw)  # Notion이 &lt; &gt; 등을 반환할 때 코드 블록 내 이중 이스케이프 방지
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
    """<한글> 같이 비 ASCII를 포함한 꺾쇠 패턴을 MDX가 태그로 해석하지 않도록 이스케이프.
    코드 블록(```...```) 및 인라인 코드(`...`) 내부는 건너뜀."""
    parts = re.split(r'(```[\s\S]*?```|`[^`\n]+`)', text)
    result = []
    for i, part in enumerate(parts):
        if i % 2 == 1:  # 코드 스팬/블록 — 그대로 유지
            result.append(part)
        else:
            result.append(re.sub(r'<([^>\n]*[^\x00-\x7F\n][^>\n]*)>', r'&lt;\1&gt;', part))
    return ''.join(result)


def escape_single_tildes(text):
    """단독 ~ 를 \~ 로 이스케이프. 백틱 인라인 코드·코드 블록 내부는 제외.
    코드 스팬 안에서 \~ 는 리터럴로 렌더링되므로 이스케이프하면 안 된다."""
    parts = re.split(r'(```[\s\S]*?```|`[^`\n]+`)', text)
    result = []
    for i, part in enumerate(parts):
        if i % 2 == 1:  # 백틱 코드 스팬/블록 — 그대로 유지
            result.append(part)
        else:
            result.append(re.sub(r'(?<!~)~(?!~)', r'\\~', part))
    return ''.join(result)


_OL_RESET_TYPES = {
    "heading_1", "heading_2", "heading_3", "heading_4",
    # bulleted_list_item / to_do 는 번호 목록 항목 사이에 주석·sub-bullet로 나타나므로 리셋 안 함
    "table", "toggle", "column_list",
}


def blocks_to_markdown(blocks, slug):
    image_counter = [0]
    ol_seq = [0]  # numbered_list_item 연속 카운터

    def convert(b):
        btype = b.get("type", "")
        if btype == "numbered_list_item":
            ol_seq[0] += 1
        elif btype in _OL_RESET_TYPES:
            ol_seq[0] = 0
        # code / paragraph / image / divider / quote / callout 은 리셋 안 함 (split-OL 연속 번호 유지)
        return block_to_markdown(b, slug, image_counter, ol_seq[0])

    body = "".join(convert(b) for b in blocks)
    body = escape_mdx_angle_brackets(body)
    body = re.sub(r'(<[a-zA-Z][^>]*/)\s*&gt;', r'\1>', body)
    body = escape_single_tildes(body)
    # 연속된 리스트 항목 사이의 빈 줄 제거 (loose → tight list)
    prev = None
    while prev != body:
        prev = body
        body = re.sub(
            r'(^(?:- (?:\[[ x]\] )?|\d+\. )[^\n]+)\n\n(?=(?:- (?:\[[ x]\] )?|\d+\. ))',
            r'\1\n',
            body,
            flags=re.MULTILINE,
        )
    return body


def slugify(title):
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    return slug or "page"


def load_sync_map():
    if not os.path.exists(SYNC_MAP_FILE):
        return {}
    with open(SYNC_MAP_FILE, encoding="utf-8") as f:
        raw = json.load(f)
    # 구 포맷 {id: "filepath"} → 신 포맷 {id: {"file": ..., "last_edited": ...}} 자동 변환
    result = {}
    for pid, val in raw.items():
        if isinstance(val, str):
            result[pid] = {"file": val, "last_edited": ""}
        else:
            result[pid] = val
    return result


def save_sync_map(mapping):
    os.makedirs(SAVE_DIR, exist_ok=True)
    with open(SYNC_MAP_FILE, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)



def save_doc_page(page, position, existing_map, parent_slug=None, is_parent=False):
    """Notion 페이지를 Markdown 파일로 저장한다.

    - is_parent=True: 하위 항목을 가진 루트 페이지 →
        {SAVE_DIR}/{slug}/index.md 저장 + _category_.json 생성
    - parent_slug 있음: 자식 페이지 →
        {SAVE_DIR}/{parent_slug}/{slug}.md 저장
    - 둘 다 없음: 기존 동작 (루트 레벨 평면 저장)
    """
    page_id = page["id"]
    last_edited = page.get("last_edited_time", "")
    created_time = page.get("created_time", "")
    props = page.get("properties", {})
    title = read_title_plain(props, NOTION_PROPERTY_TITLE) or "제목없음"
    order = position

    slug = slugify(title)

    if BLOG_MODE:
        date_str = (read_created_time_prop(props, NOTION_PROPERTY_BLOG_CREATED)
                    or (created_time[:10] if created_time else "1970-01-01"))
        new_filename = f"{SAVE_DIR}/{date_str}-{slug}.md"
        url_slug = None  # blog 플러그인이 파일명에서 자동 결정
    elif is_parent:
        new_filename = f"{SAVE_DIR}/{slug}/index.md"
        url_slug = slug  # "/"는 절대경로(/docs/)로 해석됨 → 디렉토리명 사용
    elif parent_slug:
        new_filename = f"{SAVE_DIR}/{parent_slug}/{slug}.md"
        url_slug = str(order)
    else:
        new_filename = f"{SAVE_DIR}/{slug}.md"
        url_slug = str(order)

    existing_entry = existing_map.get(page_id)
    if isinstance(existing_entry, dict):
        old_filename = existing_entry.get("file")
        stored_last_edited = existing_entry.get("last_edited", "")
        stored_hash = existing_entry.get("content_hash", "")
        stored_order = existing_entry.get("order")
        stored_parent = existing_entry.get("parent_id")
    elif isinstance(existing_entry, str):
        old_filename = existing_entry
        stored_last_edited = ""
        stored_hash = ""
        stored_order = None
        stored_parent = None
    else:
        old_filename = None
        stored_last_edited = ""
        stored_hash = ""
        stored_order = None
        stored_parent = None

    current_parent_id = parent_slug  # 문자열 slug or None

    order_unchanged = BLOG_MODE or stored_order == order
    if (last_edited and stored_last_edited == last_edited
            and old_filename == new_filename
            and os.path.exists(new_filename)
            and order_unchanged
            and stored_parent == current_parent_id):
        log(f"변경 없음, 스킵: {title}")
        if not BLOG_MODE and is_parent:
            # _category_.json이 없으면 재생성
            cat_path = f"{SAVE_DIR}/{slug}/_category_.json"
            if not os.path.exists(cat_path):
                generate_category_json(f"{SAVE_DIR}/{slug}", title, order)
            # 빈 body index.md 삭제 (skip 경로에서도 정리)
            _m = re.match(r'^---\n.*?\n---\n*$', open(new_filename, encoding='utf-8').read().strip(), re.DOTALL)
            if _m:
                os.remove(new_filename)
                log(f"빈 부모 index.md 삭제 (스킵): {new_filename}")
        return title, new_filename, last_edited, stored_hash, order

    if old_filename and old_filename != new_filename:
        for candidate in [old_filename, old_filename.replace(".md", ".mdx")]:
            if os.path.exists(candidate):
                os.remove(candidate)
                log(f"이름 변경으로 기존 파일 삭제: {candidate}")

    blocks = get_page_blocks(page_id)
    body = blocks_to_markdown(blocks, slug)
    content_hash = hashlib.sha256(body.encode()).hexdigest()

    safe_title = title.replace('"', '\\"')

    if BLOG_MODE:
        # truncate 마커 삽입: Notion 구분선 우선, 없으면 첫 단락 뒤에 자동 삽입
        if "\n---\n" in body:
            body = body.replace("\n---\n", "\n\n<!--truncate-->\n\n", 1)
        else:
            stripped = body.lstrip("\n")
            match = re.search(r"\n\n", stripped)
            if match:
                offset = len(body) - len(stripped)
                pos = offset + match.end()
                body = body[:pos] + "<!--truncate-->\n\n" + body[pos:]

        authors_list = read_multi_select(props, NOTION_PROPERTY_AUTHORS)
        if not authors_list:
            authors_list = read_people(props, NOTION_PROPERTY_AUTHORS)
        description = read_rich_text_plain(props, NOTION_PROPERTY_DESCRIPTION)
        tags = read_multi_select(props, NOTION_PROPERTY_TAGS)
        last_edited_date = read_last_edited_time_prop(props, NOTION_PROPERTY_BLOG_LAST_EDITED)
        raw_slug = read_rich_text_plain(props, NOTION_PROPERTY_SLUG)
        safe_slug = re.sub(r"[^a-z0-9-]", "", raw_slug.lower().replace(" ", "-")) if raw_slug else None

        # Notion에 slug 속성이 없으면 기존 파일에 설정된 slug 보존
        if not safe_slug and os.path.exists(new_filename):
            with open(new_filename, encoding="utf-8") as _f:
                _existing_slug_m = re.search(r"^slug:\s*(\S+)", _f.read(), re.MULTILINE)
            if _existing_slug_m:
                safe_slug = _existing_slug_m.group(1)

        lines = ["---", f'title: "{safe_title}"', f"date: {date_str}"]
        if safe_slug:
            lines.append(f"slug: {safe_slug}")
        if authors_list:
            lines.append(f"authors: [{', '.join(authors_list)}]")
        if description:
            safe_desc = description.replace('"', '\\"')
            lines.append(f'description: "{safe_desc}"')
        if tags:
            lines.append(f"tags: [{', '.join(tags)}]")
        if last_edited_date and last_edited_date != date_str:
            lines.append(f"last_update:")
            lines.append(f"  date: {last_edited_date}")
        lines.append("---\n")
        frontmatter = "\n".join(lines) + "\n"
    # 부모 index.md는 id를 생략 → Docusaurus가 파일경로 기반으로 ID 부여 (section/slug/index)
    # 자식·평면 페이지는 id를 명시 (section 내 고유 식별자)
    elif is_parent:
        _desc = read_rich_text_plain(props, NOTION_PROPERTY_DESCRIPTION)
        _tags = read_multi_select(props, NOTION_PROPERTY_TAGS)
        _kw   = read_rich_text_plain(props, NOTION_PROPERTY_KEYWORDS)
        _last_edit = read_last_edited_time_prop(props, NOTION_PROPERTY_DOCS_LAST_EDITED)
        _lines = ["---", f'title: "{safe_title}"', f"sidebar_position: {order}", f'slug: "{url_slug}"']
        if _desc:
            _lines.append(f'description: "{_desc.replace(chr(34), chr(92)+chr(34))}"')
        if _tags:
            _lines.append(f"tags: [{', '.join(_tags)}]")
        # keywords: Notion keywords 속성 우선, 없으면 tags에서 파생
        _kw_list = [k.strip() for k in _kw.split(",")] if _kw else _tags
        if _kw_list:
            _lines.append(f"keywords: [{', '.join(_kw_list)}]")
        if _last_edit:
            _lines.extend(["last_update:", f"  date: {_last_edit}"])
        _lines.append("---\n")
        frontmatter = "\n".join(_lines) + "\n"
    else:
        _desc = read_rich_text_plain(props, NOTION_PROPERTY_DESCRIPTION)
        _tags = read_multi_select(props, NOTION_PROPERTY_TAGS)
        _kw   = read_rich_text_plain(props, NOTION_PROPERTY_KEYWORDS)
        _last_edit = read_last_edited_time_prop(props, NOTION_PROPERTY_DOCS_LAST_EDITED)
        _lines = ["---", f"id: {slug}", f'title: "{safe_title}"', f"sidebar_position: {order}", f'slug: "{url_slug}"']
        if _desc:
            _lines.append(f'description: "{_desc.replace(chr(34), chr(92)+chr(34))}"')
        if _tags:
            _lines.append(f"tags: [{', '.join(_tags)}]")
        # keywords: Notion keywords 속성 우선, 없으면 tags에서 파생
        _kw_list = [k.strip() for k in _kw.split(",")] if _kw else _tags
        if _kw_list:
            _lines.append(f"keywords: [{', '.join(_kw_list)}]")
        if _last_edit:
            _lines.extend(["last_update:", f"  date: {_last_edit}"])
        _lines.append("---\n")
        frontmatter = "\n".join(_lines) + "\n"

    if is_parent:
        generate_category_json(f"{SAVE_DIR}/{slug}", title, order)
        if not body.strip():
            # body 없음 → index.md 불필요, 기존 파일 있으면 삭제
            if os.path.exists(new_filename):
                os.remove(new_filename)
                log(f"빈 부모 index.md 삭제: {new_filename}")
            return title, new_filename, last_edited, content_hash, order

    os.makedirs(os.path.dirname(new_filename) if os.path.dirname(new_filename) else SAVE_DIR, exist_ok=True)
    with open(new_filename, "w", encoding="utf-8") as f:
        f.write(frontmatter + body)

    return title, new_filename, last_edited, content_hash, order


def remove_orphans(synced_files, previously_tracked):
    """이전 sync에서 Notion이 만든 파일 중 이번에 사라진 것만 삭제.
    수동 작성 파일(sync map에 없던 파일)은 건드리지 않는다.
    계층 구조로 생성된 서브디렉토리도 정리한다."""
    import shutil
    if not os.path.isdir(SAVE_DIR):
        return
    section = SAVE_DIR.rstrip("/").split("/")[-1]

    # 루트 레벨 평면 파일 정리
    for fname in os.listdir(SAVE_DIR):
        if fname in SKIP_FILES or fname.startswith("."):
            continue
        if not (fname.endswith(".md") or fname.endswith(".mdx")):
            continue
        fpath = os.path.join(SAVE_DIR, fname)
        if fpath in previously_tracked and fpath not in synced_files:
            os.remove(fpath)
            log(f"미추적 파일 삭제: {fpath}")
            slug = os.path.splitext(fname)[0]
            img_dir = f"static/img/{section}/{slug}"
            if os.path.isdir(img_dir):
                shutil.rmtree(img_dir)
                log(f"연관 이미지 삭제: {img_dir}")

    # 서브디렉토리(부모 페이지 디렉토리) 정리
    for dname in os.listdir(SAVE_DIR):
        if dname.startswith("."):
            continue
        dpath = os.path.join(SAVE_DIR, dname)
        if not os.path.isdir(dpath):
            continue
        # 이 디렉토리가 sync가 만든 것인지 확인: index.md가 previously_tracked에 있었던 경우
        index_path = os.path.join(dpath, "index.md")
        if index_path not in previously_tracked:
            continue  # sync가 만들지 않은 디렉토리는 건드리지 않음
        # 해당 디렉토리의 모든 파일이 synced_files에서 제거됐는지 확인
        remaining = [f for f in synced_files if f.startswith(dpath + os.sep)]
        if not remaining:
            shutil.rmtree(dpath)
            log(f"빈 부모 디렉토리 삭제: {dpath}")
            img_dir = f"static/img/{section}/{dname}"
            if os.path.isdir(img_dir):
                shutil.rmtree(img_dir)
                log(f"연관 이미지 삭제: {img_dir}")


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
    _build_page_link_map(existing_map)
    log(f"기존 파일 {len(existing_map)}개 추적 중")

    has_more = True
    next_cursor = None
    saved = 0
    synced_files = set()

    # 전체 페이지 수집
    all_pages = []
    while has_more:
        if next_cursor:
            payload["start_cursor"] = next_cursor
        res = requests.post(url, headers=headers, json=payload)
        data = res.json()
        if res.status_code != 200 or data.get("object") == "error":
            log(f"ERROR: {data.get('message', data)}")
            sys.exit(1)

        all_pages.extend(data.get("results", []))
        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor")

    # FETCH_MODE=ALL: created_time 오름차순 정렬 후 position 배정
    if FETCH_MODE != "DAILY":
        all_pages.sort(key=lambda p: p.get("created_time", ""))
        log(f"총 {len(all_pages)}개 페이지, created_time 오름차순 정렬")

    # 부모-자식 관계 구성
    page_by_id = {p["id"]: p for p in all_pages}
    children_map = {}  # {parent_id: [child_page_id, ...]}
    for page in all_pages:
        child_ids = read_relation(page.get("properties", {}), NOTION_PROPERTY_SUBITEM)
        # DB 내에 존재하는 ID만 유효한 자식으로 인정
        valid_children = [cid for cid in child_ids if cid in page_by_id]
        if valid_children:
            children_map[page["id"]] = valid_children

    child_id_set = {cid for children in children_map.values() for cid in children}
    root_pages = [p for p in all_pages if p["id"] not in child_id_set]

    has_hierarchy = bool(children_map)
    if has_hierarchy:
        log(f"계층 구조 감지: {len(children_map)}개 부모, {len(child_id_set)}개 자식")
    else:
        log("계층 구조 없음, 평면 모드로 동작")

    def process_page(page, position, parent_slug=None, is_parent=False):
        title, filepath, last_edited, content_hash, page_order = save_doc_page(
            page, position, existing_map,
            parent_slug=parent_slug, is_parent=is_parent,
        )
        existing_map[page["id"]] = {
            "file": filepath,
            "last_edited": last_edited,
            "content_hash": content_hash,
            "order": page_order,
            "parent_id": parent_slug,
        }
        synced_files.add(filepath)
        log(f"저장: {filepath} ({title})")
        return title, filepath

    for root_position, page in enumerate(root_pages, start=1):
        page_id = page["id"]
        if page_id in children_map:
            # 부모 페이지
            parent_title, parent_filepath = process_page(
                page, root_position, is_parent=True,
            )
            parent_slug = slugify(read_title_plain(page.get("properties", {}), NOTION_PROPERTY_TITLE) or "제목없음")
            # 자식 페이지들 처리
            child_pages = [
                page_by_id[cid] for cid in children_map[page_id]
                if cid in page_by_id
            ]
            child_pages.sort(key=lambda p: p.get("created_time", ""))
            for child_position, child_page in enumerate(child_pages, start=1):
                process_page(child_page, child_position, parent_slug=parent_slug)
                saved += 1
            saved += 1
        else:
            # 루트 레벨 평면 페이지
            process_page(page, root_position)
            saved += 1

    if FETCH_MODE != "DAILY":
        previously_tracked = {
            (v["file"] if isinstance(v, dict) else v)
            for v in existing_map.values()
        }
        remove_orphans(synced_files, previously_tracked)
        existing_map = {
            k: v for k, v in existing_map.items()
            if (v["file"] if isinstance(v, dict) else v) in synced_files
        }

    save_sync_map(existing_map)
    log(f"완료: {saved}개 저장")

    # docs/* 섹션에서 sync 결과가 0개면 빌드 실패 방지용 placeholder 생성.
    # 실제 문서가 생기면 자동 제거.
    if SAVE_DIR.startswith("docs/") and FETCH_MODE != "DAILY":
        placeholder = os.path.join(SAVE_DIR, "placeholder.md")
        if not synced_files:
            if not os.path.exists(placeholder):
                with open(placeholder, "w", encoding="utf-8") as f:
                    f.write("---\ntitle: \"준비 중\"\nsidebar_position: 1\nslug: \"placeholder\"\n---\n\n콘텐츠를 준비 중입니다.\n")
                log(f"[placeholder] DB 비어 있음 → {placeholder} 생성")
        elif os.path.exists(placeholder):
            os.remove(placeholder)
            log(f"[placeholder] 실제 문서 존재 → {placeholder} 제거")


if __name__ == "__main__":
    main()
