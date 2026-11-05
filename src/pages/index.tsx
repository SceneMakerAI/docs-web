// ---------------------------------------------------------------
// 공개 문서사이트 홈 — Hero · Features · KPI 세 블록.
// KPI 수치(오픈소스 기여 30+ · 기술블로그 20+ · 1시간→20분 · 장면분류 F1 0.70)는
// 과제 성과지표와 직접 연결되므로, 보고 수치와 어긋나지 않게 함께 갱신한다.
// ---------------------------------------------------------------

import type {ReactNode} from 'react';
import Link from '@docusaurus/Link';
import Translate, {translate} from '@docusaurus/Translate';
import Layout from '@theme/Layout';
import Heading from '@theme/Heading';
import HomepageFeatures from '@site/src/components/HomepageFeatures';
import HomepageKPI from '@site/src/components/HomepageKPI';

import styles from './index.module.css';

function HomepageHero() {
  return (
    <header className={styles.hero}>
      <div className="container">
        <div className={styles.heroInner}>
          <div className={styles.eyebrow}>
            <span>
              <Translate id="homepage.hero.eyebrow">
                2026 NIPA 오픈소스 AI·SW 지원사업
              </Translate>
            </span>
          </div>
          <Heading as="h1" className={styles.heroTitle}>
            <Translate id="homepage.hero.title.line1">오픈소스 AI로</Translate>
            <br />
            <Translate id="homepage.hero.title.line2">
              방송 콘텐츠를 재가공한다.
            </Translate>
          </Heading>
          <p className={styles.heroSubtitle}>
            <Translate id="homepage.hero.subtitle">
              멀티모달 LLM으로 드라마·예능·다큐멘터리를 자동 분석·재구성합니다.
              솔박스 사내 프로젝트 — 4대 서비스 · 오픈소스 기여 30+건 목표.
            </Translate>
          </p>
          <div className={styles.ctaGroup}>
            <Link className={styles.ctaPrimary} to="/docs/guide">
              <Translate id="homepage.hero.cta.docs">문서 시작하기</Translate>
            </Link>
            <Link
              className={styles.ctaSecondary}
              href="https://github.com/SceneMakerAI/docs-web">
              GitHub →
            </Link>
          </div>
        </div>
      </div>
    </header>
  );
}

export default function Home(): ReactNode {
  return (
    <Layout
      title={translate({
        id: 'homepage.meta.title',
        message: 'SceneMakerAI — 오픈소스 AI로 방송 콘텐츠를 재가공',
      })}
      description={translate({
        id: 'homepage.meta.description',
        message:
          '오픈소스 멀티모달 LLM으로 방송 콘텐츠(드라마·예능·다큐멘터리)를 재가공하는 솔박스 사내 프로젝트. 모아보기·리믹스·광고·Batch 4대 서비스와 오픈소스 기여.',
      })}>
      <HomepageHero />
      <main>
        <HomepageFeatures />
        <HomepageKPI />
      </main>
    </Layout>
  );
}
