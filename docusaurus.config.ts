import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

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
  ],

  i18n: {
    defaultLocale: 'ko',
    locales: ['ko', 'en'],
    localeConfigs: {
      ko: {
        label: '한국어',
        direction: 'ltr',
        htmlLang: 'ko-KR',
        calendar: 'gregory',
        path: 'ko',
      },
      en: {
        label: 'English',
        direction: 'ltr',
        htmlLang: 'en-US',
        calendar: 'gregory',
        path: 'en',
      },
    },
  },

  plugins: [],

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          editUrl: 'https://github.com/SceneMakerAI/docs-web/edit/main/',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    // OpenGraph / Twitter card 공용 이미지 — sample.pen hero 톤, gemini-3-pro-image-preview 로 생성
    image: 'img/og.jpg',
    colorMode: {
      respectPrefersColorScheme: true,
    },
    tableOfContents: {
      minHeadingLevel: 2,
      maxHeadingLevel: 4,
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
        {type: 'docSidebar', sidebarId: 'blogSidebar', position: 'left', label: '블로그'},
        {
          type: 'docSidebar',
          sidebarId: 'contributeSidebar',
          position: 'left',
          label: '오픈소스 기여',
        },
        {
          type: 'docSidebar',
          sidebarId: 'releaseNotesSidebar',
          position: 'left',
          label: '릴리즈 노트',
        },
        {
          type: 'localeDropdown',
          position: 'right',
        },
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
              to: '/docs/intro',
            },
            {
              label: '아키텍처',
              to: '/docs/architecture',
            },
            {
              label: '오픈소스 기여',
              to: '/docs/contribute',
            },
            {
              label: '릴리즈 노트',
              to: '/docs/release-notes',
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
              to: '/docs/blog',
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
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
