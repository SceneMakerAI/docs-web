import type {ReactNode} from 'react';
import clsx from 'clsx';
import Translate, {translate} from '@docusaurus/Translate';
import Heading from '@theme/Heading';
import styles from './styles.module.css';

type AccentKey = 'teal' | 'pink' | 'warning' | 'light-green';

type FeatureItem = {
  number: string;
  title: string;
  description: ReactNode;
  accent: AccentKey;
};

const FeatureList: FeatureItem[] = [
  {
    number: '01',
    title: translate({id: 'homepage.features.highlight.title', message: '모아보기'}),
    accent: 'teal',
    description: (
      <Translate id="homepage.features.highlight.desc">
        긴 방송에서 하이라이트 장면을 멀티모달 LLM으로 자동 선별합니다.
      </Translate>
    ),
  },
  {
    number: '02',
    title: translate({id: 'homepage.features.remix.title', message: '리믹스'}),
    accent: 'pink',
    description: (
      <Translate id="homepage.features.remix.desc">
        본편 영상을 숏폼·요약본으로 재구성합니다. 자막·장면 분석 기반.
      </Translate>
    ),
  },
  {
    number: '03',
    title: translate({id: 'homepage.features.ad.title', message: '광고'}),
    accent: 'warning',
    description: (
      <Translate id="homepage.features.ad.desc">
        콘텐츠 맥락에 가장 어울리는 광고를 매칭합니다. 임베딩·검색 기반.
      </Translate>
    ),
  },
  {
    number: '04',
    title: translate({id: 'homepage.features.batch.title', message: 'Batch'}),
    accent: 'light-green',
    description: (
      <Translate id="homepage.features.batch.desc">
        방송 아카이브를 야간 배치로 일괄 분석합니다. 재처리·재인덱싱 파이프라인.
      </Translate>
    ),
  },
];

const chipClassByAccent: Record<AccentKey, string> = {
  teal: styles.chipTeal,
  pink: styles.chipPink,
  warning: styles.chipWarning,
  'light-green': styles.chipLightGreen,
};

function Feature({number, title, description, accent}: FeatureItem) {
  return (
    <div className={clsx('col col--3', styles.cardCol)}>
      <div className={styles.card}>
        <div className={clsx(styles.chip, chipClassByAccent[accent])}>
          {number}
        </div>
        <Heading as="h3" className={styles.cardTitle}>
          {title}
        </Heading>
        <p className={styles.cardDescription}>{description}</p>
      </div>
    </div>
  );
}

export default function HomepageFeatures(): ReactNode {
  return (
    <section className={styles.features}>
      <div className="container">
        <div className={styles.sectionHeader}>
          <Heading as="h2" className={styles.sectionTitle}>
            <Translate id="homepage.features.section.title">4대 AI 서비스</Translate>
          </Heading>
          <p className={styles.sectionSubtitle}>
            <Translate id="homepage.features.section.subtitle">
              멀티모달 LLM 위에 방송 도메인 4가지 서비스를 제공합니다.
            </Translate>
          </p>
        </div>
        <div className="row">
          {FeatureList.map((props, idx) => (
            <Feature key={idx} {...props} />
          ))}
        </div>
      </div>
    </section>
  );
}
