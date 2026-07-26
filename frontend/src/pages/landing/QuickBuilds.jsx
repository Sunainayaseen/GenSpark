import { useNavigate, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useApp } from '../../context/AppContext';
import { PREBUILT_SHOWCASE, prebuiltToConfiguratorBuild } from '../../data/prebuiltShowcase';
import TiltCard from '../../components/TiltCard';
import { sectionVariants, headerVariants, gridVariants, cardVariants, viewportOnce } from './motionVariants';

const QUICK_BUILD_REQUIREMENTS = {
  budget: { purpose: 'Office', budget: '50000', preferences: 'Budget-focused' },
  gaming: { purpose: 'Gaming', budget: '100000', preferences: 'Performance-focused' },
  content: { purpose: 'Content Creation', budget: '150000', preferences: 'Professional-grade' },
  ai: { purpose: 'Content Creation', budget: '200000', preferences: 'AI Workstation' },
};

export default function QuickBuilds() {
  const navigate = useNavigate();
  const { updateRequirements, setSelectedBuild } = useApp();

  const handleQuickBuild = (type) => {
    const prebuilt = PREBUILT_SHOWCASE.find((item) => item.quickKey === type);
    updateRequirements(QUICK_BUILD_REQUIREMENTS[type] || QUICK_BUILD_REQUIREMENTS.gaming);
    if (!prebuilt) {
      navigate('/builds');
      return;
    }

    setSelectedBuild(prebuiltToConfiguratorBuild(prebuilt));
    navigate('/vendor-assignment');
  };

  return (
    <motion.section
      className="quick-builds"
      initial="hidden"
      whileInView="visible"
      viewport={viewportOnce}
      variants={sectionVariants}
    >
      <div className="container">
        <motion.div className="popular-builds-header" variants={headerVariants}>
          <div className="popular-builds-heading">
            <p className="popular-builds-tag">Curated for You</p>
            <h2 className="popular-builds-title">
              <span className="title-part">Top Picks</span>{' '}
              <span className="title-accent">for Every Need</span>
            </h2>
            <p className="popular-builds-subtitle">Handpicked configurations for gaming, work, and creativity—ready to customize.</p>
          </div>
          <Link to="/builds" className="view-all-builds-btn">
            View Prebuilt PCs
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
          </Link>
        </motion.div>
        <motion.div className="build-cards-popular" variants={gridVariants}>
          <TiltCard as={motion.div} className="build-card-popular build-card-gaming" variants={cardVariants}>
            <div className="build-card-accent" />
            <p className="build-card-category">Gaming</p>
            <h3 className="build-card-title">Gaming Beast</h3>
            <p className="build-card-desc">Dominate every game at ultra settings with ray tracing.</p>
            <p className="build-card-specs">RTX 5070 Ti • Ryzen 7 9800X3D • 32GB DDR5</p>
            <div className="build-card-bottom">
              <span className="build-card-price">
                <span className="build-card-price-currency">PKR</span>
                <span className="build-card-price-amount">595,000</span>
              </span>
              <button
                type="button"
                className="build-card-configure"
                onClick={() => handleQuickBuild('gaming')}
              >
                Configure
              </button>
            </div>
          </TiltCard>

          <TiltCard as={motion.div} className="build-card-popular build-card-office" variants={cardVariants}>
            <div className="build-card-accent" />
            <p className="build-card-category">Office</p>
            <h3 className="build-card-title">Pro Workstation</h3>
            <p className="build-card-desc">Reliable performance for work, browsing, and everyday tasks.</p>
            <p className="build-card-specs">Ryzen 5 5600G • 16GB DDR4 • 512GB SSD</p>
            <div className="build-card-bottom">
              <span className="build-card-price">
                <span className="build-card-price-currency">PKR</span>
                <span className="build-card-price-amount">105,000</span>
              </span>
              <button
                type="button"
                className="build-card-configure"
                onClick={() => handleQuickBuild('budget')}
              >
                Configure
              </button>
            </div>
          </TiltCard>

          <TiltCard as={motion.div} className="build-card-popular build-card-editing" variants={cardVariants}>
            <div className="build-card-accent" />
            <p className="build-card-category">Editing</p>
            <h3 className="build-card-title">Creator Studio</h3>
            <p className="build-card-desc">4K editing, 3D rendering, and heavy multitasking.</p>
            <p className="build-card-specs">RTX 4070 • Ryzen 7 7700X • 32GB DDR5</p>
            <div className="build-card-bottom">
              <span className="build-card-price">
                <span className="build-card-price-currency">PKR</span>
                <span className="build-card-price-amount">420,000</span>
              </span>
              <button
                type="button"
                className="build-card-configure"
                onClick={() => handleQuickBuild('content')}
              >
                Configure
              </button>
            </div>
          </TiltCard>

          <TiltCard as={motion.div} className="build-card-popular build-card-ai" variants={cardVariants}>
            <div className="build-card-accent" />
            <p className="build-card-category">AI Workstation</p>
            <h3 className="build-card-title">AI Powerhouse</h3>
            <p className="build-card-desc">Run AI models, ML workloads, and intensive compute.</p>
            <p className="build-card-specs">RTX 4090 • Ryzen 9 7950X3D • 64GB DDR5</p>
            <div className="build-card-bottom">
              <span className="build-card-price">
                <span className="build-card-price-currency">PKR</span>
                <span className="build-card-price-amount">1,130,000</span>
              </span>
              <button
                type="button"
                className="build-card-configure"
                onClick={() => handleQuickBuild('ai')}
              >
                Configure
              </button>
            </div>
          </TiltCard>
        </motion.div>
      </div>
    </motion.section>
  );
}
