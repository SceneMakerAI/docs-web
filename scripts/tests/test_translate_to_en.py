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


def test_fill_empty_headings_recovers_dropped_text(monkeypatch):
    """DeepL이 제목 텍스트를 통째로 빼먹으면 KO 원문을 단독 번역해 채운다.

    '### 마무리' → '### ' (텍스트 유실). 재결합으로는 못 고친다 — 붙일 게 없다.
    실제 사례: /en/blog/11 (맥락 기반 광고 최적화).
    """
    monkeypatch.setattr(T, "translate_with_deepl_plain", lambda t: "Conclusion")
    kr = "### 들어가며\n\n본문\n\n### 마무리\n"
    en = "### Introduction\n\nBody\n\n### \n"
    assert T._fill_empty_headings(en, kr) == "### Introduction\n\nBody\n\n### Conclusion\n"


def test_fill_empty_headings_leaves_filled_headings(monkeypatch):
    """이미 내용이 있는 제목은 DeepL을 다시 부르지 않는다."""
    called = []
    monkeypatch.setattr(T, "translate_with_deepl_plain", lambda t: called.append(t) or "x")
    kr = "### 들어가며\n\n본문\n"
    en = "### Introduction\n\nBody\n"
    assert T._fill_empty_headings(en, kr) == en
    assert called == []


def test_fill_empty_headings_aligns_by_index(monkeypatch):
    """여러 제목 중 빈 것만, 순서에 맞는 KO 제목으로 채운다."""
    monkeypatch.setattr(T, "translate_with_deepl_plain", lambda t: f"EN:{t}")
    kr = "# 하나\n\n## 둘\n\n### 셋\n"
    en = "# One\n\n## \n\n### Three\n"
    assert T._fill_empty_headings(en, kr) == "# One\n\n## EN:둘\n\n### Three\n"


def test_translate_file_fills_dropped_heading_end_to_end(tmp_path, monkeypatch):
    """배선 검증 — translate_file 이 유실 제목 복구를 거친다."""
    kr = tmp_path / "post.md"
    kr.write_text('---\ntitle: "글"\n---\n\n### 들어가며\n\n본문\n\n### 마무리\n', encoding="utf-8")
    out = tmp_path / "en.md"
    def fake(t):
        # 두 번째 제목 텍스트를 통째로 삭제하는 DeepL 흉내
        t = re.sub(r'(<x id="HDR1"/>) 마무리', r'\1 ', t)
        return t.replace("들어가며", "Introduction").replace("본문", "Body").replace("글", "Post")
    monkeypatch.setattr(T, "translate_with_deepl", fake)
    monkeypatch.setattr(T, "translate_with_deepl_plain", lambda t: "Conclusion")
    monkeypatch.setattr(T, "kr_to_en_path", lambda p: str(out))
    T.translate_file(str(kr), {})
    en = out.read_text(encoding="utf-8")
    assert "### Conclusion" in en
    assert not re.search(r"^#{1,6}\s*$", en, re.MULTILINE)
