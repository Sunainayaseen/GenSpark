import { useState, useEffect } from 'react';
import { getFlaskAdminDashboardUrl } from '../utils/flaskBase';
import './AdminPanel.css';

const AdminPanel = () => {
  const [iframeLoaded, setIframeLoaded] = useState(false);
  const [iframeSrc, setIframeSrc] = useState(''); // Login ke baad hi dashboard load – bina login access nahi

  useEffect(() => {
    const onAdminLoginSuccess = () => {
      setIframeLoaded(false);
      setIframeSrc(getFlaskAdminDashboardUrl());
    };
    window.addEventListener('flask-admin-login-success', onAdminLoginSuccess);
    return () => window.removeEventListener('flask-admin-login-success', onAdminLoginSuccess);
  }, []);

  if (!iframeSrc) {
    return (
      <div className="admin-panel-page" style={{ minHeight: 'calc(100vh - 120px)', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-secondary, #f1f5f9)' }}>
        <div style={{ textAlign: 'center', padding: '2rem', maxWidth: '400px' }}>
          <h2 style={{ marginBottom: '0.5rem', color: 'var(--text-primary, #0f172a)' }}>Admin Dashboard</h2>
          <p style={{ color: 'var(--text-muted, #64748b)', marginBottom: '1rem' }}>Login required. Use the login form above to access.</p>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-muted, #64748b)' }}>Admin: admin@genspark.com / admin123</p>
        </div>
      </div>
    );
  }

  return (
    <div className="admin-panel-page">
      <div className="admin-iframe-wrapper" style={{ position: 'relative', width: '100%', minHeight: 'calc(100vh - 120px)' }}>
        <iframe
          key={iframeSrc}
          title="Admin Dashboard (GenSpark)"
          src={iframeSrc}
          width="100%"
          height="900"
          style={{ border: 'none', display: 'block', minHeight: 'calc(100vh - 120px)' }}
          onLoad={() => setIframeLoaded(true)}
        />
        {!iframeLoaded && (
          <div style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            color: '#666',
            textAlign: 'center',
          }}>
            <p>Loading dashboard…</p>
            <p style={{ fontSize: '0.9rem', marginTop: '0.5rem' }}>
              Flask: <code>python run.py</code> (vendor dashboard folder)
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default AdminPanel;







