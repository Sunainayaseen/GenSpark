import { useEffect, useRef, useState } from 'react';
import HeaderSearch from '../components/HeaderSearch';
import { initScrollAnimations } from '../utils/scrollAnimations';
import './About.css';

const IconUsers = () => (
  <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="about-svg-icon"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" /></svg>
);
const IconMonitor = () => (
  <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="about-svg-icon"><rect x="2" y="3" width="20" height="14" rx="2" /><line x1="8" y1="21" x2="16" y2="21" /><line x1="12" y1="17" x2="12" y2="21" /></svg>
);
const IconStar = () => (
  <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="about-svg-icon"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" /></svg>
);
const IconCalendar = () => (
  <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="about-svg-icon"><rect x="3" y="4" width="18" height="18" rx="2" /><line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" /><line x1="3" y1="10" x2="21" y2="10" /></svg>
);
const IconTarget = () => (
  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="about-svg-icon"><circle cx="12" cy="12" r="10" /><circle cx="12" cy="12" r="6" /><circle cx="12" cy="12" r="2" /></svg>
);
const IconCheckCircle = () => (
  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="about-svg-icon"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" /></svg>
);
const IconZap = () => (
  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="about-svg-icon"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" /></svg>
);
const IconShield = () => (
  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="about-svg-icon"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /></svg>
);
const IconEye = () => (
  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="about-svg-icon"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" /></svg>
);
const IconCode = () => (
  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="about-svg-icon"><polyline points="16 18 22 12 16 6" /><polyline points="8 6 2 12 8 18" /></svg>
);
const IconHeadphones = () => (
  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="about-svg-icon"><path d="M3 18v-6a9 9 0 0 1 18 0v6" /><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z" /></svg>
);
const IconWrench = () => (
  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="about-svg-icon"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" /></svg>
);
const IconCpu = () => (
  <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="about-svg-icon"><rect x="4" y="4" width="16" height="16" rx="2" /><rect x="9" y="9" width="6" height="6" /><line x1="9" y1="1" x2="9" y2="4" /><line x1="15" y1="1" x2="15" y2="4" /><line x1="9" y1="20" x2="9" y2="23" /><line x1="15" y1="20" x2="15" y2="23" /><line x1="20" y1="9" x2="23" y2="9" /><line x1="20" y1="14" x2="23" y2="14" /><line x1="1" y1="9" x2="4" y2="9" /><line x1="1" y1="14" x2="4" y2="14" /></svg>
);

const About = () => {
  const statsRef = useRef(null);
  const [statsAnimated, setStatsAnimated] = useState(false);
  const [clients, setClients] = useState(0);
  const [projects, setProjects] = useState(0);
  const [satisfaction, setSatisfaction] = useState(0);
  const [experience, setExperience] = useState(0);

  const animateCounter = (start, end, duration, setter) => {
    const startTime = performance.now();
    const animate = (currentTime) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const easeOutQuart = 1 - Math.pow(1 - progress, 4);
      const current = Math.floor(start + (end - start) * easeOutQuart);
      setter(current);
      if (progress < 1) {
        requestAnimationFrame(animate);
      } else {
        setter(end);
      }
    };
    requestAnimationFrame(animate);
  };

  useEffect(() => {
    const cleanup = initScrollAnimations();

    const statsObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting && !statsAnimated) {
          setStatsAnimated(true);
          animateCounter(0, 1000, 2000, setClients);
          animateCounter(0, 500, 2000, setProjects);
          animateCounter(0, 98, 2000, setSatisfaction);
          animateCounter(0, 5, 2000, setExperience);
          statsObserver.unobserve(entry.target);
        }
      });
    }, { threshold: 0.5 });

    if (statsRef.current) {
      statsObserver.observe(statsRef.current);
    }

    return () => {
      if (cleanup) cleanup();
      if (statsRef.current) {
        statsObserver.unobserve(statsRef.current);
      }
    };
  }, [statsAnimated]);

  const values = [
    {
      icon: IconTarget,
      title: 'Innovation',
      description: 'We use AI to match components by compatibility, budget, and use case—so you get the right build without guesswork. Our system suggests CPU, GPU, RAM, and PSU combinations validated for your workload.'
    },
    {
      icon: IconCheckCircle,
      title: 'Trust',
      description: 'Every vendor is verified by our admin team. Builds are checked for correctness before delivery, and we support transparent pricing and secure payment options across major cities in Pakistan.'
    },
    {
      icon: IconZap,
      title: 'Speed',
      description: 'From recommendation to delivery: get build suggestions in seconds, choose your vendor, and track assembly with real-time updates. Most builds are ready within 3–7 days depending on location.'
    },
    {
      icon: IconShield,
      title: 'Quality',
      description: 'We recommend parts from trusted brands and partner with assemblers who follow best practices. Each build is tested before handover so you get a reliable, warranty-backed PC.'
    }
  ];

  const team = [
    {
      icon: IconCode,
      name: 'Product & AI',
      role: 'Recommendation engine & platform',
      description: 'Develops the AI that powers build suggestions, compatibility checks, and the configurator so every recommendation is technically sound and within your budget.'
    },
    {
      icon: IconHeadphones,
      name: 'Customer Success',
      role: 'Support & onboarding',
      description: 'Helps you from first visit to delivery: answers questions, explains options, and coordinates with vendors so your build and assembly go smoothly.'
    },
    {
      icon: IconWrench,
      name: 'Vendor network',
      role: 'Assembly & logistics',
      description: 'Verified assemblers across Karachi, Lahore, Islamabad, and other cities. They handle assembly, basic testing, and safe packaging for pickup or delivery.'
    }
  ];

  return (
    <div className="about-page">
      {/* Hero Section */}
      <section className="about-hero">
        <div className="container">
          <div className="about-hero-content">
            <div className="about-badge" data-scroll="fade-up" data-delay="100">
              <span>About GenSpark Builds</span>
            </div>
            <h1 className="about-title" data-scroll="fade-up" data-delay="200">
              Building Dreams, One PC at a Time
            </h1>
            <p className="about-subtitle" data-scroll="fade-up" data-delay="300">
              AI-powered build recommendations, verified assembly partners across Pakistan, 
              and admin-validated deliveries—so you get a compatible, reliable PC without the guesswork.
            </p>
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="about-stats" ref={statsRef}>
        <div className="container">
          <div className="stats-grid">
            <div className="stat-card" data-scroll="scale" data-delay="100">
              <div className="stat-icon"><IconUsers /></div>
              <div className="stat-number">{clients}+</div>
              <div className="stat-label">Happy Clients</div>
            </div>
            <div className="stat-card" data-scroll="scale" data-delay="200">
              <div className="stat-icon"><IconMonitor /></div>
              <div className="stat-number">{projects}+</div>
              <div className="stat-label">PCs Built</div>
            </div>
            <div className="stat-card" data-scroll="scale" data-delay="300">
              <div className="stat-icon"><IconStar /></div>
              <div className="stat-number">{satisfaction}%</div>
              <div className="stat-label">Satisfaction Rate</div>
            </div>
            <div className="stat-card" data-scroll="scale" data-delay="400">
              <div className="stat-icon"><IconCalendar /></div>
              <div className="stat-number">{experience}+</div>
              <div className="stat-label">Years Experience</div>
            </div>
          </div>
        </div>
      </section>

      {/* Story Section */}
      <section className="about-story">
        <div className="container">
          <div className="story-content">
            <div className="story-text" data-scroll="fade-up">
              <h2>Our Story</h2>
              <p>
                GenSpark Builds started with a clear goal: make custom PC building straightforward 
                and trustworthy for everyone in Pakistan. Picking compatible parts, finding reliable 
                assemblers, and staying within budget were common pain points—so we built a platform 
                that addresses all three.
              </p>
              <p>
                Our AI recommends builds based on your use case (gaming, office, content creation), 
                budget, and city. It checks socket compatibility, PSU wattage, and form factor so 
                every suggestion is technically valid. We then connect you with verified assembly 
                partners in Karachi, Lahore, Islamabad, and other cities. Each build is reviewed 
                by our team before it reaches you, with options for pickup or delivery.
              </p>
              <p>
                Today we serve thousands of customers—gamers, professionals, and creators—with 
                a single flow: get recommendations, customize if needed, choose a vendor, and 
                receive a tested, ready-to-use PC with local support and warranty where applicable.
              </p>
            </div>
            <div className="story-image" data-scroll="zoom" data-delay="200">
              <div className="story-visual">
                <div className="visual-circle circle-1"></div>
                <div className="visual-circle circle-2"></div>
                <div className="visual-circle circle-3"></div>
                <div className="visual-center">
                  <span className="visual-icon"><IconCpu /></span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Mission & Vision */}
      <section className="about-mission">
        <div className="container">
          <div className="mission-grid">
            <div className="mission-card" data-scroll="slide-left">
              <div className="mission-icon"><IconTarget /></div>
              <h3>Our Mission</h3>
              <p>
                To make custom PC building accessible across Pakistan: AI-driven recommendations 
                for compatibility and budget, verified vendors for assembly, and admin-validated 
                builds so everyone—gamers, creators, and professionals—can get a reliable machine 
                without the guesswork.
              </p>
            </div>
            <div className="mission-card" data-scroll="slide-right">
              <div className="mission-icon"><IconEye /></div>
              <h3>Our Vision</h3>
              <p>
                To be the go-to platform for PC building in Pakistan: trusted recommendations, 
                nationwide vendor coverage, and a seamless path from configurator to delivery. 
                We aim to set the standard for transparency, quality, and customer support in 
                the local custom PC space.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Values Section */}
      <section className="about-values">
        <div className="container">
          <div className="section-header">
            <h2 className="section-title" data-scroll="fade-up">Our Core Values</h2>
            <p className="section-subtitle" data-scroll="fade-up" data-delay="100">
              The principles that guide everything we do
            </p>
          </div>
          <div className="values-grid scroll-stagger">
            {values.map((value, index) => {
              const IconComponent = value.icon;
              return (
                <div key={index} className="value-card" data-scroll="fade-up">
                  <div className="value-icon">{IconComponent ? <IconComponent /> : null}</div>
                  <h4>{value.title}</h4>
                  <p>{value.description}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Team Section */}
      <section className="about-team">
        <div className="container">
          <div className="section-header">
            <h2 className="section-title" data-scroll="fade-up">Our Team</h2>
            <p className="section-subtitle" data-scroll="fade-up" data-delay="100">
              The people behind GenSpark Builds
            </p>
          </div>
          <div className="team-grid scroll-stagger">
            {team.map((member, index) => {
              const IconComponent = member.icon;
              return (
                <div key={index} className="team-card" data-scroll="scale">
                  <div className="team-avatar">
                    <span className="avatar-icon">{IconComponent ? <IconComponent /> : null}</span>
                  </div>
                  <h4>{member.name}</h4>
                  <p className="team-role">{member.role}</p>
                  <p className="team-description">{member.description}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="about-cta">
        <div className="container">
          <div className="cta-content" data-scroll="fade-up">
            <h2>Ready to Build Your Perfect PC?</h2>
            <p>Get AI-backed recommendations, choose your vendor, and receive a tested build. Join thousands who’ve built with GenSpark across Pakistan.</p>
            <div className="cta-buttons">
              <a href="/chatbot" className="btn btn-primary btn-lg">
                Start Building
              </a>
              <div className="about-cta-search" aria-label="Search components (same as site header)">
                <HeaderSearch />
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};

export default About;

