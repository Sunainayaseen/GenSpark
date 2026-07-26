import { motion } from 'framer-motion';
import TiltCard from '../../components/TiltCard';
import { sectionVariants, headerVariants, gridVariants, cardVariants, viewportOnce } from './motionVariants';

export default function FeaturesSection() {
  return (
    <motion.section
      className="features"
      initial="hidden"
      whileInView="visible"
      viewport={viewportOnce}
      variants={sectionVariants}
    >
      <div className="features-bg-effects" aria-hidden />
      <div className="container">
        <motion.div className="features-header" variants={headerVariants}>
          <h2 className="section-title">Why Choose GenSpark?</h2>
          <p className="features-subtitle">
            Built for builders. Trust, transparency, and local support at every step.
          </p>
        </motion.div>
        <motion.div className="features-grid" variants={gridVariants}>
          <TiltCard as={motion.div} className="feature-card" variants={cardVariants}>
            <div className="feature-card-icon-wrap">
              <svg className="feature-card-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="4" y="4" width="16" height="16" rx="2" ry="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/><line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/><line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/></svg>
            </div>
            <h4>AI-Powered Matching</h4>
            <p>Smart compatibility checking ensures all parts work together perfectly.</p>
          </TiltCard>
          <TiltCard as={motion.div} className="feature-card" variants={cardVariants}>
            <div className="feature-card-icon-wrap">
              <svg className="feature-card-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
            </div>
            <h4>Local Vendors</h4>
            <p>City-based assembly partners for faster delivery and local support.</p>
          </TiltCard>
          <TiltCard as={motion.div} className="feature-card" variants={cardVariants}>
            <div className="feature-card-icon-wrap">
              <svg className="feature-card-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13 2v2"/><path d="M13 20v2"/></svg>
            </div>
            <h4>Real-time Updates</h4>
            <p>Track every step of your build journey with live order status and instant in-app notifications.</p>
          </TiltCard>
          <TiltCard as={motion.div} className="feature-card" variants={cardVariants}>
            <div className="feature-card-icon-wrap">
              <svg className="feature-card-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
            </div>
            <h4>Verified Assembly</h4>
            <p>Admin-validated builds with photo proof before delivery.</p>
          </TiltCard>
        </motion.div>
      </div>
    </motion.section>
  );
}
