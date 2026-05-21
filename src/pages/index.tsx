import type {ReactNode} from 'react';
import Link from '@docusaurus/Link';
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
            <span>2026 NIPA 오픈소스 AI·SW 지원사업</span>
          </div>
          <Heading as="h1" className={styles.heroTitle}>
            오픈소스 AI로
            <br />
            방송 콘텐츠를 재가공한다.
          </Heading>
          <p className={styles.heroSubtitle}>
            멀티모달 LLM으로 드라마·예능·다큐멘터리를 자동 분석·재구성합니다.
            솔박스 사내 프로젝트 — 4대 서비스 · 오픈소스 기여 30+건 목표.
          </p>
          <div className={styles.ctaGroup}>
            <Link className={styles.ctaPrimary} to="/docs/guide/scenemakerai-문서">
              문서 시작하기
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
      title="SceneMakerAI — 오픈소스 AI로 방송 콘텐츠를 재가공"
      description="오픈소스 멀티모달 LLM으로 방송 콘텐츠(드라마·예능·다큐멘터리)를 재가공하는 솔박스 사내 프로젝트. 모아보기·리믹스·광고·Batch 4대 서비스와 오픈소스 기여.">
      <HomepageHero />
      <main>
        <HomepageFeatures />
        <HomepageKPI />
      </main>
    </Layout>
  );
}
