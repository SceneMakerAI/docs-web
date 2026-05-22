"""
translate_to_en.py — git diff로 변경된 docs/ 파일을 DeepL로 번역하여 docs_en/ 저장

Env vars:
  DEEPL_API_KEY   DeepL API 키 (Free: :fx 로 끝남, Pro: 일반 키)
"""
import os
import re
import sys
import subprocess
import requests


DEEPL_API_KEY = os.environ.get("DEEPL_API_KEY", "")


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


def get_changed_docs_files():
    """git diff 기준으로 docs/ 에서 변경·추가된 .md 파일 목록 반환"""
    # 추적 중인 파일 중 변경·추가된 것
    r1 = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACM", "HEAD", "--", "docs/"],
        capture_output=True, text=True,
    )
    # 미추적 신규 파일
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
    """git diff 기준으로 docs/ 에서 삭제된 .md 파일 목록 반환"""
    r = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=D", "HEAD", "--", "docs/"],
        capture_output=True, text=True,
    )
    files = []
    for line in r.stdout.splitlines():
        line = line.strip()
        if line.endswith(".md") and line.startswith("docs/"):
            files.append(line)
    return files


def delete_en_file(kr_path):
    en_path = "docs_en/" + kr_path[len("docs/"):]
    if os.path.exists(en_path):
        os.remove(en_path)
        log(f"EN 파일 삭제: {en_path}")
    else:
        log(f"EN 파일 없음, 스킵: {en_path}")


def translate_file(kr_path):
    with open(kr_path, encoding="utf-8") as f:
        content = f.read()

    # frontmatter + body 분리
    match = re.match(r"^(---\n.*?\n---\n\n)(.*)", content, re.DOTALL)
    if not match:
        log(f"frontmatter 없음, 스킵: {kr_path}")
        return

    frontmatter = match.group(1)
    body = match.group(2)

    # EN frontmatter에서 id 제거 (파일 경로로 locale 매칭, id 불필요)
    frontmatter = re.sub(r'^id: .+\n', '', frontmatter, count=1, flags=re.MULTILINE)

    # title 번역
    title_match = re.search(r'^title: "(.+)"', frontmatter, re.MULTILINE)
    if title_match:
        kr_title = title_match.group(1)
        en_title = translate_with_deepl(kr_title)
        frontmatter = frontmatter.replace(f'title: "{kr_title}"', f'title: "{en_title}"', 1)

    en_body = translate_with_deepl(body) if body.strip() else body

    # docs/section/file.md → docs_en/section/file.md
    en_path = "docs_en/" + kr_path[len("docs/"):]
    os.makedirs(os.path.dirname(en_path), exist_ok=True)

    with open(en_path, "w", encoding="utf-8") as f:
        f.write(frontmatter + en_body)

    log(f"{kr_path} → {en_path}")


def main():
    if not DEEPL_API_KEY:
        log("DEEPL_API_KEY 없음, 번역 건너뜀")
        sys.exit(0)

    deleted = get_deleted_docs_files()
    changed = get_changed_docs_files()

    if not changed and not deleted:
        log("번역할 변경 파일 없음")
        sys.exit(0)

    if deleted:
        log(f"EN 삭제 대상 {len(deleted)}개: {deleted}")
        for path in deleted:
            delete_en_file(path)

    if changed:
        log(f"번역 대상 {len(changed)}개: {changed}")
        for path in changed:
            translate_file(path)


if __name__ == "__main__":
    main()
