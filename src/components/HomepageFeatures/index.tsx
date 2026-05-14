import type {ReactNode} from 'react';
import clsx from 'clsx';
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
    title: '모아보기',
    accent: 'teal',
    description: (
      <>긴 방송에서 하이라이트 장면을 멀티모달 LLM으로 자동 선별합니다.</>
    ),
  },
  {
    number: '02',
    title: '리믹스',
    accent: 'pink',
    description: (
      <>본편 영상을 숏폼·요약본으로 재구성합니다. 자막·장면 분석 기반.</>
    ),
  },
  {
    number: '03',
    title: '광고',
    accent: 'warning',
    description: (
      <>콘텐츠 맥락에 가장 어울리는 광고를 매칭합니다. 임베딩·검색 기반.</>
    ),
  },
  {
    number: '04',
    title: 'Batch',
    accent: 'light-green',
    description: (
      <>방송 아카이브를 야간 배치로 일괄 분석합니다. 재처리·재인덱싱 파이프라인.</>
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
            4대 AI 서비스
          </Heading>
          <p className={styles.sectionSubtitle}>
            멀티모달 LLM 위에 방송 도메인 4가지 서비스를 제공합니다.
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
