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
