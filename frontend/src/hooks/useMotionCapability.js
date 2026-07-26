import { useEffect, useState } from 'react';

/**
 * Whether the device can comfortably handle hover-driven motion (3D tilt, parallax,
 * a mouse-reactive canvas): no OS/browser reduced-motion preference, a fine pointer
 * (mouse/trackpad, not touch), and — optionally — a wide-enough viewport that the
 * effect wouldn't just be wasted off-screen on small devices.
 */
export function useMotionCapability({ minWidth = 0 } = {}) {
  const [capable, setCapable] = useState(false);

  useEffect(() => {
    const evaluate = () => {
      try {
        const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        const fine = window.matchMedia('(pointer: fine)').matches;
        const wide = window.innerWidth >= minWidth;
        setCapable(!reduced && fine && wide);
      } catch {
        setCapable(false);
      }
    };
    evaluate();
    window.addEventListener('resize', evaluate);
    return () => window.removeEventListener('resize', evaluate);
  }, [minWidth]);

  return capable;
}
