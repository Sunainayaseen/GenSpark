import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import MyOrders from './MyOrders';
import './SavedBuildsOrders.css';

const SavedBuildsOrders = () => {
  const [tab, setTab] = useState('saved');
  const [saved, setSaved] = useState([]);
  const navigate = useNavigate();

  useEffect(() => {
    try {
      const raw = localStorage.getItem('savedBuilds') || '[]';
      const parsed = JSON.parse(raw);
      setSaved(Array.isArray(parsed) ? parsed : []);
    } catch (_) {
      setSaved([]);
    }
  }, []);

  const handleLoad = (b) => {
    try {
      localStorage.setItem('selectedBuild', JSON.stringify(b.build || b));
      navigate('/configurator');
    } catch (_) {
      // ignore
    }
  };

  const handleDelete = (idx) => {
    const copy = [...saved];
    copy.splice(idx, 1);
    setSaved(copy);
    try {
      localStorage.setItem('savedBuilds', JSON.stringify(copy));
    } catch (_) {}
  };

  return (
    <div className="saved-builds-page">
      <div className="container">
        <h1>Saved Builds & Order History</h1>
        <div className="tabs">
          <button className={tab === 'saved' ? 'active' : ''} onClick={() => setTab('saved')}>Saved Builds</button>
          <button className={tab === 'orders' ? 'active' : ''} onClick={() => setTab('orders')}>Order History</button>
        </div>

        <div className="tab-panel">
          {tab === 'saved' ? (
            <div className="saved-list">
              {saved.length === 0 ? (
                <p>No saved builds yet. Create one in the configurator.</p>
              ) : (
                <ul>
                  {saved.map((s, i) => (
                    <li key={i} className="saved-row">
                      <div className="saved-meta">
                        <strong>{s.build?.title || s.title || `Saved ${new Date(s.saved_at || Date.now()).toLocaleString()}`}</strong>
                        <div className="saved-sub">Saved: {new Date(s.saved_at || Date.now()).toLocaleString()}</div>
                      </div>
                      <div className="saved-actions">
                        <button className="btn btn-secondary" onClick={() => handleLoad(s)}>Open</button>
                        <button className="btn btn-secondary" onClick={() => handleDelete(i)}>Delete</button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ) : (
            <div className="orders-tab">
              <MyOrders />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SavedBuildsOrders;
