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


def test_protect_blockquotes_distinguishes_empty_quote_lines():
    """내용 있는 '> 텍스트'와 빈 '>' 줄은 서로 다른 placeholder 종류를 받는다.
    빈 줄에 뒤 문단을 끌어붙이면 안 되기 때문."""
    body = "> 테이블 구현\n>\n> 다음 줄"
    protected, store = T._protect_blockquotes(body)
    assert 'id="BQ0"' in protected        # 내용 있음
    assert 'id="BQE1"' in protected       # 빈 줄
    assert 'id="BQ2"' in protected        # 내용 있음
    assert T._restore_blockquotes(protected, store) == body


def test_rejoin_detached_blockquote_marker():
    """DeepL이 마커와 본문 사이에 빈 줄을 넣어도(실제 버그 재현) 다시 붙는다.

    실제 응답: '<x id="BQ1"/>\\n\\nTable Implementation'
    → 복원 시 '> ' 만 남은 빈 blockquote + 별도 문단이 됐다 (/en/blog/6).
    """
    body = "- 앞 문장\n\n> 테이블 구현\n\n| 공정 | 담당 |\n"
    protected, store = T._protect_blockquotes(body)
    key = next(k for k in store if 'id="BQ0"' in k)
    deepl_out = protected.replace(f"{key}테이블 구현", f"{key}\n\nTable Implementation")
    repaired = T._rejoin_blockquote_markers(deepl_out)
    restored = T._restore_blockquotes(repaired, store)
    assert "> Table Implementation" in restored
    assert not re.search(r"^>\s*$", restored, re.MULTILINE)


def test_rejoin_keeps_consecutive_markers_on_own_lines():
    """마커가 연달아 있으면 본문은 마지막 마커에만 붙는다 — 중첩 인용(> >) 금지."""
    body = "> \n>\n> 첫 문장\n"
    protected, store = T._protect_blockquotes(body)
    last = next(k for k in store if 'id="BQ2"' in k)
    deepl_out = protected.replace(f"{last}첫 문장", f"{last}\n\nFirst sentence")
    restored = T._restore_blockquotes(T._rejoin_blockquote_markers(deepl_out), store)
    assert "> First sentence" in restored
    assert "> > " not in restored
    assert restored.count("\n") == body.count("\n")


def test_rejoin_does_not_swallow_paragraph_after_empty_quote_line():
    """빈 '>' 줄 다음의 일반 문단은 인용 안으로 끌려들어가지 않는다."""
    body = "> 인용\n>\n\n일반 문단\n"
    protected, store = T._protect_blockquotes(body)
    restored = T._restore_blockquotes(T._rejoin_blockquote_markers(protected), store)
    assert restored == body
