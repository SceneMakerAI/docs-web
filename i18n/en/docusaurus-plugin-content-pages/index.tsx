import type {ReactNode} from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import Layout from '@theme/Layout';
import Heading from '@theme/Heading';

import styles from '@site/src/pages/index.module.css';
import featureStyles from '@site/src/components/HomepageFeatures/styles.module.css';
import kpiStyles from '@site/src/components/HomepageKPI/styles.module.css';

// ── Hero ──────────────────────────────────────────────────────────────────────

function HomepageHero() {
  return (
    <header className={styles.hero}>
      <div className="container">
        <div className={styles.heroInner}>
          <div className={styles.eyebrow}>
            <span>2026 NIPA Open-Source AI &amp; SW Support Program</span>
          </div>
          <Heading as="h1" className={styles.heroTitle}>
            Reprocessing broadcast content
            <br />
            with open-source AI.
          </Heading>
          <p className={styles.heroSubtitle}>
            Automatically analyze and reconstruct dramas, variety shows, and
            documentaries using multimodal LLMs. An internal Solbox project —
            4 services &amp; 30+ open-source contributions targeted.
          </p>
          <div className={styles.ctaGroup}>
            <Link className={styles.ctaPrimary} to="/docs/guide/1">
              Get Started
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

// ── Features ──────────────────────────────────────────────────────────────────

type AccentKey = 'teal' | 'pink' | 'warning' | 'light-green';

const FeatureList = [
  {
    number: '01',
    title: 'Highlights',
    accent: 'teal' as AccentKey,
    description: 'Automatically selects highlight scenes from long broadcasts using multimodal LLMs.',
  },
  {
    number: '02',
    title: 'Remix',
    accent: 'pink' as AccentKey,
    description: 'Restructures full-length videos into short-form clips or summaries based on subtitle and scene analysis.',
  },
  {
    number: '03',
    title: 'Ad Match',
    accent: 'warning' as AccentKey,
    description: 'Matches the most contextually relevant ads to content using embedding-based retrieval.',
  },
  {
    number: '04',
    title: 'Batch',
    accent: 'light-green' as AccentKey,
    description: 'Processes broadcast archives overnight in bulk. Re-analysis and re-indexing pipeline.',
  },
];

const chipClassByAccent: Record<AccentKey, string> = {
  teal: featureStyles.chipTeal,
  pink: featureStyles.chipPink,
  warning: featureStyles.chipWarning,
  'light-green': featureStyles.chipLightGreen,
};

function HomepageFeatures() {
  return (
    <section className={featureStyles.features}>
      <div className="container">
        <div className={featureStyles.sectionHeader}>
          <Heading as="h2" className={featureStyles.sectionTitle}>
            4 AI Services
          </Heading>
          <p className={featureStyles.sectionSubtitle}>
            Four broadcast-domain services built on top of multimodal LLMs.
          </p>
        </div>
        <div className="row">
          {FeatureList.map(({number, title, accent, description}, idx) => (
            <div key={idx} className={clsx('col col--3', featureStyles.cardCol)}>
              <div className={featureStyles.card}>
                <div className={clsx(featureStyles.chip, chipClassByAccent[accent])}>
                  {number}
                </div>
                <Heading as="h3" className={featureStyles.cardTitle}>
                  {title}
                </Heading>
                <p className={featureStyles.cardDescription}>{description}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ── KPI ───────────────────────────────────────────────────────────────────────

const KPIList = [
  {
    value: '30+',
    label: 'Open-source contributions',
    note: 'PRs · Issues · Datasets (cumulative)',
  },
  {
    value: '20+',
    label: 'Tech blog posts',
    note: 'Bi-weekly (cumulative)',
  },
  {
    value: '20m',
    label: 'Inference throughput',
    note: '1-hour broadcast → under 20 min',
  },
  {
    value: '0.70',
    label: 'Scene classification F1',
    note: 'Based on 40–60 min content',
    featured: true,
  },
];

function HomepageKPI() {
  return (
    <section className={kpiStyles.kpiBand}>
      <div className="container">
        <div className={kpiStyles.sectionHeader}>
          <Heading as="h2" className={kpiStyles.sectionTitle}>
            2026 Goals
          </Heading>
          <p className={kpiStyles.sectionSubtitle}>
            Public deliverables through open-source contributions and a tech blog — plus inference performance targets.
          </p>
        </div>
        <div className="row">
          {KPIList.map(({value, label, note, featured}, idx) => (
            <div key={idx} className={clsx('col col--3', kpiStyles.cellCol)}>
              <div className={clsx(kpiStyles.cell, featured && kpiStyles.cellFeatured)}>
                <div className={kpiStyles.value}>{value}</div>
                <div className={kpiStyles.label}>{label}</div>
                <div className={kpiStyles.note}>{note}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function Home(): ReactNode {
  return (
    <Layout
      title="SceneMakerAI — Reprocessing broadcast content with open-source AI"
      description="An internal Solbox project using open-source multimodal LLMs to reprocess broadcast content (dramas, variety shows, documentaries). 4 services and 30+ open-source contributions.">
      <HomepageHero />
      <main>
        <HomepageFeatures />
        <HomepageKPI />
      </main>
    </Layout>
  );
}
