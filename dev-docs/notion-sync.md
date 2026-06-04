# Notion 동기화

> [CLAUDE.md](../CLAUDE.md) 허브에서 분리한 상세 문서. 서버 crontab 운영 방식 · DB 매핑 · 동기화 내부 로직.

## 실제 운영 방식 — 서버 crontab

GitHub Actions가 아닌 **서버에서 직접 crontab으로 30분마다** 실행한다.

```
*/30 * * * * /root/docs-web/scripts/server-sync.sh >> /var/log/notion-sync.log 2>&1
```

**`scripts/server-sync.sh` 흐름:**

1. `git pull --rebase origin main` — 원격 최신 코드 반영
2. 8개 Notion DB 병렬 동기화 (`notion_to_md.py`, `FETCH_MODE=ALL`)
3. `translate_to_en.py` — 변경된 KR 파일 DeepL 번역 → `docs_en/` 저장
4. 변경사항 있으면 `git commit + push` → `deploy.yml` 트리거 → GH Pages 배포

환경변수는 `/root/docs-web/.env` 파일에서 로드한다 (레포에 포함되지 않음).

로그 확인:
```bash
tail -f /var/log/notion-sync.log
```

> 평소 콘텐츠 동기화는 서버 crontab이 전담한다. GitHub Actions는 배포(`deploy.yml`) 및 브랜치 동기화(`sync-develop.yml`, `merge-develop.yml`)만 담당한다.

---

## DB ↔ 디렉토리 매핑

| `.env` 변수 | 저장 경로 |
|------------|-----------|
| `NOTION_ABOUT` | `docs/about/` |
| `NOTION_ARCHITECTURE` | `docs/architecture/` |
| `NOTION_BLOG` | `blog/` |
| `NOTION_CONTRIBUTE` | `docs/contribute/` |
| `NOTION_DOCS` | `docs/guide/` |
| `NOTION_INSTALL` | `docs/install/` |
| `NOTION_POC` | `docs/poc/` |
| `NOTION_RELEASE` | `docs/release-notes/` |
| `NOTION_TOKEN` | API 인증 토큰 |
| `DEEPL_API_KEY` | DeepL 번역 API 키 |

## 동기화 내부 로직 (`notion_to_md.py`)

Notion "하위 항목" relation을 읽어 자동으로 계층 구조를 결정한다.

- 하위 항목 없는 페이지 → `docs/{section}/{slug}.md` (평면)
- 하위 항목 있는 부모 → `docs/{section}/{slug}/index.md` + `_category_.json` 자동 생성
- 자식 페이지 → `docs/{section}/{parent-slug}/{child-slug}.md`

| 환경변수 | 기본값 | 설명 |
|---------|--------|------|
| `NOTION_PROPERTY_SUBITEM` | `하위 항목` | Sub-items relation 속성명 |
| `NOTION_PROPERTY_PARENT` | `상위 항목` | Parent item relation 속성명 |

## 수동 동기화 (단일 섹션)

```bash
NOTION_TOKEN=... NOTION_DATABASE_ID=... SAVE_DIR=docs/guide python3 scripts/notion_to_md.py
```

### 특정 페이지 강제 재취득 (캐시 무효화)

`notion_to_md.py`는 `.notion-sync.json`에 `last_edited` 타임스탬프를 캐시해 변경 없으면 스킵한다.
Notion 원복·강제 재sync 시 캐시를 초기화해야 한다:

```bash
python3 -c "
import json
path = 'docs/{section}/.notion-sync.json'
with open(path) as f: d = json.load(f)
for v in d.values():
    if '원하는-파일명' in v.get('file', ''):
        v['last_edited'] = ''
        v['content_hash'] = ''
with open(path, 'w') as f: json.dump(d, f, ensure_ascii=False, indent=2)
"
```

---

## 알려진 변환 문제 및 수정 이력

Notion → Markdown 변환 과정에서 발생했던 버그들. **이미 수정됨** — 재발 방지를 위해 기록.

| 문제 | 원인 | 수정 방법 | 수정 위치 |
|------|------|---------|---------|
| **Mermaid 다이어그램이 코드 텍스트로 표시** | `@docusaurus/theme-mermaid` 미설치 | 패키지 설치 + `docusaurus.config.ts`에 `markdown.mermaid: true` · `themes` 추가 | `docusaurus.config.ts` |
| **코드 블록 안 `<한글>` 이 `&lt;한글&gt;`로 표시** | `escape_mdx_angle_brackets()`가 코드 블록 내부까지 이스케이프 | 코드 블록(` ``` `)을 분리 후 외부만 이스케이프 | `notion_to_md.py` `escape_mdx_angle_brackets()` |
| **`<br />` 아티팩트** | Notion 빈 단락 블록 → `<br />`로 변환 | 빈 단락 → `\n` 처리 | `notion_to_md.py` `block_to_markdown()` paragraph 분기 |
| **`<summary>**bold**` 토글 화살표 겹침** | MDX에서 `<summary>` 내 마크다운 미처리 | summary 내 `**bold**` → `<strong>bold</strong>` 변환 | `notion_to_md.py` toggle 분기 |

### Mermaid 지원 설정 (현재 적용됨)

`docusaurus.config.ts`:
```ts
markdown: {
  format: 'detect',
  mermaid: true,   // ← 추가됨
},
themes: ['@docusaurus/theme-mermaid'],  // ← 추가됨
```

Notion 코드 블록 언어를 `mermaid`로 설정하면 SVG 다이어그램으로 렌더링된다.

### 코드 블록 안 꺾쇠 (`<`, `>`) 주의사항

- Notion 코드 블록에 `<한글>` 같은 비ASCII 꺾쇠 패턴이 있으면 Docusaurus에서 정상 렌더링됨 (수정 후)
- `<ASCII>` 패턴(예: `<URL>`, `<tag>`)은 이스케이프 없이 그대로 출력됨
- 본문 일반 텍스트의 `<한글>` 은 MDX JSX 파싱 오류 방지를 위해 `&lt;한글&gt;`로 이스케이프됨 (정상 동작)
