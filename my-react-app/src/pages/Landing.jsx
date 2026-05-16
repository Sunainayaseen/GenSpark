import { useNavigate, Link } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { useEffect, useRef, useState } from 'react';
import { PREBUILT_SHOWCASE, prebuiltToConfiguratorBuild } from '../data/prebuiltShowcase';
import { initScrollAnimations } from '../utils/scrollAnimations';
import HeroSlideshow from '../components/HeroSlideshow';
import './Landing.css';

const Landing = () => {
  const navigate = useNavigate();
  const { updateRequirements, setSelectedBuild } = useApp();

  const buildCardsRef = useRef([]);
  const featureCardsRef = useRef([]);
  const reviewsStatsRef = useRef(null);
  const [statValues, setStatValues] = useState([0, 0, 0]);
  const statTargets = [
    { value: 4.9, suffix: '', decimals: 1 },
    { value: 500, suffix: '+', decimals: 0 },
    { value: 98, suffix: '%', decimals: 0 },
  ];
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    subject: '',
    message: '',
  });

  useEffect(() => {
    const cleanup = initScrollAnimations();
    return () => { if (cleanup) cleanup(); };
  }, []);

  // Count-up stats when review section is in view (on scroll down or scroll up)
  useEffect(() => {
    const el = reviewsStatsRef.current;
    if (!el) return;
    const duration = 1200;
    const startTimes = [null, null, null];

    const runCountUp = () => {
      const start = performance.now();
      const tick = (now) => {
        const elapsed = now - start;
        const t = Math.min(elapsed / duration, 1);
        const easeOut = 1 - Math.pow(1 - t, 2);
        setStatValues(statTargets.map((target, i) => {
          const v = target.value * easeOut;
          return target.decimals === 1 ? Math.round(v * 10) / 10 : Math.round(v);
        }));
        if (t < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    };

    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries[0].isIntersecting) return;
        setStatValues([0, 0, 0]);
        requestAnimationFrame(() => runCountUp());
      },
      { threshold: 0.2, rootMargin: '0px 0px 40px 0px' }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const handleQuickBuild = (type) => {
    const requirements = {
      'budget': { purpose: 'Office', budget: '50000', preferences: 'Budget-focused' },
      'gaming': { purpose: 'Gaming', budget: '100000', preferences: 'Performance-focused' },
      'content': { purpose: 'Content Creation', budget: '150000', preferences: 'Professional-grade' },
      'ai': { purpose: 'Content Creation', budget: '200000', preferences: 'AI Workstation' },
    };

    const prebuilt = PREBUILT_SHOWCASE.find((item) => item.quickKey === type);
    updateRequirements(requirements[type] || requirements.gaming);
    if (!prebuilt) {
      navigate('/builds');
      return;
    }

    setSelectedBuild(prebuiltToConfiguratorBuild(prebuilt));
    navigate('/vendor-assignment');
  };

  const handleFormSubmit = (e) => {
    e.preventDefault();
    // Handle form submission
    console.log('Form submitted:', formData);
    alert('Thank you for contacting us! We will get back to you soon.');
    setFormData({
      name: '',
      email: '',
      phone: '',
      subject: '',
      message: '',
    });
  };

  const handleFormChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  return (
    <div className="landing">
      <HeroSlideshow />

      <section className="quick-builds" data-scroll="fade" data-delay="0" data-duration="500">
        <div className="container">
          <div className="popular-builds-header" data-scroll="fade-up" data-delay="100">
            <div className="popular-builds-heading">
              <p className="popular-builds-tag">Curated for You</p>
              <h2 className="popular-builds-title">
                <span className="title-part">Top Picks</span>{' '}
                <span className="title-accent">for Every Need</span>
              </h2>
              <p className="popular-builds-subtitle">Handpicked configurations for gaming, work, and creativity—ready to customize.</p>
            </div>
            <Link to="/builds" className="view-all-builds-btn">
              View predefined PCs
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
            </Link>
          </div>
          <div className="build-cards-popular scroll-stagger">
            <div className="build-card-popular build-card-gaming" ref={(el) => buildCardsRef.current[0] = el}>
              <div className="build-card-accent" />
              <p className="build-card-category">Gaming</p>
              <h3 className="build-card-title">Gaming Beast</h3>
              <p className="build-card-desc">Dominate every game at ultra settings with ray tracing.</p>
              <p className="build-card-specs">RTX 5070 Ti • Ryzen 7 9800X3D • 32GB DDR5</p>
              <div className="build-card-bottom">
                <span className="build-card-price">PKR 1,89,000</span>
                <button
                  type="button"
                  className="build-card-configure"
                  onClick={() => handleQuickBuild('gaming')}
                >
                  Configure
                </button>
              </div>
                </div>

            <div className="build-card-popular build-card-office" ref={(el) => buildCardsRef.current[1] = el}>
              <div className="build-card-accent" />
              <p className="build-card-category">Office</p>
              <h3 className="build-card-title">Pro Workstation</h3>
              <p className="build-card-desc">Reliable performance for work, browsing, and everyday tasks.</p>
              <p className="build-card-specs">Ryzen 5 5600G • 16GB DDR4 • 512GB SSD</p>
              <div className="build-card-bottom">
                <span className="build-card-price">PKR 55,000</span>
                <button
                  type="button"
                  className="build-card-configure"
                  onClick={() => handleQuickBuild('budget')}
                >
                  Configure
                </button>
              </div>
            </div>

            <div className="build-card-popular build-card-editing" ref={(el) => buildCardsRef.current[2] = el}>
              <div className="build-card-accent" />
              <p className="build-card-category">Editing</p>
              <h3 className="build-card-title">Creator Studio</h3>
              <p className="build-card-desc">4K editing, 3D rendering, and heavy multitasking.</p>
              <p className="build-card-specs">RTX 4070 • Ryzen 7 7700X • 32GB DDR5</p>
              <div className="build-card-bottom">
                <span className="build-card-price">PKR 1,45,000</span>
                <button
                  type="button"
                  className="build-card-configure"
                  onClick={() => handleQuickBuild('content')}
                >
                  Configure
                </button>
              </div>
            </div>

            <div className="build-card-popular build-card-ai" ref={(el) => buildCardsRef.current[3] = el}>
              <div className="build-card-accent" />
              <p className="build-card-category">AI Workstation</p>
              <h3 className="build-card-title">AI Powerhouse</h3>
              <p className="build-card-desc">Run AI models, ML workloads, and intensive compute.</p>
              <p className="build-card-specs">RTX 4090 • Ryzen 9 7950X3D • 64GB DDR5</p>
              <div className="build-card-bottom">
                <span className="build-card-price">PKR 4,20,000</span>
                <button
                  type="button"
                  className="build-card-configure"
                  onClick={() => handleQuickBuild('ai')}
                >
                  Configure
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="features">
        <div className="features-bg-effects" aria-hidden />
        <div className="container">
          <div className="features-header">
            <h2 className="section-title">Why Choose GenSpark?</h2>
            <p className="features-subtitle">
              Built for builders. Trust, transparency, and local support at every step.
            </p>
          </div>
          <div className="features-grid scroll-stagger" data-once="true">
            <div className="feature-card" ref={(el) => featureCardsRef.current[0] = el}>
              <div className="feature-card-icon-wrap">
                <svg className="feature-card-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="4" y="4" width="16" height="16" rx="2" ry="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/><line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/><line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/></svg>
              </div>
              <h4>AI-Powered Matching</h4>
              <p>Smart compatibility checking ensures all parts work together perfectly.</p>
            </div>
            <div className="feature-card" ref={(el) => featureCardsRef.current[1] = el}>
              <div className="feature-card-icon-wrap">
                <svg className="feature-card-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
              </div>
              <h4>Local Vendors</h4>
              <p>City-based assembly partners for faster delivery and local support.</p>
            </div>
            <div className="feature-card" ref={(el) => featureCardsRef.current[2] = el}>
              <div className="feature-card-icon-wrap">
                <svg className="feature-card-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13 2v2"/><path d="M13 20v2"/></svg>
              </div>
              <h4>Real-time Updates</h4>
              <p>Get WhatsApp notifications at every step of your build journey.</p>
            </div>
            <div className="feature-card" ref={(el) => featureCardsRef.current[3] = el}>
              <div className="feature-card-icon-wrap">
                <svg className="feature-card-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
              </div>
              <h4>Verified Assembly</h4>
              <p>Admin-validated builds with photo proof before delivery.</p>
            </div>
          </div>
        </div>
      </section>

      <section className="reviews-section" data-scroll="fade" data-delay="0" data-duration="500">
        <div className="container">
          <h2 className="section-title" data-scroll="fade-up" data-delay="100">What Our Customers Say</h2>
          <p className="section-subtitle" data-scroll="fade-up" data-delay="200">
            Trusted by hundreds of builders across Pakistan. Real builds, real feedback.
          </p>
          <div className="reviews-stats" ref={reviewsStatsRef} data-scroll="fade-up" data-delay="250">
            <div className="review-stat">
              <span className="stat-value">{statValues[0]}{statTargets[0].suffix}</span>
              <span className="stat-label">Average Rating</span>
            </div>
            <div className="review-stat">
              <span className="stat-value">{statValues[1]}{statTargets[1].suffix}</span>
              <span className="stat-label">Happy Builders</span>
            </div>
            <div className="review-stat">
              <span className="stat-value">{statValues[2]}{statTargets[2].suffix}</span>
              <span className="stat-label">Would Recommend</span>
            </div>
          </div>
          <div className="reviews-grid scroll-stagger">
            <div className="review-card">
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
            </div>
            <div className="review-card">
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
            </div>
            <div className="review-card">
              <div className="review-rating">
                <span className="star">★</span><span className="star">★</span><span className="star">★</span><span className="star">★</span><span className="star">★</span>
              </div>
              <blockquote className="review-quote">
                Ordered an office PC for our startup. On-time delivery, clean assembly, and WhatsApp updates at every step. Highly recommend.
              </blockquote>
              <div className="review-author">
                <div className="review-avatar">R</div>
                <div className="review-meta">
                  <strong>Rizwan H.</strong>
                  <span>Islamabad · Office Build</span>
                </div>
                <span className="review-verified" title="Verified purchase">✓ Verified</span>
              </div>
            </div>
            <div className="review-card review-card-featured">
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
            </div>
          </div>
        </div>
      </section>

      <section className="contact-section" data-scroll="fade" data-delay="0" data-duration="500">
        <div className="container">
          <h2 className="section-title" data-scroll="fade-up" data-delay="100">Get in Touch</h2>
          <p className="section-subtitle" data-scroll="fade-up" data-delay="200">
            Have questions? We'd love to hear from you. Get in touch with us today.
          </p>
          <div className="contact-content-wrapper" data-scroll="fade-up" data-delay="300">
            <div className="contact-cards">
              <div className="contact-card">
                <div className="contact-card-icon" aria-hidden>
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
                </div>
                <h3>Email</h3>
                <a href="mailto:support@gensparkbuilds.com" className="contact-link">
                  support@gensparkbuilds.com
                </a>
              </div>
              <div className="contact-card">
                <div className="contact-card-icon" aria-hidden>
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/></svg>
                </div>
                <h3>Phone</h3>
                <a href="tel:+923201436593" className="contact-link">
                  +92 320 1436593
                </a>
              </div>
              <div className="contact-card">
                <div className="contact-card-icon" aria-hidden>
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
                </div>
                <h3>Location</h3>
                <p className="contact-text">Lahore, Pakistan</p>
              </div>
            </div>
            <div className="contact-form-wrapper" data-scroll="fade-up" data-delay="400">
            <div className="contact-form-container">
              <h3 className="form-title">Send us a Message</h3>
              <form className="landing-contact-form" onSubmit={handleFormSubmit}>
                <div className="form-row">
                  <div className="form-group">
                    <label htmlFor="landing-name">Full Name *</label>
                    <input
                      type="text"
                      id="landing-name"
                      name="name"
                      value={formData.name}
                      onChange={handleFormChange}
                      required
                      placeholder="Enter your name"
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="landing-email">Email *</label>
                    <input
                      type="email"
                      id="landing-email"
                      name="email"
                      value={formData.email}
                      onChange={handleFormChange}
                      required
                      placeholder="your.email@example.com"
                    />
                  </div>
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label htmlFor="landing-phone">Phone Number</label>
                    <input
                      type="tel"
                      id="landing-phone"
                      name="phone"
                      value={formData.phone}
                      onChange={handleFormChange}
                      placeholder="+92 320 1436593"
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="landing-subject">Subject *</label>
                    <select
                      id="landing-subject"
                      name="subject"
                      value={formData.subject}
                      onChange={handleFormChange}
                      required
                    >
                      <option value="">Select a subject</option>
                      <option value="build-inquiry">Build Inquiry</option>
                      <option value="support">Technical Support</option>
                      <option value="partnership">Partnership</option>
                      <option value="vendor">Vendor Application</option>
                      <option value="other">Other</option>
                    </select>
                  </div>
                </div>

                <div className="form-group">
                  <label htmlFor="landing-message">Message *</label>
                  <textarea
                    id="landing-message"
                    name="message"
                    value={formData.message}
                    onChange={handleFormChange}
                    required
                    rows="6"
                    placeholder="Tell us how we can help you..."
                  ></textarea>
                </div>

                <button type="submit" className="btn btn-primary btn-lg submit-btn">
                  Send Message
                </button>
              </form>
            </div>
          </div>
          </div>
        </div>
      </section>
    </div>
  );
};

export default Landing;

