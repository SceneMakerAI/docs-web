"""
translate_to_en.py — 변경된 docs/ 파일을 DeepL로 번역하여 docs_en/ 저장

git diff HEAD 기준으로 working tree 변경분을 감지하므로,
커밋 전에 실행해야 한다 (server-sync.sh 에서 Notion sync 직후 호출).
body SHA-256 해시와 slug/sidebar_position을 .notion-translate-hashes.json 에 캐시해
내용이 동일한 파일은 DeepL 호출 없이 스킵한다.
slug/sidebar_position만 바뀐 경우에는 DeepL 없이 frontmatter만 업데이트한다.

Env vars:
  DEEPL_API_KEY   DeepL API 키 (Free: :fx 로 끝남, Pro: 일반 키)
"""
import hashlib
import html
import json
import os
import re
import sys
import subprocess
import requests


DEEPL_API_KEY = os.environ.get("DEEPL_API_KEY", "")
HASH_FILE = ".notion-translate-hashes.json"


def log(msg):
    print(f"[translate] {msg}", flush=True)


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
    """구 포맷 str → 신 포맷 dict 마이그레이션."""
    if isinstance(cached, str):
        return {"body_hash": cached, "slug": None, "sidebar_position": None}
    return cached if isinstance(cached, dict) else {}


def get_changed_docs_files():
    """working tree 기준으로 docs/ 에서 변경·추가된 .md 파일 목록 반환."""
    r1 = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACM", "HEAD", "--", "docs/"],
        capture_output=True, text=True,
    )
    r2 = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "docs/"],
        capture_output=True, text=True,
    )
    files = []
    for line in (r1.stdout + r2.stdout).splitlines():
        line = line.strip()
        if line.endswith(".md") and line.startswith("docs/"):
            files.append(line)
    return files


def get_deleted_docs_files():
    """working tree 기준으로 docs/ 에서 삭제된 .md 파일 목록 반환."""
    r = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=D", "HEAD", "--", "docs/"],
        capture_output=True, text=True,
    )
    return [
        l.strip() for l in r.stdout.splitlines()
        if l.strip().endswith(".md") and l.strip().startswith("docs/")
    ]


def delete_en_file(kr_path):
    en_path = "docs_en/" + kr_path[len("docs/"):]
    if os.path.exists(en_path):
        os.remove(en_path)
        log(f"EN 파일 삭제: {en_path}")
    else:
        log(f"EN 파일 없음, 스킵: {en_path}")


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

    cached   = _normalize_cached(hashes.get(kr_path, {}))
    body_same = (cached.get("body_hash") == body_hash)
    meta_same = (cached.get("slug") == slug and cached.get("sidebar_position") == pos)

    if body_same and meta_same:
        log(f"변경 없음, 스킵: {kr_path}")
        return

    # EN frontmatter에서 id 제거 (파일 경로로 locale 매칭)
    en_frontmatter = re.sub(r'^id: .+\n', '', frontmatter, count=1, flags=re.MULTILINE)
    en_path = "docs_en/" + kr_path[len("docs/"):]
    os.makedirs(os.path.dirname(en_path), exist_ok=True)

    if body_same and os.path.exists(en_path):
        # slug/sidebar_position만 바뀐 경우 — DeepL 불필요, frontmatter만 동기화
        with open(en_path, encoding="utf-8") as f:
            existing_en = f.read()
        en_match = re.match(r"^(---\n.*?\n---\n\n)(.*)", existing_en, re.DOTALL)
        if en_match:
            # 기존 EN 제목(이미 번역됨) 보존, slug/sidebar_position 교체
            kr_title_m = re.search(r'^title: "(.+)"', en_frontmatter, re.MULTILINE)
            en_title_m = re.search(r'^title: "(.+)"', en_match.group(1), re.MULTILINE)
            if kr_title_m and en_title_m:
                en_frontmatter = en_frontmatter.replace(
                    f'title: "{kr_title_m.group(1)}"',
                    f'title: "{en_title_m.group(1)}"', 1
                )
            with open(en_path, "w", encoding="utf-8") as f:
                f.write(en_frontmatter + en_match.group(2))
            hashes[kr_path] = {"body_hash": body_hash, "slug": slug, "sidebar_position": pos}
            log(f"frontmatter 동기화 (본문 동일): {kr_path} → {en_path}")
            return

    # body 변경 → 전체 번역
    title_match = re.search(r'^title: "(.+)"', en_frontmatter, re.MULTILINE)
    if title_match:
        kr_title = title_match.group(1)
        en_title = translate_with_deepl(kr_title)
        en_frontmatter = en_frontmatter.replace(f'title: "{kr_title}"', f'title: "{en_title}"', 1)

    # --- (수평선) 을 DeepL 이 테이블 구분자로 오인하지 않도록 보호
    body_protected = re.sub(r'(?m)^---$', '<hr/>', body)
    translated = translate_with_deepl(body_protected) if body.strip() else body_protected
    en_body = html.unescape(re.sub(r'<hr/>', '---', translated))

    with open(en_path, "w", encoding="utf-8") as f:
        f.write(en_frontmatter + en_body)

    hashes[kr_path] = {"body_hash": body_hash, "slug": slug, "sidebar_position": pos}
    log(f"{kr_path} → {en_path}")


def main():
    if not DEEPL_API_KEY:
        log("DEEPL_API_KEY 없음, 번역 건너뜀")
        sys.exit(0)

    hashes = load_hashes()
    deleted = get_deleted_docs_files()
    changed = get_changed_docs_files()

    if not changed and not deleted:
        log("번역할 변경 파일 없음")
        sys.exit(0)

    if deleted:
        log(f"EN 삭제 대상 {len(deleted)}개: {deleted}")
        for path in deleted:
            delete_en_file(path)
            hashes.pop(path, None)

    if changed:
        log(f"번역 후보 {len(changed)}개 (해시 동일 시 스킵)")
        for path in changed:
            translate_file(path, hashes)

    save_hashes(hashes)


if __name__ == "__main__":
    main()
