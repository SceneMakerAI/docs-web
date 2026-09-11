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


def test_rejoin_detached_heading_marker():
    """DeepL이 제목 마커와 본문 사이에 빈 줄을 넣어도 다시 붙는다.

    실제 응답: '<x id="HDR1"/>\\n\\n\\n\\nConclusion'
    → 복원 시 '###' 만 남은 빈 제목 + 별도 문단이 됐다 (/en/blog/14).
    """
    deepl_out = '<x id="HDR0"/>\n\n\n\nIntroduction\n\n본문\n'
    repaired = T._rejoin_marker_tags(deepl_out, "HDR")
    assert repaired.startswith('<x id="HDR0"/> Introduction')


def test_rejoin_marker_tags_keeps_intact_markers_untouched():
    """이미 붙어 있는 마커는 건드리지 않는다."""
    ok = '<x id="HDR0"/> Introduction\n\n본문\n'
    assert T._rejoin_marker_tags(ok, "HDR") == ok


def test_rejoin_heading_does_not_merge_two_markers():
    """마커가 연달아 있으면 서로 붙이지 않는다."""
    body = '<x id="HDR0"/>\n<x id="HDR1"/>\n\nTitle\n'
    out = T._rejoin_marker_tags(body, "HDR")
    assert '<x id="HDR0"/>\n<x id="HDR1"/> Title' in out


def test_translate_file_repairs_detached_markers_end_to_end(tmp_path, monkeypatch):
    """배선 검증 — translate_file 이 실제로 재결합을 거쳐 파일을 쓴다.

    DeepL 이 마커를 떼어내는 상황을 흉내내, 결과 파일에 빈 제목(###)이나
    빈 인용문(> )이 남지 않는지 본다. 단위 테스트만으론 호출 누락을 못 잡는다.
    """
    kr = tmp_path / "post.md"
    kr.write_text('---\ntitle: "테스트"\n---\n\n### 들어가며\n\n> 테이블 구현\n\n끝\n',
                  encoding="utf-8")
    out = tmp_path / "en.md"

    def fake_deepl(text):
        # 마커를 뒤 본문에서 떼어낸다 (실제 DeepL 응답 형태)
        text = re.sub(r'(<x id="HDR\d+"/>) ', r'\1\n\n\n\n', text)
        text = re.sub(r'(<x id="BQ\d+"/>)', r'\1\n\n', text)
        return (text.replace("들어가며", "Introduction")
                    .replace("테이블 구현", "Table Implementation")
                    .replace("끝", "End").replace("테스트", "Test"))

    monkeypatch.setattr(T, "translate_with_deepl", fake_deepl)
    monkeypatch.setattr(T, "translate_with_deepl_plain", fake_deepl)
    monkeypatch.setattr(T, "kr_to_en_path", lambda p: str(out))
    T.translate_file(str(kr), {})

    en = out.read_text(encoding="utf-8")
    assert "### Introduction" in en
    assert "> Table Implementation" in en
    assert not re.search(r"^#{1,6}\s*$", en, re.MULTILINE)   # 빈 제목 없음
    assert not re.search(r"^>\s*$", en, re.MULTILINE)        # 빈 인용문 없음


def test_rejoin_does_not_swallow_hr_placeholder():
    """제목 텍스트가 유실됐을 때 재결합이 다음 구분선(---)을 제목으로 끌어올리면 안 된다.

    '<x id="HDR1"/>\\n\\n<x id="HR"/>' → '### ---' 가 되어, 뒤이은 유실 복구까지 막혔다
    (실제 사례: /en/blog/11 '### 마무리').
    """
    body = '<x id="HDR1"/>\n\n<x id="HR"/>\n\nnext\n'
    assert T._rejoin_marker_tags(body, "HDR") == body


def test_rejoin_still_joins_normal_text():
    """정상 본문은 여전히 붙인다 — HR 차단이 과하게 걸리면 안 된다."""
    body = '<x id="HDR0"/>\n\nIntroduction\n'
    assert T._rejoin_marker_tags(body, "HDR") == '<x id="HDR0"/> Introduction\n'


def test_rejoin_does_not_swallow_html_comment():
    """재결합이 HTML 주석(<!--truncate-->)을 제목·인용문 안으로 끌어올리면 안 된다.

    '### <!--truncate-->' 가 되어 블로그 미리보기 마커가 제목으로 렌더됐다
    (실제 사례: /en/blog/7·8·16·19·20).
    """
    body = '<x id="HDR1"/>\n\n<!--truncate-->\n\nnext\n'
    assert T._rejoin_marker_tags(body, "HDR") == body
    bq = '<x id="BQ0"/>\n\n<!--truncate-->\n'
    assert T._rejoin_marker_tags(bq, "BQ", sep="") == bq


def test_unglue_html_comment_moves_it_before_marker():
    """DeepL이 제목 마커 뒤에 붙여버린 <!--truncate--> 를 마커 앞으로 되돌린다.

    실제 응답: '<x id="HDR1"/><!--truncate-->\\n\\n  Collect'
    → 그대로 두면 '### <!--truncate-->' 가 되고 제목 텍스트는 문단으로 떨어진다.
    KO 원문은 항상 주석이 제목보다 앞에 온다.
    """
    body = '<x id="HDR1"/><!--truncate-->\n\n  Collect\n'
    out = T._unglue_html_comments(body)
    assert out == '<!--truncate-->\n\n<x id="HDR1"/>\n\n  Collect\n'
    joined = T._rejoin_marker_tags(out, "HDR")
    assert '<!--truncate-->\n\n<x id="HDR1"/> Collect' in joined


def test_unglue_html_comments_leaves_normal_text():
    """주석이 붙어 있지 않으면 그대로 둔다."""
    body = '<x id="HDR0"/> Introduction\n'
    assert T._unglue_html_comments(body) == body
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
