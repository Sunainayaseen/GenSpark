import { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import TiltCard from '../../components/TiltCard';
import { sectionVariants, headerVariants, gridVariants, cardVariants, viewportOnce } from './motionVariants';

const STAT_TARGETS = [
  { value: 4.9, suffix: '', decimals: 1 },
  { value: 500, suffix: '+', decimals: 0 },
  { value: 98, suffix: '%', decimals: 0 },
];

export default function ReviewsSection() {
  const reviewsStatsRef = useRef(null);
  const [statValues, setStatValues] = useState([0, 0, 0]);

  // Count-up stats every time the review section scrolls into view (up or down).
  useEffect(() => {
    const el = reviewsStatsRef.current;
    if (!el) return;
    const duration = 1200;
    let rafId = null;

    const runCountUp = () => {
      if (rafId) cancelAnimationFrame(rafId);
      const start = performance.now();
      const tick = (now) => {
        const elapsed = now - start;
        const t = Math.min(elapsed / duration, 1);
        const easeOut = 1 - Math.pow(1 - t, 2);
        setStatValues(STAT_TARGETS.map((target) => {
          const v = target.value * easeOut;
          return target.decimals === 1 ? Math.round(v * 10) / 10 : Math.round(v);
        }));
        if (t < 1) rafId = requestAnimationFrame(tick);
      };
      rafId = requestAnimationFrame(tick);
    };

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          // Re-run the count-up each time it enters the viewport.
          requestAnimationFrame(() => runCountUp());
        } else {
          // Reset to zero when it leaves so the next scroll-in re-animates.
          if (rafId) cancelAnimationFrame(rafId);
          setStatValues([0, 0, 0]);
        }
      },
      { threshold: 0.2, rootMargin: '0px 0px 40px 0px' }
    );
    observer.observe(el);
    return () => {
      if (rafId) cancelAnimationFrame(rafId);
      observer.disconnect();
    };
  }, []);

  return (
    <motion.section
      className="reviews-section"
      initial="hidden"
      whileInView="visible"
      viewport={viewportOnce}
      variants={sectionVariants}
    >
      <div className="container">
        <motion.h2 className="section-title" variants={headerVariants}>What Our Customers Say</motion.h2>
        <motion.p className="section-subtitle" variants={headerVariants}>
          Trusted by hundreds of builders across Pakistan. Real builds, real feedback.
        </motion.p>
        <motion.div className="reviews-stats" ref={reviewsStatsRef} variants={headerVariants}>
          <div className="review-stat">
            <span className="stat-value">{statValues[0]}{STAT_TARGETS[0].suffix}</span>
            <span className="stat-label">Average Rating</span>
          </div>
          <div className="review-stat">
            <span className="stat-value">{statValues[1]}{STAT_TARGETS[1].suffix}</span>
            <span className="stat-label">Happy Builders</span>
          </div>
          <div className="review-stat">
            <span className="stat-value">{statValues[2]}{STAT_TARGETS[2].suffix}</span>
            <span className="stat-label">Would Recommend</span>
          </div>
        </motion.div>
        <motion.div className="reviews-grid" variants={gridVariants}>
          <TiltCard as={motion.div} className="review-card" variants={cardVariants}>
            <div className="review-rating">
              <span className="star">★</span><span className="star">★</span><span className="star">★</span><span className="star">★</span><span className="star">★</span>
            </div>
            <blockquote className="review-quote">
              AI suggested the perfect build for my budget. Got my gaming rig assembled in Karachi within a week. Absolutely worth it!
            </blockquote>
            <div className="review-author">
              <div className="review-avatar">A</div>
              <div className="review-meta">
                <strong>Ahmed K.</strong>
                <span>Karachi · Gaming Build</span>
              </div>
              <span className="review-verified" title="Verified purchase">✓ Verified</span>
            </div>
          </TiltCard>
          <TiltCard as={motion.div} className="review-card" variants={cardVariants}>
            <div className="review-rating">
              <span className="star">★</span><span className="star">★</span><span className="star">★</span><span className="star">★</span><span className="star">★</span>
            </div>
            <blockquote className="review-quote">
              Local vendor was professional and the compatibility check saved me from wrong parts. GenSpark made my first PC build stress-free.
            </blockquote>
            <div className="review-author">
              <div className="review-avatar">S</div>
              <div className="review-meta">
                <strong>Sara M.</strong>
                <span>Lahore · Content Creator Build</span>
              </div>
              <span className="review-verified" title="Verified purchase">✓ Verified</span>
            </div>
          </TiltCard>
          <TiltCard as={motion.div} className="review-card" variants={cardVariants}>
            <div className="review-rating">
              <span className="star">★</span><span className="star">★</span><span className="star">★</span><span className="star">★</span><span className="star">★</span>
            </div>
            <blockquote className="review-quote">
              Ordered an office PC for our startup. On-time delivery, clean assembly, and live order updates at every step. Highly recommend.
            </blockquote>
            <div className="review-author">
              <div className="review-avatar">R</div>
              <div className="review-meta">
                <strong>Rizwan H.</strong>
                <span>Islamabad · Office Build</span>
              </div>
              <span className="review-verified" title="Verified purchase">✓ Verified</span>
            </div>
          </TiltCard>
          <TiltCard as={motion.div} className="review-card review-card-featured" variants={cardVariants}>
            <div className="review-badge">Featured</div>
            <div className="review-rating">
              <span className="star">★</span><span className="star">★</span><span className="star">★</span><span className="star">★</span><span className="star">★</span>
            </div>
            <blockquote className="review-quote">
              Best platform for custom PCs in Pakistan. The AI configurator understood exactly what I needed for streaming and editing. Vendor assembly was top-notch.
            </blockquote>
            <div className="review-author">
              <div className="review-avatar">F</div>
              <div className="review-meta">
                <strong>Fatima Z.</strong>
                <span>Rawalpindi · Performance Build</span>
              </div>
              <span className="review-verified" title="Verified purchase">✓ Verified</span>
            </div>
          </TiltCard>
        </motion.div>
      </div>
    </motion.section>
  );
}
