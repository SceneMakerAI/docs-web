import type {ReactNode} from 'react';
import clsx from 'clsx';
import Heading from '@theme/Heading';
import styles from './styles.module.css';

type KPIItem = {
  value: string;
  label: string;
  note: string;
  featured?: boolean;
};

const KPIList: KPIItem[] = [
  {
    value: '30+',
    label: '오픈소스 기여',
    note: 'PR · Issue · Dataset (누적)',
  },
  {
    value: '20+',
    label: '기술 블로그',
    note: '격주 게시 (누적)',
  },
  {
    value: '20m',
    label: '추론 처리',
    note: '1시간 방송 → 20분 이하',
  },
  {
    value: '0.70',
    label: '장면 분류 F1',
    note: '40-60분 콘텐츠 기준',
    featured: true,
  },
];

function KPICell({value, label, note, featured}: KPIItem) {
  return (
    <div className={clsx('col col--3', styles.cellCol)}>
      <div className={clsx(styles.cell, featured && styles.cellFeatured)}>
        <div className={styles.value}>{value}</div>
        <div className={styles.label}>{label}</div>
        <div className={styles.note}>{note}</div>
      </div>
    </div>
  );
}

export default function HomepageKPI(): ReactNode {
  return (
    <section className={styles.kpiBand}>
      <div className="container">
        <div className={styles.sectionHeader}>
          <Heading as="h2" className={styles.sectionTitle}>
            2026년 목표
          </Heading>
          <p className={styles.sectionSubtitle}>
            오픈소스 생태계 기여와 기술 블로그를 통한 공개 산출물 — 그리고 추론 성능 목표.
          </p>
        </div>
        <div className="row">
          {KPIList.map((item, idx) => (
            <KPICell key={idx} {...item} />
          ))}
        </div>
      </div>
    </section>
  );
}
