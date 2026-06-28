import { motion, useScroll, useSpring } from 'framer-motion';
import './ScrollProgressBar.css';

/** Thin fixed bar at the very top of the viewport that fills as the page is scrolled. */
export default function ScrollProgressBar() {
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 300, damping: 40, mass: 0.2 });

  return <motion.div className="scroll-progress-bar" style={{ scaleX }} aria-hidden="true" />;
}
