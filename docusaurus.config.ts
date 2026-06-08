import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

const config: Config = {
  title: 'SceneMakerAI',
  tagline: '오픈소스 AI로 방송 콘텐츠를 재가공하다 — SceneMakerAI 기술 블로그 · 문서',
  favicon: 'img/favicon.svg',

  // Future flags, see https://docusaurus.io/docs/api/docusaurus-config#future
  future: {
    v4: true,
    faster: false, // 네이티브 바이너리(Rspack/SWC/lightningcss)가 이 환경에서 SIGBUS 발생
  },

  markdown: {
    format: 'detect', // .md → 'md' (plain Markdown), .mdx → 'mdx'. blog 플러그인의 MDX ESM-strict 파싱 충돌 방지
    mermaid: true,
  },

  themes: ['@docusaurus/theme-mermaid'],

  // Set the production url of your site here
  url: 'https://doc.scenemaker.solbox.com',
  // 커스텀 도메인 적용 후에는 호스트가 이 리포 전용이므로 서브패스 불필요
  baseUrl: '/',

  // GitHub pages deployment config.
  organizationName: 'SceneMakerAI', // GitHub org name
  projectName: 'docs-web',          // GitHub repo name

  onBrokenLinks: 'throw',

  headTags: [
    // 파비콘 변형 (SVG 우선 — favicon 옵션 / PNG·ICO·apple-touch-icon fallback)
    { tagName: 'link', attributes: { rel: 'icon', type: 'image/png', sizes: '32x32', href: '/img/favicon-32x32.png' } },
    { tagName: 'link', attributes: { rel: 'icon', type: 'image/png', sizes: '16x16', href: '/img/favicon-16x16.png' } },
    { tagName: 'link', attributes: { rel: 'icon', type: 'image/x-icon', href: '/img/favicon.ico' } },
    { tagName: 'link', attributes: { rel: 'apple-touch-icon', sizes: '180x180', href: '/img/apple-touch-icon.png' } },

    // Google Fonts (Geist + Inter) — design.md 의 font-display / font-body 토큰
    { tagName: 'link', attributes: { rel: 'preconnect', href: 'https://fonts.googleapis.com' } },
    { tagName: 'link', attributes: { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: 'anonymous' } },
    { tagName: 'link', attributes: { rel: 'stylesheet', href: 'https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap' } },

    // Organization 구조화 데이터 — Google 리치 결과
    {
      tagName: 'script',
      attributes: { type: 'application/ld+json' },
      innerHTML: JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'Organization',
        name: 'SceneMakerAI',
        description: '오픈소스 AI(멀티모달 LLM)로 방송 콘텐츠를 재가공하는 플랫폼',
        url: 'https://doc.scenemaker.solbox.com',
        sameAs: ['https://github.com/SceneMakerAI'],
        parentOrganization: { '@type': 'Organization', name: '솔박스(Solbox Inc.)' },
      }),
    },
  ],

  i18n: {
    defaultLocale: 'ko',
    locales: ['ko'],
    localeConfigs: {
      ko: {
        label: '한국어',
        direction: 'ltr',
        htmlLang: 'ko-KR',
        calendar: 'gregory',
        path: 'ko',
      },
    },
  },

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          editUrl: 'https://github.com/SceneMakerAI/docs-web/edit/main/',
          remarkPlugins: [remarkMath],
          rehypePlugins: [rehypeKatex],
        },
        blog: {
          path: 'blog',
          routeBasePath: 'blog',
          blogTitle: 'SceneMakerAI 블로그',
          blogDescription: 'SceneMakerAI 기술 블로그 — 오픈소스 AI로 방송 콘텐츠를 재가공하는 플랫폼 개발 이야기',
          blogSidebarTitle: '전체 글',
          blogSidebarCount: 'ALL',
          showReadingTime: true,
          readingTime: ({content}) => {
            const koreanChars = (content.match(/[가-힯]/g) ?? []).length;
            const englishWords = (
              content.replace(/[가-힯ᄀ-ᇿ㄰-㆏]/g, ' ').match(/\S+/g) ?? []
            ).length;
            const minutes = koreanChars / 500 + englishWords / 200;
            return Math.max(1, Math.round(minutes));
          },
          feedOptions: {
            type: ['rss', 'atom', 'json'],
            title: 'SceneMakerAI 블로그',
            description: 'SceneMakerAI 기술 블로그 — 오픈소스 AI로 방송 콘텐츠를 재가공하는 플랫폼 개발 이야기',
            copyright: `Copyright © ${new Date().getFullYear()} SceneMakerAI · Solbox Inc.`,
            language: 'ko',
            limit: false,
          },
          onInlineTags: 'warn',
          onInlineAuthors: 'warn',
          remarkPlugins: [remarkMath],
          rehypePlugins: [rehypeKatex],
        },
        theme: {
          customCss: [
            './src/css/custom.css',
            require.resolve('katex/dist/katex.min.css'),
          ],
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    metadata: [
      {
        name: 'keywords',
        content: 'SceneMakerAI, 오픈소스 AI, 방송 콘텐츠 재가공, 멀티모달 LLM, Qwen, STT, 자막 생성, 클립 추출, 하이라이트, NIPA, 솔박스',
      },
      { name: 'twitter:card', content: 'summary_large_image' },
    ],
    // OpenGraph / Twitter card 공용 이미지 — sample.pen hero 톤, gemini-3-pro-image-preview 로 생성
    image: 'img/og.jpg',
    colorMode: {
      respectPrefersColorScheme: true,
    },
    tableOfContents: {
      minHeadingLevel: 2,
      maxHeadingLevel: 5,
    },
    navbar: {
      title: 'SceneMakerAI',
      logo: {
        alt: 'SceneMakerAI Logo',
        src: '/img/logo.svg',
        srcDark: '/img/logo-dark.svg',
      },
      items: [
        {type: 'docSidebar', sidebarId: 'aboutSidebar', label: '프로젝트 소개', position: 'left'},
        {
          type: 'docSidebar',
          sidebarId: 'architectureSidebar',
          position: 'left',
          label: '아키텍처',
        },
        {
          type: 'docSidebar',
          sidebarId: 'installSidebar',
          position: 'left',
          label: '설치',
        },
        {
          type: 'docSidebar',
          sidebarId: 'pocSidebar',
          position: 'left',
          label: 'PoC',
        },
        {
          type: 'docSidebar',
          sidebarId: 'docsSidebar',
          position: 'left',
          label: '문서',
        },
        {to: '/blog', label: '블로그', position: 'left'},
        {type: 'docSidebar', sidebarId: 'contributeSidebar', position: 'left', label: '오픈소스 기여'},
        {type: 'docSidebar', sidebarId: 'releaseNotesSidebar', position: 'left', label: '릴리즈 노트'},
        {
          href: 'https://github.com/SceneMakerAI/docs-web',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: '문서',
          items: [
            {
              label: '시작하기',
              to: '/docs/guide/1',
            },
            {
              label: '아키텍처',
              to: '/docs/architecture',
            },
          ],
        },
        {
          title: '커뮤니티',
          items: [
            {
              label: 'Hugging Face',
              href: 'https://huggingface.co/Qwen',
            },
            {
              label: 'LangChain',
              href: 'https://www.langchain.com/',
            },
          ],
        },
        {
          title: '더 보기',
          items: [
            {
              label: '블로그',
              to: '/blog',
            },
            {
              label: 'GitHub',
              href: 'https://github.com/SceneMakerAI/docs-web',
            },
            {
              label: 'Solbox',
              href: 'https://solbox.com',
            },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} SceneMakerAI · Solbox Inc. Built with Docusaurus.`,
    },
    prism: {
      theme: prismThemes.oneDark,
      darkTheme: prismThemes.oneDark,
      additionalLanguages: ['bash', 'shell-session', 'json'],
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
