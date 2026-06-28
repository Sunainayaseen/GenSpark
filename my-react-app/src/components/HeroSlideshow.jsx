import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import './HeroSlideshow.css';

// Two-level cascade: the panel staggers copy-block → visual-block, then the copy
// block staggers its own lines. Mirrors the timing the old per-element CSS
// `heroFadeUp` animations used, now driven by Framer Motion (respects
// prefers-reduced-motion globally via the <MotionConfig reducedMotion="user"> in main.jsx).
const panelVariants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.16 } },
};

const copyVariants = {
  hidden: { opacity: 0, y: 16 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, ease: [0.4, 0, 0.2, 1], staggerChildren: 0.09, delayChildren: 0.04 },
  },
};

const visualVariants = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.55, ease: [0.4, 0, 0.2, 1] } },
};

const lineVariants = {
  hidden: { opacity: 0, y: 14 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.4, 0, 0.2, 1] } },
};

export default function HeroSlideshow() {
  const navigate = useNavigate();

  const handleCta = (route) => {
    if (route) navigate(route);
  };

  return (
    <section className="hero-video-section" aria-label="GenSpark Builds hero banner">
      <div className="hero-solo-bg" aria-hidden="true" />

      <div className="hero-video-content">
        <motion.div className="hero-panel" initial="hidden" animate="visible" variants={panelVariants}>
          <motion.div className="hero-panel-copy hero-copy-surface" variants={copyVariants}>
            <motion.div className="hero-brand-row" variants={lineVariants}>
              <ul className="hero-brand-trust">
                <li>Custom PCs</li>
                <li>Genuine parts</li>
                <li>PKR pricing</li>
              </ul>
            </motion.div>

            <motion.h1 className="hero-headline" variants={lineVariants}>
              <span className="hero-headline-line hero-headline-line--primary">Build Your Perfect PC —</span>
              <span className="hero-headline-line hero-headline-line--accent">
                Powered by AI Compatibility Checks
              </span>
            </motion.h1>

            <motion.p className="hero-lede" variants={lineVariants}>
              Compare builds in PKR, run compatibility checks, and fulfil through approved vendors—without
              spreadsheet guesswork.
            </motion.p>

            <motion.ul className="hero-value-points" variants={lineVariants} aria-label="What you get">
              <li>
                <span className="hero-value-icon" aria-hidden="true">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
                  </svg>
                </span>
                <span>Smarter part suggestions</span>
              </li>
              <li>
                <span className="hero-value-icon" aria-hidden="true">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                  </svg>
                </span>
                <span>Compatibility-first checks</span>
              </li>
              <li>
                <span className="hero-value-icon" aria-hidden="true">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
                    <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
                    <line x1="12" y1="22.08" x2="12" y2="12" />
                  </svg>
                </span>
                <span>Trusted vendor fulfilment</span>
              </li>
            </motion.ul>

            <motion.div className="hero-banner-actions" variants={lineVariants}>
              <button
                type="button"
                className="hero-slide-cta hero-slide-cta--primary cta-shimmer"
                onClick={() => handleCta('/chatbot')}
              >
                <span>Start with AI</span>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              </button>
              <button
                type="button"
                className="hero-slide-cta hero-slide-cta--secondary"
                onClick={() => handleCta('/components')}
              >
                Browse components
              </button>
            </motion.div>
          </motion.div>

          <motion.aside className="hero-panel-visual" variants={visualVariants}>
            <figure className="hero-visual-figure">
              <div className="hero-visual-frame">
                <img
                  className="hero-visual-img"
                  src="/hero-banner-pc.png?v=4dc9a0bc"
                  alt="Custom gaming PC, monitor, and PC components"
                  width={1200}
                  height={600}
                  decoding="async"
                  fetchPriority="high"
                />
              </div>
            </figure>
          </motion.aside>
        </motion.div>
      </div>
    </section>
  );
}
