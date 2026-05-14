import type {ReactNode} from 'react';
import clsx from 'clsx';
import Heading from '@theme/Heading';
import styles from './styles.module.css';

type FeatureItem = {
  title: string;
  description: ReactNode;
};

const FeatureList: FeatureItem[] = [
  {
    title: '모아보기',
    description: (
      <>긴 방송에서 하이라이트 장면을 멀티모달 LLM 으로 자동 선별합니다.</>
    ),
  },
  {
    title: '리믹스',
    description: (
      <>본편 영상을 숏폼·요약본으로 재구성합니다. 자막·장면 분석 기반.</>
    ),
  },
  {
    title: '광고',
    description: (
      <>콘텐츠 맥락에 가장 어울리는 광고를 매칭합니다. 임베딩·검색 기반.</>
    ),
  },
  {
    title: 'Batch',
    description: (
      <>방송 아카이브를 야간 배치로 일괄 분석합니다. 재처리·재인덱싱 파이프라인.</>
    ),
  },
];

function Feature({title, description}: FeatureItem) {
  return (
    <div className={clsx('col col--3')}>
      <div className="text--center padding-horiz--md">
        <Heading as="h3">{title}</Heading>
        <p>{description}</p>
      </div>
    </div>
  );
}

export default function HomepageFeatures(): ReactNode {
  return (
    <section className={styles.features}>
      <div className="container">
        <div className="row">
          {FeatureList.map((props, idx) => (
            <Feature key={idx} {...props} />
          ))}
        </div>
      </div>
    </section>
  );
}
