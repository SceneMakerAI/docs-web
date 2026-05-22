"""
translate_to_en.py — 변경된 docs/ 파일을 DeepL로 번역하여 docs_en/ 저장

마지막 번역 시점의 git commit hash를 .notion-translate-ref 에 저장하고,
다음 실행 시 그 시점부터 HEAD까지 diff하여 누적 변경을 모두 반영한다.

Env vars:
  DEEPL_API_KEY   DeepL API 키 (Free: :fx 로 끝남, Pro: 일반 키)
"""
import hashlib
import json
import os
import re
import sys
import subprocess
import requests


DEEPL_API_KEY = os.environ.get("DEEPL_API_KEY", "")
REF_FILE = ".notion-translate-ref"
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


def load_translate_ref():
    if os.path.exists(REF_FILE):
        ref = open(REF_FILE).read().strip()
        return ref or None
    return None


def save_translate_ref():
    r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
    with open(REF_FILE, "w") as f:
        f.write(r.stdout.strip())


def get_changed_docs_files(base_ref=None):
    """base_ref 이후 docs/ 에서 변경·추가된 .md 파일 목록 반환.
    base_ref 없으면 docs/ 전체를 반환 (최초 실행)."""
    if base_ref:
        r1 = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACM", f"{base_ref}..HEAD", "--", "docs/"],
            capture_output=True, text=True,
        )
    else:
        r1 = subprocess.run(["git", "ls-files", "docs/"], capture_output=True, text=True)

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


def get_deleted_docs_files(base_ref=None):
    """base_ref 이후 docs/ 에서 삭제된 .md 파일 목록 반환."""
    if not base_ref:
        return []
    r = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=D", f"{base_ref}..HEAD", "--", "docs/"],
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

    # frontmatter + body 분리
    match = re.match(r"^(---\n.*?\n---\n\n)(.*)", content, re.DOTALL)
    if not match:
        log(f"frontmatter 없음, 스킵: {kr_path}")
        return

    frontmatter = match.group(1)
    body = match.group(2)

    # body 해시 비교 — 내용이 동일하면 DeepL 호출 건너뜀
    body_hash = hashlib.sha256(body.encode()).hexdigest()
    if hashes.get(kr_path) == body_hash:
        log(f"내용 동일, 번역 스킵: {kr_path}")
        return

    # EN frontmatter에서 id 제거 (파일 경로로 locale 매칭)
    frontmatter = re.sub(r'^id: .+\n', '', frontmatter, count=1, flags=re.MULTILINE)

    # title 번역
    title_match = re.search(r'^title: "(.+)"', frontmatter, re.MULTILINE)
    if title_match:
        kr_title = title_match.group(1)
        en_title = translate_with_deepl(kr_title)
        frontmatter = frontmatter.replace(f'title: "{kr_title}"', f'title: "{en_title}"', 1)

    # --- (수평선) 을 DeepL 이 테이블 구분자로 오인하지 않도록 보호
    body_protected = re.sub(r'(?m)^---$', '<hr/>', body)
    translated = translate_with_deepl(body_protected) if body.strip() else body_protected
    en_body = re.sub(r'<hr/>', '---', translated)

    # docs/section/file.md → docs_en/section/file.md
    en_path = "docs_en/" + kr_path[len("docs/"):]
    os.makedirs(os.path.dirname(en_path), exist_ok=True)

    with open(en_path, "w", encoding="utf-8") as f:
        f.write(frontmatter + en_body)

    hashes[kr_path] = body_hash
    log(f"{kr_path} → {en_path}")


def main():
    if not DEEPL_API_KEY:
        log("DEEPL_API_KEY 없음, 번역 건너뜀")
        sys.exit(0)

    base_ref = load_translate_ref()
    if base_ref:
        log(f"마지막 번역 ref: {base_ref[:8]}")
    else:
        log("초기 실행 — docs/ 전체 스캔 (해시 비교로 실제 변경만 번역)")

    hashes = load_hashes()

    deleted = get_deleted_docs_files(base_ref)
    changed = get_changed_docs_files(base_ref)

    if not changed and not deleted:
        log("번역할 변경 파일 없음")
        save_translate_ref()
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
    save_translate_ref()


if __name__ == "__main__":
    main()
