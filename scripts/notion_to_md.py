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
            content = f'<a href="{_html.escape(href)}">{content}</a>'
        parts.append(content)
    return "".join(parts)

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


def generate_category_json(dir_path, label, position):
    # generated-index: slug: "/" 절대경로 충돌 없이 /docs/poc/{slug} 자동 생성
    data = {"label": label, "position": position,
            "link": {"type": "generated-index"}}
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


def indent_md(text, prefix="  "):
    lines = text.rstrip("\n").splitlines()
    return "\n".join(prefix + line if line.strip() else line for line in lines) + "\n"


def block_to_markdown(block, slug, image_counter):
    b_type = block["type"]
    children = block.get("_children", [])

    def render_children():
        return "".join(block_to_markdown(c, slug, image_counter) for c in children)

    if b_type == "table":
        if not children:
            return ""
        has_color = any(
            _get_cell_bg(cell)
            for row in children
            for cell in row.get("table_row", {}).get("cells", [])
        )
        if has_color:
            lines = ["<table>"]
            for i, row in enumerate(children):
                cells = row.get("table_row", {}).get("cells", [])
                tag = "th" if i == 0 else "td"
                if i == 0:
                    lines.append("<thead><tr>")
                else:
                    if i == 1:
                        lines.append("<tbody>")
                    lines.append("<tr>")
                for cell in cells:
                    bg = _get_cell_bg(cell)
                    text = _rich_text_to_html(cell)
                    attr = f' data-notion-bg="{bg}"' if bg else ""
                    lines.append(f"<{tag}{attr}>{text}</{tag}>")
                lines.append("</tr></thead>" if i == 0 else "</tr>")
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
            if i == 0:
                sep = " | ".join("---" for _ in cells)
                lines.append(f"| {sep} |")
        return "\n".join(lines) + "\n\n"

    elif b_type in ("column_list", "column"):
        return render_children()

    elif b_type in (
        "paragraph", "heading_1", "heading_2", "heading_3", "heading_4",
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
                return f"1. {content}\n{indent_md(child_md, '   ')}\n"
            return f"1. {content}\n\n"
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
        raw_lang = block["code"].get("language", "text")
        language = _NOTION_LANG_MAP.get(raw_lang.lower(), raw_lang)
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


def blocks_to_markdown(blocks, slug):
    image_counter = [0]
    body = "".join(block_to_markdown(b, slug, image_counter) for b in blocks)
    body = escape_mdx_angle_brackets(body)
    return escape_single_tildes(body)


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
    props = page.get("properties", {})
    title = read_title_plain(props, NOTION_PROPERTY_TITLE) or "제목없음"
    order = position

    slug = slugify(title)

    if is_parent:
        new_filename = f"{SAVE_DIR}/{slug}/index.md"
        url_slug = slug  # "/"는 Docusaurus 절대경로(/docs/)로 해석 → 카테고리 slug 사용
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

    if (last_edited and stored_last_edited == last_edited
            and old_filename == new_filename
            and os.path.exists(new_filename)
            and stored_order == order
            and stored_parent == current_parent_id):
        log(f"변경 없음, 스킵: {title}")
        if is_parent:
            # _category_.json이 없으면 재생성
            cat_path = f"{SAVE_DIR}/{slug}/_category_.json"
            if not os.path.exists(cat_path):
                generate_category_json(f"{SAVE_DIR}/{slug}", title, order)
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
    # 부모 index.md는 id를 생략 → Docusaurus가 파일경로 기반으로 ID 부여 (section/slug/index)
    # 자식·평면 페이지는 id를 명시 (section 내 고유 식별자)
    if is_parent:
        frontmatter = (
            f"---\n"
            f'title: "{safe_title}"\n'
            f"sidebar_position: {order}\n"
            f'slug: "{url_slug}"\n'
            f"---\n\n"
        )
    else:
        frontmatter = (
            f"---\n"
            f"id: {slug}\n"
            f'title: "{safe_title}"\n'
            f"sidebar_position: {order}\n"
            f'slug: "{url_slug}"\n'
            f"---\n\n"
        )

    os.makedirs(os.path.dirname(new_filename) if os.path.dirname(new_filename) else SAVE_DIR, exist_ok=True)
    with open(new_filename, "w", encoding="utf-8") as f:
        f.write(frontmatter + body)

    if is_parent:
        generate_category_json(f"{SAVE_DIR}/{slug}", title, order)

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


if __name__ == "__main__":
    main()
