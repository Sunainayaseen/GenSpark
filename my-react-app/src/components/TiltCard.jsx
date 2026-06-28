import { useRef } from 'react';
import { useMotionCapability } from '../hooks/useMotionCapability';
import './TiltCard.css';

/**
 * Wrapper that adds a pointer-relative 3D tilt + lift to whatever card markup/classes
 * are passed in via `className`. On touch/reduced-motion devices the tilt is skipped
 * entirely — the card keeps whatever plain :hover effect its own CSS already defines.
 */
export default function TiltCard({ as = 'div', className = '', tiltStrength = 8, children, ...rest }) {
  const ref = useRef(null);
  const capable = useMotionCapability();
  const Tag = as;

  const handleMove = (e) => {
    if (!capable) return;
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const px = (e.clientX - rect.left) / rect.width;
    const py = (e.clientY - rect.top) / rect.height;
    const rx = (0.5 - py) * tiltStrength;
    const ry = (px - 0.5) * tiltStrength;
    el.style.transition = 'transform 0.05s linear';
    el.style.transform = `perspective(900px) rotateX(${rx}deg) rotateY(${ry}deg) translateY(-6px) scale(1.015)`;
  };

  const handleLeave = () => {
    const el = ref.current;
    if (!el) return;
    el.style.transition = 'transform 0.5s cubic-bezier(0.34, 1.56, 0.64, 1)';
    el.style.transform = '';
  };

  return (
    <Tag
      ref={ref}
      className={`tilt-card ${className}`}
      onMouseMove={handleMove}
      onMouseLeave={handleLeave}
      {...rest}
    >
      {children}
    </Tag>
  );
}
