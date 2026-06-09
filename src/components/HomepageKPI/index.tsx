import type {ReactNode} from 'react';
import clsx from 'clsx';
import Translate, {translate} from '@docusaurus/Translate';
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
    label: translate({id: 'homepage.kpi.oss.label', message: '오픈소스 기여'}),
    note: translate({id: 'homepage.kpi.oss.note', message: 'PR · Issue · Dataset (누적)'}),
  },
  {
    value: '20+',
    label: translate({id: 'homepage.kpi.blog.label', message: '기술 블로그'}),
    note: translate({id: 'homepage.kpi.blog.note', message: '격주 게시 (누적)'}),
  },
  {
    value: '20m',
    label: translate({id: 'homepage.kpi.infer.label', message: '추론 처리'}),
    note: translate({id: 'homepage.kpi.infer.note', message: '1시간 방송 → 20분 이하'}),
  },
  {
    value: '0.70',
    label: translate({id: 'homepage.kpi.f1.label', message: '장면 분류 F1'}),
    note: translate({id: 'homepage.kpi.f1.note', message: '40-60분 콘텐츠 기준'}),
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
            <Translate id="homepage.kpi.section.title">2026년 목표</Translate>
          </Heading>
          <p className={styles.sectionSubtitle}>
            <Translate id="homepage.kpi.section.subtitle">
              오픈소스 생태계 기여와 기술 블로그를 통한 공개 산출물 — 그리고 추론 성능 목표.
            </Translate>
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
