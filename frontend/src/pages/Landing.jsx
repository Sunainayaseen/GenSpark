import HeroSlideshow from '../components/HeroSlideshow';
import QuickBuilds from './landing/QuickBuilds';
import FeaturesSection from './landing/FeaturesSection';
import ReviewsSection from './landing/ReviewsSection';
import ContactSection from './landing/ContactSection';
import './Landing.css';

const Landing = () => {
  return (
    <div className="landing">
      <HeroSlideshow />
      <QuickBuilds />
      <FeaturesSection />
      <ReviewsSection />
      <ContactSection />
    </div>
  );
};

export default Landing;
