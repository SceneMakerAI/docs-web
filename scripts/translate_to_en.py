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

_PROG_LANG_PROTECT = {
    'bash', 'sh', 'shell', 'python', 'py', 'javascript', 'js',
    'typescript', 'ts', 'yaml', 'yml', 'json', 'toml', 'ini',
    'sql', 'css', 'scss', 'html', 'xml', 'java', 'cpp', 'c',
    'csharp', 'go', 'rust', 'ruby', 'php', 'swift', 'kotlin',
    'r', 'diff', 'dockerfile', 'makefile',
}


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
                    en_desc = translate_with_deepl(kr_desc_m.group(1))
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
        en_title = translate_with_deepl(kr_title)
        en_frontmatter = en_frontmatter.replace(f'title: "{kr_title}"', f'title: "{en_title}"', 1)

    desc_match = re.search(r'^description: "(.+)"', en_frontmatter, re.MULTILINE)
    if desc_match:
        kr_desc = desc_match.group(1)
        en_desc = translate_with_deepl(kr_desc)
        en_frontmatter = en_frontmatter.replace(f'description: "{kr_desc}"', f'description: "{en_desc}"', 1)

    body_no_code, code_store = _protect_code_blocks(body)
    body_no_inline, inline_store = _protect_inline_code(body_no_code)
    # DeepL converts <hr/> to "---" which merges with next headings — use opaque placeholder
    _HR = "\x00HRHR\x00"
    body_protected = re.sub(r'(?m)^---$', _HR, body_no_inline)
    translated = translate_with_deepl(body_protected) if body_no_inline.strip() else body_protected
    en_body = html.unescape(translated.replace(_HR, '\n\n---\n\n'))
    # Safety net: fix any ---# produced by DeepL converting <hr/> in older translations
    en_body = re.sub(r'^---(?=#{1,6} )', '---\n\n', en_body, flags=re.MULTILINE)
    en_body = re.sub(r'\n{3,}', '\n\n', en_body)
    en_body = _restore_inline_code(en_body, inline_store)
    en_body = _restore_code_blocks(en_body, code_store)

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
