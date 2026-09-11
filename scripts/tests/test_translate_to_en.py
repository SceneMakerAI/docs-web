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


def test_rejoin_ordered_list_markers_reattaches_and_normalizes():
    """DeepL이 숫자 목록 마커를 본문에서 떼어내고 구분자까지 바꾼 것을 되돌린다.

    실제 응답: '<x id="OL0"/>\\n\\n: Noise removal' / '<x id="OL1"/>\\n\\n. Detection'
    → 복원하면 '1' 과 ': Noise removal' 이 따로 놀아 목록이 깨진다
    (실제 사례: /en/blog/3 음성분석 5단계).
    """
    body = ('<x id="OL0"/>\n\n: Noise removal (Denoise)\n'
            '<x id="OL1"/>\n\n. Detection of human speech segments (VAD)\n')
    out = T._rejoin_ol_markers(body)
    assert out == ('<x id="OL0"/>. Noise removal (Denoise)\n'
                   '<x id="OL1"/>. Detection of human speech segments (VAD)\n')


def test_rejoin_ordered_list_markers_leaves_intact_items():
    """이미 붙어 있는 목록 항목은 그대로 둔다."""
    body = '<x id="OL0"/>. Noise removal\n<x id="OL1"/>. VAD\n'
    assert T._rejoin_ol_markers(body) == body


def test_translate_file_repairs_ordered_list_end_to_end(tmp_path, monkeypatch):
    """배선 검증 — translate_file 이 숫자 목록 복구를 거친다."""
    kr = tmp_path / "post.md"
    kr.write_text('---\ntitle: "글"\n---\n\n1. 노이즈 제거\n1. 화자 분리\n', encoding="utf-8")
    out = tmp_path / "en.md"
    def fake(t):
        t = re.sub(r'(<x id="OL0"/>)\. ', r'\1\n\n: ', t)
        t = re.sub(r'(<x id="OL1"/>)\. ', r'\1\n\n. ', t)
        return t.replace("노이즈 제거", "Denoise").replace("화자 분리", "Diarization").replace("글", "Post")
    monkeypatch.setattr(T, "translate_with_deepl", fake)
    monkeypatch.setattr(T, "translate_with_deepl_plain", fake)
    monkeypatch.setattr(T, "kr_to_en_path", lambda p: str(out))
    T.translate_file(str(kr), {})
    en = out.read_text(encoding="utf-8")
    assert "1. Denoise" in en
    assert "1. Diarization" in en
    assert not re.search(r"^\d+\s*$", en, re.MULTILINE)   # 숫자만 있는 줄 없음


def test_rejoin_ol_markers_normalizes_various_separators():
    """DeepL이 목록 구분자 '.' 를 ';' '?' ',' 등으로 바꿔도 '.' 로 되돌린다.

    실제 응답: '<x id="OL1"/>\\n\\n; semantic unit segmentation',
               '<x id="OL1"/>\\n\\n? **Response Time in Korea**'
    """
    for sep in ('.', ':', ';', '?', ',', '!'):
        body = f'<x id="OL3"/>\n\n{sep} Item text\n'
        assert T._rejoin_ol_markers(body) == '<x id="OL3"/>. Item text\n', sep


def test_rejoin_ol_markers_without_separator():
    """구분자를 통째로 떨어뜨린 경우에도 붙인다."""
    body = '<x id="OL0"/>\n\nItem text\n'
    assert T._rejoin_ol_markers(body) == '<x id="OL0"/>. Item text\n'


def test_rejoin_ol_markers_does_not_swallow_comment_or_marker():
    """다음 블록이 주석·다른 마커면 붙이지 않는다."""
    for nxt in ('<!--truncate-->', '<x id="OL1"/>', '<x id="HR"/>'):
        body = f'<x id="OL0"/>\n\n{nxt}\n'
        assert T._rejoin_ol_markers(body) == body, nxt


def test_unglue_separated_html_comment_between_marker_and_text():
    """마커와 본문 사이에 끼어든 <!--truncate--> 를 마커 앞으로 옮긴다.

    실제 응답: '<x id="OL0"/>\\n\\n<!--truncate-->\\n\\n: document structuring'
    KO 원문은 주석이 목록보다 앞에 온다.
    """
    body = '<x id="OL0"/>\n\n<!--truncate-->\n\n: document structuring\n'
    out = T._unglue_html_comments(body)
    assert out == '<!--truncate-->\n\n<x id="OL0"/>\n\n: document structuring\n'
    assert T._rejoin_ol_markers(out) == '<!--truncate-->\n\n<x id="OL0"/>. document structuring\n'


def test_translate_file_repairs_list_split_by_comment_end_to_end(tmp_path, monkeypatch):
    """배선·순서 검증 — 주석이 목록 마커와 본문 사이에 끼어든 경우까지 복구된다.

    unglue 가 OL 재결합보다 뒤에 있으면 이 테스트가 실패한다.
    """
    kr = tmp_path / "post.md"
    kr.write_text('---\ntitle: "글"\n---\n\n<!--truncate-->\n\n1. 파싱\n1. 청킹\n', encoding="utf-8")
    out = tmp_path / "en.md"
    def fake(t):
        # 주석을 첫 목록 마커 뒤로 옮기고 구분자를 ':' 로 바꾸는 DeepL 흉내
        t = t.replace('<!--truncate-->\n\n<x id="OL0"/>. ', '<x id="OL0"/>\n\n<!--truncate-->\n\n: ')
        t = re.sub(r'(<x id="OL1"/>)\. ', r'\1\n\n; ', t)
        return t.replace("파싱", "Parsing").replace("청킹", "Chunking").replace("글", "Post")
    monkeypatch.setattr(T, "translate_with_deepl", fake)
    monkeypatch.setattr(T, "translate_with_deepl_plain", fake)
    monkeypatch.setattr(T, "kr_to_en_path", lambda p: str(out))
    T.translate_file(str(kr), {})
    en = out.read_text(encoding="utf-8")
    assert "1. Parsing" in en
    assert "1. Chunking" in en
    assert "<!--truncate-->" in en
    assert not re.search(r"^\d+\s*$", en, re.MULTILINE)


def test_rejoin_sentence_split_across_hr():
    """DeepL이 영어 어순 때문에 문장 앞부분을 구분선 위로 올린 것을 되돌린다.

    실제 사례 (/en/blog/4):
      '### Introduction' / 'If you apply' / '---' / '`faster-whisper …` directly to …'
    KO 원문은 '### 들어가며' / '---' / '`faster-whisper …` 를 … 나오지 않는다.' 였다.
    """
    hr = '<x id="HR"/>'
    body = (f'### Introduction\n\nIf you apply\n\n{hr}\n\n'
            '`faster-whisper large-v3` directly to Korean broadcast content.\n')
    out = T._rejoin_sentence_across_hr(body, hr)
    assert out == (f'### Introduction\n\n{hr}\n\n'
                   'If you apply `faster-whisper large-v3` directly to '
                   'Korean broadcast content.\n')


def test_rejoin_sentence_across_hr_keeps_complete_sentences():
    """마침표로 끝난 완결 문장은 구분선 아래로 내리지 않는다."""
    hr = '<x id="HR"/>'
    body = f'A complete sentence.\n\n{hr}\n\nNext paragraph.\n'
    assert T._rejoin_sentence_across_hr(body, hr) == body


def test_rejoin_sentence_across_hr_skips_non_text_blocks():
    """제목·목록·표·주석·placeholder 는 문장 조각으로 보지 않는다."""
    hr = '<x id="HR"/>'
    for prev in ('### Heading', '- list item', '| a | b |', '<!--truncate-->',
                 '<x id="IMG0"/>', '> quote'):
        body = f'{prev}\n\n{hr}\n\nNext text.\n'
        assert T._rejoin_sentence_across_hr(body, hr) == body, prev


def test_translate_file_rejoins_sentence_across_hr_end_to_end(tmp_path, monkeypatch):
    """배선 검증 — translate_file 이 구분선 위로 올라간 문장 조각을 되돌린다."""
    kr = tmp_path / "post.md"
    kr.write_text('---\ntitle: "글"\n---\n\n### 들어가며\n\n---\n\n'
                  '`faster-whisper` 를 그대로 돌리면 자막이 이상하다.\n', encoding="utf-8")
    out = tmp_path / "en.md"
    def fake(t):
        t = t.replace('<x id="HDR0"/> 들어가며', '<x id="HDR0"/> Introduction')
        # 문장 앞머리를 HR 위로 올리는 DeepL 흉내
        t = t.replace('<x id="HR"/>\n\n__INLINE0__ 를 그대로 돌리면 자막이 이상하다.',
                      'If you apply\n\n<x id="HR"/>\n\n__INLINE0__ directly, subtitles look wrong.')
        return t.replace("글", "Post")
    monkeypatch.setattr(T, "translate_with_deepl", fake)
    monkeypatch.setattr(T, "translate_with_deepl_plain", fake)
    monkeypatch.setattr(T, "kr_to_en_path", lambda p: str(out))
    T.translate_file(str(kr), {})
    en = out.read_text(encoding="utf-8")
    assert "If you apply `faster-whisper` directly, subtitles look wrong." in en
    assert not re.search(r"^If you apply\s*$", en, re.MULTILINE)


def test_rejoin_sentence_across_hr_inline_token_form():
    """복구 시점엔 구분선이 아직 placeholder라 문장 조각과 같은 줄에 있다.

    실제 응답: '### Introduction\\n\\nIf you apply <x id="HR"/>\\n\\n`faster-whisper` directly to …'
    줄 단위로만 보면 못 잡는다 — 같은 줄 형태를 반드시 다뤄야 한다.
    """
    hr = '<x id="HR"/>'
    body = (f'### Introduction\n\nIf you apply {hr}\n\n'
            '__INLINE0__ directly to Korean broadcast content.\n')
    out = T._rejoin_sentence_across_hr(body, hr)
    assert out == (f'### Introduction\n\n{hr}\n\n'
                   'If you apply __INLINE0__ directly to Korean broadcast content.\n')


def test_rejoin_sentence_across_hr_inline_keeps_complete_sentence():
    """같은 줄이어도 완결 문장이면 옮기지 않는다."""
    hr = '<x id="HR"/>'
    body = f'A complete sentence. {hr}\n\nNext paragraph.\n'
    assert T._rejoin_sentence_across_hr(body, hr) == f'A complete sentence.\n\n{hr}\n\nNext paragraph.\n'
