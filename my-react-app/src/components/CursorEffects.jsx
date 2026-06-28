import { useState, useEffect, useRef } from 'react';
import './CursorEffects.css';

const HOVER_SELECTORS = 'a, button, [role="button"], input, select, textarea, .btn, [data-cursor-hover], [onclick]';

export default function CursorEffects() {
  const [enabled, setEnabled] = useState(false);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isHovering, setIsHovering] = useState(false);
  const [isVisible, setIsVisible] = useState(false);
  const rafRef = useRef(null);
  const posRef = useRef({ x: 0, y: 0 });
  const targetRef = useRef({ x: 0, y: 0 });
  const hoverRef = useRef(false);
  const prevHoverRef = useRef(false);

  useEffect(() => {
    try {
      const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      const fine = window.matchMedia('(pointer: fine)').matches;
      setEnabled(!reduced && fine);
    } catch (_) {
      setEnabled(false);
    }
  }, []);

  useEffect(() => {
    if (!enabled) return;

    const lerp = (current, target, factor) => current + (target - current) * factor;

    const handleMove = (e) => {
      targetRef.current = { x: e.clientX, y: e.clientY };
      if (!isVisible) setIsVisible(true);
    };

    const animate = () => {
      const factor = 0.18;
      posRef.current.x = lerp(posRef.current.x, targetRef.current.x, factor);
      posRef.current.y = lerp(posRef.current.y, targetRef.current.y, factor);
      setPosition({ x: posRef.current.x, y: posRef.current.y });
      if (hoverRef.current !== prevHoverRef.current) {
        prevHoverRef.current = hoverRef.current;
        setIsHovering(hoverRef.current);
      }
      rafRef.current = requestAnimationFrame(animate);
    };

    const handleOver = (e) => {
      const el = e.target.closest(HOVER_SELECTORS);
      if (el && !el.disabled) hoverRef.current = true;
    };

    const handleOut = () => {
      hoverRef.current = false;
    };

    rafRef.current = requestAnimationFrame(animate);
    window.addEventListener('mousemove', handleMove, { passive: true });
    document.addEventListener('mouseover', handleOver, { passive: true });
    document.addEventListener('mouseout', handleOut, { passive: true });

    const handleLeave = () => setIsVisible(false);
    document.documentElement.addEventListener('mouseleave', handleLeave, { passive: true });

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      window.removeEventListener('mousemove', handleMove);
      document.removeEventListener('mouseover', handleOver);
      document.removeEventListener('mouseout', handleOut);
      document.documentElement.removeEventListener('mouseleave', handleLeave);
    };
  }, [enabled, isVisible]);

  useEffect(() => {
    if (!isVisible) {
      document.body.classList.remove('cursor-effects-active');
      return;
    }
    const isFine = window.matchMedia('(pointer: fine)').matches;
    if (isFine) document.body.classList.add('cursor-effects-active');
    return () => document.body.classList.remove('cursor-effects-active');
  }, [isVisible]);

  if (!enabled) return null;

  return (
    <div
      className={`cursor-effects ${isVisible ? 'visible' : ''} ${isHovering ? 'hover' : ''}`}
      style={{
        '--cursor-x': `${position.x}px`,
        '--cursor-y': `${position.y}px`,
      }}
      aria-hidden
    >
      <div className="cursor-dot" />
      <div className="cursor-ring" />
    </div>
  );
}
