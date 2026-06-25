import React from 'react';

const AdminPage: React.FC = () => {
  return (
    <div className="admin-page">
      <h1>Admin Dashboard</h1>
      <p>Quick access to system metrics, audit trails, and integration controls.</p>
      <section className="grid-cards">
        <article className="info-card">
          <h2>System Status</h2>
          <p>All services are currently online. Review logs and health metrics from the backend.</p>
        </article>
        <article className="info-card">
          <h2>Audit & Security</h2>
          <p>Inspect recent activity and verify admin-only workflows securely.</p>
        </article>
        <article className="info-card">
          <h2>Integrations</h2>
          <p>Manage repository connections, webhook targets, and external AI services.</p>
        </article>
      </section>
    </div>
  );
};

export default AdminPage;
