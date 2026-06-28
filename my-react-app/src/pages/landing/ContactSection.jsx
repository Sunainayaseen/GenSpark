import { useState } from 'react';
import { motion } from 'framer-motion';
import { useConfirm } from '../../components/ConfirmProvider';
import { dashboardPost } from '../../api/dashboardApi';
import { sectionVariants, headerVariants, viewportOnce } from './motionVariants';

const initialFormData = { name: '', email: '', phone: '', subject: '', message: '' };

export default function ContactSection() {
  const { notify } = useConfirm();
  const [formData, setFormData] = useState(initialFormData);
  const [submitting, setSubmitting] = useState(false);

  const handleFormSubmit = async (e) => {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    try {
      await dashboardPost('/contact', formData);
      notify('Thank you for contacting us! We will get back to you soon.', { type: 'success' });
      setFormData(initialFormData);
    } catch (err) {
      notify(err?.data?.error || err?.message || 'Could not send your message. Please try again.', { type: 'error' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleFormChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  return (
    <motion.section
      className="contact-section"
      initial="hidden"
      whileInView="visible"
      viewport={viewportOnce}
      variants={sectionVariants}
    >
      <div className="container">
        <motion.h2 className="section-title" variants={headerVariants}>Get in Touch</motion.h2>
        <motion.p className="section-subtitle" variants={headerVariants}>
          Have questions? We'd love to hear from you. Get in touch with us today.
        </motion.p>
        <motion.div className="contact-content-wrapper" variants={headerVariants}>
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
          <div className="contact-form-wrapper">
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

              <button type="submit" className="btn btn-primary btn-lg submit-btn cta-glow" disabled={submitting}>
                {submitting ? 'Sending…' : 'Send Message'}
              </button>
            </form>
          </div>
        </div>
        </motion.div>
      </div>
    </motion.section>
  );
}
