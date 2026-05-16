import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { PREBUILT_SHOWCASE, prebuiltToConfiguratorBuild } from '../data/prebuiltShowcase';
import './BuildSuggestions.css';

/** Split catalog spec line into chips (separator •) */
function parseSpecChips(specs) {
  if (!specs || typeof specs !== 'string') return [];
  return specs
    .split(/\s*•\s*/)
    .map((s) => s.trim())
    .filter(Boolean);
}

const BuildSuggestions = () => {
  const navigate = useNavigate();
  const { setSelectedBuild } = useApp();

  const handlePrebuiltCardClick = (itemId) => {
    navigate(`/builds/prebuilt/${itemId}`);
  };

  const handlePrebuiltConfigure = (e, item) => {
    e.stopPropagation();
    setSelectedBuild(prebuiltToConfiguratorBuild(item));
    navigate('/configurator');
  };

  return (
    <div className="build-suggestions-page">
      <div className="build-suggestions-container">
        <section className="builds-prebuilt" aria-labelledby="builds-prebuilt-heading">
          <div className="builds-prebuilt-header">
            <div className="builds-prebuilt-heading">
              <p className="builds-prebuilt-tag">Prebuilt catalog</p>
              <h1 id="builds-prebuilt-heading" className="builds-prebuilt-title">
                Prebuilt PC Configurations
              </h1>
              <p className="builds-prebuilt-subtitle">
                Fixed builds with transparent specifications and PKR pricing. Open any system for full details, checkout, or
                customization.
              </p>
            </div>
          </div>
          <div className="build-cards-popular builds-prebuilt-grid">
            {PREBUILT_SHOWCASE.map((item) => (
              <div
                key={item.id}
                role="button"
                tabIndex={0}
                className={`build-card-popular ${item.cardClass}`}
                onClick={() => handlePrebuiltCardClick(item.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    handlePrebuiltCardClick(item.id);
                  }
                }}
              >
                <div className="build-card-accent" aria-hidden="true" />
                <div className="build-card-top">
                  <p className="build-card-category">{item.category}</p>
                  <h3 className="build-card-title">{item.title}</h3>
                  <p className="build-card-desc">{item.desc}</p>
                </div>
                <ul className="build-card-spec-chips" aria-label="Key specifications">
                  {parseSpecChips(item.specs).map((chip, idx) => (
                    <li key={`${item.id}-spec-${idx}`} className="build-card-spec-chip">
                      {chip}
                    </li>
                  ))}
                </ul>
                <div className="build-card-footer">
                  <div className="build-card-price-block">
                    <span className="build-card-price-label">From</span>
                    <span className="build-card-price">PKR {item.price.toLocaleString()}</span>
                  </div>
                  <button
                    type="button"
                    className="build-card-configure"
                    onClick={(e) => handlePrebuiltConfigure(e, item)}
                  >
                    Configure
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
};

export default BuildSuggestions;
