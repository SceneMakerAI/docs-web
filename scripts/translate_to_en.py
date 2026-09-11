"""
translate_to_en.py — docs/ + blog/ 파일을 DeepL로 번역하여 i18n/en/ 에 저장

매주 GitHub Actions (weekly-translate.yml) 에서 실행.
body SHA-256 해시를 .notion-translate-hashes.json 에 캐시해
내용이 동일한 파일은 DeepL 호출 없이 스킵한다.

Env vars:
  DEEPL_API_KEY   DeepL API 키 (Free: :fx 로 끝남, Pro: 일반 키)
"""
import hashlib
import html
import json
import os
import re
import sys
import requests


DEEPL_API_KEY = os.environ.get("DEEPL_API_KEY", "")
HASH_FILE = ".notion-translate-hashes.json"

EN_DOCS_DIR = "i18n/en/docusaurus-plugin-content-docs/current/"
EN_BLOG_DIR = "i18n/en/docusaurus-plugin-content-blog/"
KR_AUTHORS_YML = "blog/authors.yml"
EN_AUTHORS_YML = EN_BLOG_DIR + "authors.yml"

_PROG_LANG_PROTECT = {
    'bash', 'sh', 'shell', 'python', 'py', 'javascript', 'js',
    'typescript', 'ts', 'yaml', 'yml', 'json', 'toml', 'ini',
    'sql', 'css', 'scss', 'html', 'xml', 'java', 'cpp', 'c',
    'csharp', 'go', 'rust', 'ruby', 'php', 'swift', 'kotlin',
    'r', 'diff', 'dockerfile', 'makefile',
    'mermaid',  # 사전 번역 후 이중 번역 방지
}

# 주석이 # 으로 시작하는 언어 (한국어 주석만 번역)
_HASH_COMMENT_LANGS = {'bash', 'sh', 'shell', 'python', 'py', 'r', 'makefile'}
# 주석이 // 로 시작하는 언어
_SLASH_COMMENT_LANGS = {'javascript', 'js', 'typescript', 'ts', 'java', 'cpp', 'c', 'csharp', 'go', 'rust', 'swift', 'kotlin'}

_KO_RE = re.compile(r'[가-힣]')


def log(msg):
    print(f"[translate] {msg}", flush=True)


def _protect_code_blocks(body):
    store = {}

    def replacer(m):
        lang = m.group(1).strip().lower()
        if lang in _PROG_LANG_PROTECT:
            key = f'__CODE{len(store)}__'
            store[key] = m.group(0)
            return key
        return m.group(0)

    protected = re.sub(r'```(\w*)\n[\s\S]*?```', replacer, body)
    return protected, store


def _restore_code_blocks(body, store):
    for key, val in store.items():
        body = body.replace(key, val)
    return body


def _protect_images(body):
    """이미지 마크다운 전체(![alt](/url))를 placeholder 태그로 보호.
    URL만 보호하면 DeepL(tag_handling=html)이 self-closing 태그 뒤 ) 를
    다음 줄로 밀어내 이미지 구문을 깨뜨린다 — 구문 전체를 감춰 괄호를 못 보게 한다."""
    store = {}

    def _sub(m):
        key = f'<x id="IMG{len(store)}"/>'
        store[key] = m.group(0)
        return key

    protected = re.sub(r'!\[[^\]]*\]\((/[^)]+)\)', _sub, body)
    return protected, store


def _restore_images(body, store):
    for key, val in store.items():
        body = body.replace(key, val)
    return body


def _protect_blockquotes(body):
    """blockquote '> ' 마커를 placeholder 태그로 보호.

    tag_handling="html" 이 <x .../> 를 그대로 보존하므로 DeepL 이 '> ' 를 태그 이름으로
    바꿔먹는 것을 막는다. 내용이 있는 줄은 BQ, 빈 '>' 줄은 BQE 로 구분한다 —
    분리된 마커를 다시 붙일 때(_rejoin_blockquote_markers) 빈 줄이 뒤 문단을
    끌어당기면 안 되기 때문.
    """
    store = {}

    def _sub(m):
        line_end = body.find("\n", m.end())
        rest = body[m.end():] if line_end == -1 else body[m.end():line_end]
        kind = "BQ" if rest.strip() else "BQE"
        key = f'<x id="{kind}{len(store)}"/>'
        store[key] = m.group(0)
        return key

    return re.sub(r'^> ?', _sub, body, flags=re.MULTILINE), store


def _restore_blockquotes(body, store):
    for key, val in store.items():
        body = body.replace(key, val)
    return body


def _unglue_html_comments(body):
    """DeepL 이 마커 placeholder 뒤에 붙여 내보낸 HTML 주석을 마커 앞으로 되돌린다.

    실제 응답: '<x id="HDR1"/><!--truncate-->\\n\\n  Collect' — 그대로 복원하면
    '### <!--truncate-->' 라는 제목이 생기고 진짜 제목 텍스트는 문단으로 떨어진다
    (실제 사례: /en/blog/7·8·16·19·20).

    KO 원문은 <!--truncate--> 가 항상 제목보다 앞에 오므로, 앞으로 옮기는 것이
    원문 순서를 되살리는 것이기도 하다.
    """
    return re.sub(r'(<x id="(?:HDR|BQ)\d+"/>)(<!--.*?-->)', r'\2\n\n\1', body)


def _rejoin_marker_tags(body, prefix, sep=" "):
    """DeepL 이 마커 placeholder 와 본문 사이에 넣은 줄바꿈을 제거해 다시 한 줄로 만든다.

    DeepL 은 문맥이 길어지면 <x id="…"/> 를 뒤따르던 본문에서 떼어내 별도 줄로 내보낸다.
    그대로 복원하면 마커만 남은 빈 블록 + 밖으로 떨어진 문단이 된다
    (실제 사례: '<x id="BQ1"/>\\n\\nTable Implementation' → 빈 인용문 /en/blog/6,
     '<x id="HDR1"/>\\n\\n\\n\\nConclusion' → 빈 제목 /en/blog/14).

    뒤가 또 다른 같은 종류 마커면 붙이지 않는다 — 붙이면 '> > ' 중첩 인용이나
    제목 마커 중복이 된다. 본문은 연속 마커 중 마지막 것에만 붙는다.
    구분선(HR) 과 HTML 주석(<!--truncate--> 등) 도 붙이지 않는다 — 본문이 통째로
    유실됐을 때 다음 블록을 제목 안으로 끌어올려 '### ---' · '### <!--truncate-->'
    를 만들고, 빈 제목 복구(_fill_empty_headings)까지 막는다.

    Args:
        prefix: 마커 종류 ("BQ" 는 BQE(빈 인용 줄)까지 함께 걸러진다).
        sep: 마커와 본문 사이에 되돌릴 구분자 — 인용문은 "", 제목은 " ".
    """
    pat = rf'(<x id="{prefix}\d+"/>)\n+[ \t]*(?!<x id="(?:HR|{prefix})|<!--)(?=\S)'
    return re.sub(pat, lambda m: m.group(1) + sep, body)


def _rejoin_blockquote_markers(body):
    """인용문 마커 재결합 — 마커와 본문 사이에 구분자가 없다."""
    return _rejoin_marker_tags(body, "BQ", sep="")


def _protect_inline_code(body):
    store = {}
    result = []
    i = 0
    for m in re.finditer(r'``[^`]+``|`[^`\n]+`', body):
        result.append(body[i:m.start()])
        key = f'__INLINE{len(store)}__'
        store[key] = m.group(0)
        result.append(key)
        i = m.end()
    result.append(body[i:])
    return ''.join(result), store


def _restore_inline_code(body, store):
    for key, val in store.items():
        body = body.replace(key, val)
    return body


def translate_with_deepl(text):
    if not text.strip():
        return text
    endpoint = (
        "https://api-free.deepl.com/v2/translate"
        if DEEPL_API_KEY.endswith(":fx")
        else "https://api.deepl.com/v2/translate"
    )
    resp = requests.post(
        endpoint,
        headers={"Authorization": f"DeepL-Auth-Key {DEEPL_API_KEY}"},
        json={"text": [text], "source_lang": "KO", "target_lang": "EN-US", "tag_handling": "html"},
    )
    if resp.status_code != 200:
        log(f"DeepL 오류 {resp.status_code}: {resp.text[:200]}")
        return text
    return resp.json()["translations"][0]["text"]


def clean_frontmatter_value(text):
    """DeepL 번역 결과를 frontmatter `key: "..."` 값으로 안전하게 정리.
    HTML 엔티티(&quot; 등)를 되돌리고, YAML 큰따옴표 문자열을 깨는 내부 " 를 \\" 로 이스케이프."""
    return html.unescape(text).replace('"', '\\"')


def translate_with_deepl_plain(text):
    """tag_handling 없이 번역 — mermaid·코드 주석용."""
    if not text.strip():
        return text
    endpoint = (
        "https://api-free.deepl.com/v2/translate"
        if DEEPL_API_KEY.endswith(":fx")
        else "https://api.deepl.com/v2/translate"
    )
    resp = requests.post(
        endpoint,
        headers={"Authorization": f"DeepL-Auth-Key {DEEPL_API_KEY}"},
        json={"text": [text], "source_lang": "KO", "target_lang": "EN-US"},
    )
    if resp.status_code != 200:
        log(f"DeepL 오류 {resp.status_code}: {resp.text[:200]}")
        return text
    return resp.json()["translations"][0]["text"]


def _protect_inline_in_line(line):
    """한 줄 내 인라인 코드를 플레이스홀더로 보호. (store, protected_line) 반환."""
    store = {}

    def _sub(m):
        key = f'\x01INLN{len(store)}\x01'
        store[key] = m.group(0)
        return key

    protected = re.sub(r'``[^`]+``|`[^`\n]+`', _sub, line)
    return store, protected


def _pretranslate_mermaid_blocks(body):
    """Mermaid 블록 내 한국어를 사전 번역. 인라인 코드는 보호."""
    def _handle(m):
        content = m.group(1)
        if not _KO_RE.search(content):
            return m.group(0)
        inline_store = {}

        def _sub(im):
            key = f'\x01INMER{len(inline_store)}\x01'
            inline_store[key] = im.group(0)
            return key

        protected = re.sub(r'``[^`]+``|`[^`\n]+`', _sub, content)
        translated = translate_with_deepl_plain(protected)
        for key, val in inline_store.items():
            translated = translated.replace(key, val)
        return f'```mermaid\n{translated.rstrip()}\n```'

    return re.sub(r'```mermaid\n([\s\S]*?)\n```', _handle, body)


def _pretranslate_all_code_korean(body):
    """모든 코드 블록 (no-lang 포함, mermaid 제외) 내 한국어가 포함된 줄을 사전 번역."""
    def _handle(m):
        lang = m.group(1).strip().lower()
        if lang == 'mermaid':
            return m.group(0)
        content = m.group(2)
        if not _KO_RE.search(content):
            return m.group(0)

        lines = content.split('\n')
        changed = False
        for i, line in enumerate(lines):
            if not _KO_RE.search(line):
                continue
            inline_store, protected = _protect_inline_in_line(line)
            translated = translate_with_deepl_plain(protected)
            for key, val in inline_store.items():
                translated = translated.replace(key, val)
            if translated.strip():
                lines[i] = translated
                changed = True

        if not changed:
            return m.group(0)
        return f'```{m.group(1)}\n' + '\n'.join(lines) + '```'

    return re.sub(r'```(\w*)\n([\s\S]*?)```', _handle, body)


def load_hashes():
    if os.path.exists(HASH_FILE):
        with open(HASH_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_hashes(hashes):
    with open(HASH_FILE, "w", encoding="utf-8") as f:
        json.dump(hashes, f, ensure_ascii=False, indent=2)


def _normalize_cached(cached):
    if isinstance(cached, str):
        return {"body_hash": cached, "slug": None, "sidebar_position": None}
    return cached if isinstance(cached, dict) else {}


def _frontmatter_key(frontmatter_str):
    lines = frontmatter_str.split('\n')
    key_lines = [l for l in lines if l and l not in ('---',)
                 and not l.startswith('title:') and not l.startswith('id:')]
    return hashlib.sha256('\n'.join(key_lines).encode()).hexdigest()


def kr_to_en_path(kr_path):
    """KR 소스 경로 → EN 출력 경로 반환."""
    if kr_path.startswith("docs/"):
        return EN_DOCS_DIR + kr_path[len("docs/"):]
    if kr_path.startswith("blog/"):
        return EN_BLOG_DIR + kr_path[len("blog/"):]
    return None


def collect_source_files():
    """docs/ + blog/ 하위 모든 .md 파일 경로 반환."""
    files = []
    for base in ("docs/", "blog/"):
        if not os.path.isdir(base):
            continue
        for dirpath, _dirs, filenames in os.walk(base):
            for fname in sorted(filenames):
                if fname.endswith(".md"):
                    files.append(os.path.join(dirpath, fname).replace("\\", "/"))
    return files


def cleanup_stale_en_files(source_files):
    """EN 디렉토리에 있으나 KR 소스가 없는 스테일 파일 삭제."""
    source_set = set(source_files)
    for en_base in (EN_DOCS_DIR, EN_BLOG_DIR):
        if not os.path.isdir(en_base):
            continue
        for dirpath, _dirs, filenames in os.walk(en_base):
            for fname in filenames:
                if not fname.endswith(".md"):
                    continue
                en_path = os.path.join(dirpath, fname).replace("\\", "/")
                if en_base == EN_DOCS_DIR:
                    kr_path = "docs/" + en_path[len(EN_DOCS_DIR):]
                else:
                    kr_path = "blog/" + en_path[len(EN_BLOG_DIR):]
                if kr_path not in source_set:
                    os.remove(en_path)
                    log(f"스테일 EN 파일 삭제: {en_path}")


def _fill_empty_headings(en_body, kr_body):
    """DeepL 이 통째로 빼먹은 제목 텍스트를 KO 원문 단독 번역으로 채운다.

    마커 재결합(_rejoin_marker_tags)은 '떨어진' 텍스트를 도로 붙이는 것이라
    아예 사라진 경우는 못 고친다 — '### 마무리' 가 '### ' 로 나온 실제 사례
    (/en/blog/11). 제목 개수는 마커 보호 덕에 KO 와 항상 같으므로 순서로 짝짓는다.

    코드블록이 placeholder 로 치환된 상태에서 불러야 한다 — 그렇지 않으면
    bash 주석('# ...')이 제목으로 세어져 짝이 어긋난다.
    """
    kr_titles = re.findall(r'(?m)^#{1,6} +(.+?)\s*$', kr_body)
    lines = en_body.split('\n')
    idx = -1
    for i, line in enumerate(lines):
        m = re.match(r'^(#{1,6})\s*(.*)$', line)
        if not m:
            continue
        idx += 1
        if m.group(2).strip() or idx >= len(kr_titles):
            continue
        lines[i] = f"{m.group(1)} {html.unescape(translate_with_deepl_plain(kr_titles[idx])).strip()}"
    return '\n'.join(lines)

def translate_authors_yml(hashes):
    """blog/authors.yml 의 역할 라벨(title·description)만 영어화해 EN 로케일용으로 쓴다.

    Docusaurus 는 i18n/<locale>/docusaurus-plugin-content-blog/authors.yml 이 있으면
    그걸 쓴다. 이게 없어 EN 블로그 전 페이지와 /en/blog/authors/* 에 'SceneMakerAI 팀'
    이 한글로 노출됐다.

    `name` 은 사람 이름이라 번역하지 않는다 — 로마자 표기는 본인이 정할 일이다.
    YAML 파서를 거치지 않고 줄 단위로 바꾼다: 순서·주석·들여쓰기가 그대로 남아
    KR 원본과 diff 가 읽히기 때문.
    """
    if not os.path.exists(KR_AUTHORS_YML):
        return
    raw = open(KR_AUTHORS_YML, encoding="utf-8").read()
    digest = hashlib.sha256(raw.encode()).hexdigest()
    cached = _normalize_cached(hashes.get(KR_AUTHORS_YML))
    if cached.get("body_hash") == digest and os.path.exists(EN_AUTHORS_YML):
        return

    memo = {}

    def _line(m):
        indent, key, val = m.group(1), m.group(2), m.group(3).strip()
        if not _KO_RE.search(val):
            return m.group(0)
        if val not in memo:
            memo[val] = html.unescape(translate_with_deepl_plain(val)).strip()
        return f"{indent}{key}: {memo[val]}"

    out = re.sub(r'(?m)^( +)(title|description): (.+)$', _line, raw)
    os.makedirs(os.path.dirname(EN_AUTHORS_YML), exist_ok=True)
    with open(EN_AUTHORS_YML, "w", encoding="utf-8") as f:
        f.write(out)
    hashes[KR_AUTHORS_YML] = {"body_hash": digest, "slug": None, "sidebar_position": None}
    log(f"{KR_AUTHORS_YML} → {EN_AUTHORS_YML} (역할 라벨 {len(memo)}건 번역)")
def _translate_frontmatter_tags(en_frontmatter):
    """frontmatter `tags: [...]` 중 한글 항목만 영어화한다.

    태그는 EN 페이지 하단 'Tags:' 와 /en/blog/tags/<태그>/ URL 을 만든다.
    한글 태그를 그대로 두면 EN 로케일에 한글 라벨·한글 URL 이 생긴다
    (실제 사례: /en/blog/tags/업데이트-필요/).

    영문 태그(rag, milvus 등)는 건드리지 않는다 — 번역하면 KR/EN 태그가
    불필요하게 갈린다.
    """
    m = re.search(r'^tags: \[(.+)\]$', en_frontmatter, re.MULTILINE)
    if not m:
        return en_frontmatter
    items = [t.strip() for t in m.group(1).split(',')]
    if not any(_KO_RE.search(t) for t in items):
        return en_frontmatter
    en_items = [html.unescape(translate_with_deepl_plain(t)).strip() if _KO_RE.search(t) else t
                for t in items]
    return en_frontmatter.replace(m.group(0), f'tags: [{", ".join(en_items)}]', 1)


def translate_file(kr_path, hashes):
    with open(kr_path, encoding="utf-8") as f:
        content = f.read()

    match = re.match(r"^(---\n.*?\n---\n\n)(.*)", content, re.DOTALL)
    if not match:
        log(f"frontmatter 없음, 스킵: {kr_path}")
        return

    frontmatter = match.group(1)
    body = match.group(2)
    body_hash = hashlib.sha256(body.encode()).hexdigest()

    slug_m = re.search(r'^slug:\s*"(.+)"', frontmatter, re.MULTILINE)
    pos_m  = re.search(r'^sidebar_position:\s*(\d+)', frontmatter, re.MULTILINE)
    slug = slug_m.group(1) if slug_m else ""
    pos  = pos_m.group(1)  if pos_m  else ""

    cached    = _normalize_cached(hashes.get(kr_path, {}))
    fm_hash   = _frontmatter_key(frontmatter)
    body_same = (cached.get("body_hash") == body_hash)
    meta_same = (cached.get("slug") == slug
                 and cached.get("sidebar_position") == pos
                 and cached.get("frontmatter_hash", "") == fm_hash)

    if body_same and meta_same:
        log(f"변경 없음, 스킵: {kr_path}")
        return

    en_path = kr_to_en_path(kr_path)
    if en_path is None:
        return
    os.makedirs(os.path.dirname(en_path), exist_ok=True)

    # id 필드 제거 (로케일 매칭은 파일 경로로 처리)
    en_frontmatter = re.sub(r'^id: .+\n', '', frontmatter, count=1, flags=re.MULTILINE)
    en_frontmatter = _translate_frontmatter_tags(en_frontmatter)

    def _new_cache():
        return {"body_hash": body_hash, "slug": slug, "sidebar_position": pos, "frontmatter_hash": fm_hash}

    if body_same and os.path.exists(en_path):
        with open(en_path, encoding="utf-8") as f:
            existing_en = f.read()
        en_match = re.match(r"^(---\n.*?\n---\n\n)(.*)", existing_en, re.DOTALL)
        if en_match and en_match.group(2).strip():
            kr_title_m = re.search(r'^title: "(.+)"', en_frontmatter, re.MULTILINE)
            en_title_m = re.search(r'^title: "(.+)"', en_match.group(1), re.MULTILINE)
            if kr_title_m and en_title_m:
                en_frontmatter = en_frontmatter.replace(
                    f'title: "{kr_title_m.group(1)}"',
                    f'title: "{en_title_m.group(1)}"', 1
                )
            kr_desc_m = re.search(r'^description: "(.+)"', en_frontmatter, re.MULTILINE)
            en_desc_m = re.search(r'^description: "(.+)"', en_match.group(1), re.MULTILINE)
            if kr_desc_m:
                if en_desc_m and en_desc_m.group(1) != kr_desc_m.group(1):
                    en_frontmatter = en_frontmatter.replace(
                        f'description: "{kr_desc_m.group(1)}"',
                        f'description: "{en_desc_m.group(1)}"', 1
                    )
                else:
                    en_desc = clean_frontmatter_value(translate_with_deepl(kr_desc_m.group(1)))
                    en_frontmatter = en_frontmatter.replace(
                        f'description: "{kr_desc_m.group(1)}"',
                        f'description: "{en_desc}"', 1
                    )
            with open(en_path, "w", encoding="utf-8") as f:
                f.write(en_frontmatter + en_match.group(2))
            hashes[kr_path] = _new_cache()
            log(f"frontmatter 동기화 (본문 동일): {kr_path} → {en_path}")
            return

    # 전체 번역
    title_match = re.search(r'^title: "(.+)"', en_frontmatter, re.MULTILINE)
    if title_match:
        kr_title = title_match.group(1)
        en_title = clean_frontmatter_value(translate_with_deepl(kr_title))
        en_frontmatter = en_frontmatter.replace(f'title: "{kr_title}"', f'title: "{en_title}"', 1)

    desc_match = re.search(r'^description: "(.+)"', en_frontmatter, re.MULTILINE)
    if desc_match:
        kr_desc = desc_match.group(1)
        en_desc = clean_frontmatter_value(translate_with_deepl(kr_desc))
        en_frontmatter = en_frontmatter.replace(f'description: "{kr_desc}"', f'description: "{en_desc}"', 1)

    # 사전 번역: mermaid 블록 + 모든 코드 블록 한국어 줄 (인라인 코드는 보호됨)
    body = _pretranslate_mermaid_blocks(body)
    body = _pretranslate_all_code_korean(body)
    body_no_code, code_store = _protect_code_blocks(body)
    body_no_inline, inline_store = _protect_inline_code(body_no_code)
    # Protect blockquote > markers — DeepL with tag_handling="html" can replace "> " with tag names
    body_no_inline, _bq_store = _protect_blockquotes(body_no_inline)
    # DeepL converts <hr/> to "---" which merges with next headings
    # Use an HTML tag placeholder: tag_handling="html" preserves <x ...> tags exactly
    _HR = '<x id="HR"/>'
    body_protected = re.sub(r'(?m)^---$', _HR, body_no_inline)
    # Protect heading markers (# ## ### etc.) — DeepL separates them from content, leaving empty headings
    _hdr_store: dict[str, str] = {}

    def _protect_hdr(m: re.Match) -> str:
        key = f'<x id="HDR{len(_hdr_store)}"/>'
        _hdr_store[key] = m.group(1)
        return f'{key} '

    body_protected = re.sub(r'(?m)^(#{1,6}) ', _protect_hdr, body_protected)
    # Protect ordered list markers (e.g. "2. **item**") — DeepL can corrupt them to "details." etc.
    # after </details> context; <x> tags are preserved exactly by tag_handling="html"
    _ol_store: dict[str, str] = {}

    def _protect_ol(m: re.Match) -> str:
        key = f'<x id="OL{len(_ol_store)}"/>'
        _ol_store[key] = m.group(2)          # group 2 = the number
        return f'{m.group(1)}{key}. '        # group 1 = leading spaces

    body_protected = re.sub(r'(?m)^( *)(\d+)\. ', _protect_ol, body_protected)
    # Protect images — hide the whole ![alt](/url) so DeepL can't translate Korean
    # path segments nor relocate the closing ) onto a new line (breaks the image)
    body_protected, _img_store = _protect_images(body_protected)
    translated = translate_with_deepl(body_protected) if body_no_inline.strip() else body_protected
    for key, num in _ol_store.items():
        translated = translated.replace(key, num)
    translated = _unglue_html_comments(translated)
    translated = _rejoin_marker_tags(translated, "HDR")
    for key, markers in _hdr_store.items():
        translated = translated.replace(key, markers)
    translated = _fill_empty_headings(translated, body_no_code)
    en_body = html.unescape(translated.replace(_HR, '\n\n---\n\n'))
    # Safety net: fix any ---# produced by DeepL converting <hr/> in older translations
    en_body = re.sub(r'^---(?=#{1,6} )', '---\n\n', en_body, flags=re.MULTILINE)
    # Safety net: DeepL strips space after heading markers (e.g. ###3. → ### 3.)
    en_body = re.sub(r'^(#{1,6})([^ #\n])', r'\1 \2', en_body, flags=re.MULTILINE)
    # Safety net: DeepL displaces heading marker to end of prior line
    # e.g. "content###\n\n 3.3. Title" → "content\n\n### 3.3. Title"
    en_body = re.sub(r'([^#\n])(#{1,6})\n+[ \t]*(\S)', r'\1\n\n\2 \3', en_body)
    # Safety net: DeepL separates heading marker from content with blank lines
    # e.g. "##\n\n2. Install Docker" → "## 2. Install Docker"
    en_body = re.sub(r'^(#{1,6})\n{1,3}([^#\n])', r'\1 \2', en_body, flags=re.MULTILINE)
    # Safety net: HRHR variants left when old null-byte placeholder was stripped by DeepL
    _HRHR = r'(?:\*\*HRHR\*\*|#HRHR#|-HRHR-|—HRHR—|\|HRHR\||HRHR)'
    en_body = re.sub(rf'^{_HRHR}$', '---', en_body, flags=re.MULTILINE)
    # Safety net: "****word" → "**word" — DeepL drops Korean in "**KO (EN)**" and adjacent ** merge
    en_body = re.sub(r'\*{4,}(\w)', r'**\1', en_body)
    # Safety net: DeepL prepends closing-tag name to following Markdown elements
    _TAG = r'(?:table|tbody|thead|tr|details|div|section|blockquote)'
    en_body = re.sub(rf'^{_TAG}(#{1,6} )', r'\1', en_body, flags=re.MULTILINE)
    # Bold: "tag*text**" → "**text**" (tag ate one * from opening **)
    en_body = re.sub(rf'^{_TAG}\*', '**', en_body, flags=re.MULTILINE)
    # Table row: "tag Cell | ..." → "| Cell | ..." (leading | was dropped)
    en_body = re.sub(rf'^{_TAG} ([^\n|]+\|)', r'| \1', en_body, flags=re.MULTILINE)
    # Safety net: DeepL removes blank lines after closing block HTML tags
    _BLOCK_CLOSE = r'</(table|tbody|thead|tr|details|div|section|blockquote)>'
    en_body = re.sub(rf'({_BLOCK_CLOSE})([^\n<])', r'\1\n\n\2', en_body)
    # Safety net: DeepL inserts blank lines after <br> inside table cells, breaking the row
    en_body = re.sub(r'(<br>)\n\n(?=[^|\n])', r'\1', en_body)
    en_body = re.sub(r'\n{3,}', '\n\n', en_body)
    en_body = _restore_inline_code(en_body, inline_store)
    en_body = _restore_code_blocks(en_body, code_store)
    en_body = _rejoin_blockquote_markers(en_body)
    en_body = _restore_blockquotes(en_body, _bq_store)
    en_body = _restore_images(en_body, _img_store)
    # Safety net: DeepL relocates blockquote '> ' marker mid-sentence
    # e.g. "If an>  `code` ..." → "> If an `code` ..."
    en_body = re.sub(r'^([A-Za-z][^>\n]*\S)(> +)(\S)', r'> \1 \3', en_body, flags=re.MULTILINE)

    with open(en_path, "w", encoding="utf-8") as f:
        f.write(en_frontmatter + en_body)

    hashes[kr_path] = _new_cache()
    log(f"{kr_path} → {en_path}")


def main():
    if not DEEPL_API_KEY:
        log("DEEPL_API_KEY 없음, 번역 건너뜀")
        sys.exit(0)

    hashes = load_hashes()
    source_files = collect_source_files()

    cleanup_stale_en_files(source_files)

    try:
        translate_authors_yml(hashes)
    except Exception as e:
        log(f"오류 (authors.yml): {e}")

    translated = 0
    errors = 0
    for kr_path in source_files:
        try:
            translate_file(kr_path, hashes)
            translated += 1
        except Exception as e:
            log(f"오류 ({kr_path}): {e}")
            errors += 1

    save_hashes(hashes)
    log(f"완료 — 처리: {translated}개, 오류: {errors}개")


if __name__ == "__main__":
    main()
