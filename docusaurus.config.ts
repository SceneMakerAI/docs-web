import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

const config: Config = {
  title: 'SceneMakerAI',
  tagline: '오픈소스 AI로 방송 콘텐츠를 재가공하다 — SceneMakerAI 기술 블로그 · 문서',
  favicon: 'img/favicon.ico',

  // Future flags, see https://docusaurus.io/docs/api/docusaurus-config#future
  future: {
    v4: true, // Improve compatibility with the upcoming Docusaurus v4
  },

  // Set the production url of your site here
  url: 'https://scenemakerai.github.io',
  // Set the /<baseUrl>/ pathname under which your site is served
  // For GitHub pages deployment, it is often '/<projectName>/'
  baseUrl: '/docs-web/',

  // GitHub pages deployment config.
  organizationName: 'SceneMakerAI', // GitHub org name
  projectName: 'docs-web',          // GitHub repo name

  onBrokenLinks: 'throw',

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

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          editUrl: 'https://github.com/SceneMakerAI/docs-web/edit/main/',
        },
        blog: {
          showReadingTime: true,
          feedOptions: {
            type: ['rss', 'atom'],
            xslt: true,
          },
          editUrl: 'https://github.com/SceneMakerAI/docs-web/edit/main/',
          // Useful options to enforce blogging best practices
          onInlineTags: 'warn',
          onInlineAuthors: 'warn',
          onUntruncatedBlogPosts: 'warn',
        },
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    // Replace with your project's social card
    image: 'img/docusaurus-social-card.jpg',
    colorMode: {
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: 'SceneMakerAI',
      logo: {
        alt: 'SceneMakerAI Logo',
        src: 'img/logo.svg',
      },
      items: [
        {to: '/blog', label: '블로그', position: 'left'},
        {
          type: 'docSidebar',
          sidebarId: 'docsSidebar',
          position: 'left',
          label: '문서',
        },
        {
          type: 'docSidebar',
          sidebarId: 'architectureSidebar',
          position: 'left',
          label: '아키텍처',
        },
        {
          type: 'docSidebar',
          sidebarId: 'contributeSidebar',
          position: 'left',
          label: '오픈소스 기여',
        },
        {to: '/about', label: '프로젝트 소개', position: 'left'},
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
              to: '/docs/architecture/overview',
            },
            {
              label: '오픈소스 기여',
              to: '/docs/contribute/overview',
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
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
