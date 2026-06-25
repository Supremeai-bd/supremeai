import React from 'react';

const SkillsPage: React.FC = () => {
  return (
    <div className="skills-page">
      <h1>Skills Management</h1>
      <p>Browse and launch available skill workflows from within the desktop app.</p>
      <section className="grid-cards">
        <article className="info-card">
          <h2>Web Scraping</h2>
          <p>Run crawlers, collect page data, and extract structured information.</p>
        </article>
        <article className="info-card">
          <h2>Content Generation</h2>
          <p>Generate drafts, summaries, or code snippets using integrated AI skills.</p>
        </article>
        <article className="info-card">
          <h2>Data Analysis</h2>
          <p>Analyze datasets and surface insights without leaving the app.</p>
        </article>
      </section>
    </div>
  );
};

export default SkillsPage;
