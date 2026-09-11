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


def test_translate_authors_yml_localizes_role_labels(tmp_path, monkeypatch):
    """authors.yml 의 title·description 만 영어화하고 나머지는 그대로 둔다.

    EN 블로그 전 페이지 하단·작성자 페이지에 'SceneMakerAI 팀' 이 한글로 노출됐다.
    """
    src = tmp_path / "authors.yml"
    src.write_text(
        "minsung:\n"
        "  name: 임민성\n"
        "  title: SceneMakerAI 팀\n"
        "  description: SceneMakerAI 멀티모달 AI 파이프라인 개발자\n"
        "  url: https://github.com/MinsungIM\n"
        "  socials:\n"
        "    github: MinsungIM\n", encoding="utf-8")
    dst = tmp_path / "en" / "authors.yml"
    monkeypatch.setattr(T, "KR_AUTHORS_YML", str(src))
    monkeypatch.setattr(T, "EN_AUTHORS_YML", str(dst))
    monkeypatch.setattr(T, "translate_with_deepl_plain",
                        lambda t: {"SceneMakerAI 팀": "SceneMakerAI Team",
                                   "SceneMakerAI 멀티모달 AI 파이프라인 개발자":
                                       "SceneMakerAI Multimodal AI Pipeline Developer"}[t])
    T.translate_authors_yml({})

    out = dst.read_text(encoding="utf-8")
    assert "title: SceneMakerAI Team" in out
    assert "description: SceneMakerAI Multimodal AI Pipeline Developer" in out
    assert "url: https://github.com/MinsungIM" in out      # 비번역 키 보존
    assert "github: MinsungIM" in out                      # 중첩 구조 보존
    assert "minsung:" in out


def test_translate_authors_yml_skips_when_unchanged(tmp_path, monkeypatch):
    """해시가 같고 산출물이 있으면 DeepL을 부르지 않는다."""
    src = tmp_path / "authors.yml"
    src.write_text("a:\n  title: SceneMakerAI 팀\n", encoding="utf-8")
    dst = tmp_path / "en" / "authors.yml"
    monkeypatch.setattr(T, "KR_AUTHORS_YML", str(src))
    monkeypatch.setattr(T, "EN_AUTHORS_YML", str(dst))
    calls = []
    monkeypatch.setattr(T, "translate_with_deepl_plain",
                        lambda t: calls.append(t) or "SceneMakerAI Team")
    hashes = {}
    T.translate_authors_yml(hashes)
    assert len(calls) == 1
    T.translate_authors_yml(hashes)          # 두 번째 호출은 스킵
    assert len(calls) == 1
