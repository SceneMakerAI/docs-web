import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import translate_to_en as T


def test_protect_images_hides_parens_from_translation():
    """이미지 마크다운 전체가 placeholder로 치환되어 DeepL이 괄호를 못 본다."""
    body = "본문\n\n:::\n\n![image](/img/blog/x/img-00.png)\n\n뒷 문장"
    protected, store = T._protect_images(body)
    assert "![image](" not in protected          # 괄호가 노출되지 않음
    assert "/img/blog/x/img-00.png" not in protected
    assert len(store) == 1


def test_restore_images_survives_deepl_paren_relocation():
    """DeepL이 self-closing placeholder 앞뒤로 빈 줄을 삽입해도(실제 버그 재현)
    복원 후 이미지 마크다운이 한 줄로 온전히 살아난다."""
    body = "본문\n\n:::\n\n![image](/img/blog/x/img-00.png)\n\n뒷 문장"
    protected, store = T._protect_images(body)
    key = next(iter(store))
    # DeepL이 태그를 다른 줄로 밀어낸 상황 시뮬레이션
    deepl_out = protected.replace(key, f"\n\n{key}\n\n")
    restored = T._restore_images(deepl_out, store)
    assert "![image](/img/blog/x/img-00.png)" in restored
    # 닫는 괄호 없이 끊긴 이미지 라인이 없어야 함
    assert not re.search(r"!\[[^\]]*\]\([^)\n]*$", restored, re.MULTILINE)


def test_protect_images_multiple_and_korean_path():
    """여러 이미지 + 한글 경로 보존."""
    body = (
        "![image](/img/blog/09-맥락-기반/img-00.png)\n\n"
        "가운데\n\n"
        "![image](/img/blog/09-맥락-기반/img-01.png)"
    )
    protected, store = T._protect_images(body)
    assert len(store) == 2
    restored = T._restore_images(protected, store)
    assert restored == body


def test_translate_frontmatter_tags_only_korean_items(monkeypatch):
    """한글 태그만 번역하고 영문 태그는 그대로 둔다.

    EN 페이지에 'Tags: 업데이트 필요' 가 한글로 노출되고
    /en/blog/tags/업데이트-필요/ 라는 한글 URL 이 생겼다.
    """
    monkeypatch.setattr(T, "translate_with_deepl_plain", lambda t: "Update required")
    fm = '---\ntitle: "x"\ntags: [rag, 업데이트 필요, milvus]\n---\n\n'
    out = T._translate_frontmatter_tags(fm)
    assert "tags: [rag, Update required, milvus]" in out


def test_translate_frontmatter_tags_no_korean_skips_deepl(monkeypatch):
    """한글이 없으면 DeepL을 부르지 않고 원본 그대로 돌려준다."""
    called = []
    monkeypatch.setattr(T, "translate_with_deepl_plain", lambda t: called.append(t) or "x")
    fm = '---\ntags: [rag, milvus]\n---\n\n'
    assert T._translate_frontmatter_tags(fm) == fm
    assert called == []


def test_translate_frontmatter_tags_without_tags_line(monkeypatch):
    """tags 줄이 없으면 그대로 통과."""
    fm = '---\ntitle: "x"\n---\n\n'
    assert T._translate_frontmatter_tags(fm) == fm


def test_translate_file_translates_korean_tags_end_to_end(tmp_path, monkeypatch):
    """배선 검증 — translate_file 이 실제로 태그 번역을 거친다."""
    kr = tmp_path / "post.md"
    kr.write_text('---\ntitle: "스키마 공개"\ntags: [rag, 업데이트 필요]\n---\n\n본문\n',
                  encoding="utf-8")
    out = tmp_path / "en.md"
    monkeypatch.setattr(T, "translate_with_deepl", lambda t: t.replace("스키마 공개", "Schema Release").replace("본문", "Body"))
    monkeypatch.setattr(T, "translate_with_deepl_plain", lambda t: "Update required")
    monkeypatch.setattr(T, "kr_to_en_path", lambda p: str(out))
    T.translate_file(str(kr), {})
    en = out.read_text(encoding="utf-8")
    assert "tags: [rag, Update required]" in en
    assert "업데이트 필요" not in en
