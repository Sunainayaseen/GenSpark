import { useEffect, useRef } from 'react';

/**
 * Custom hook for scroll-triggered animations
 * Automatically animates elements when they come into view
 * 
 * @param {Object} options - Configuration options
 * @param {string} options.animationType - Type of animation: 'fade', 'slide-up', 'slide-down', 'slide-left', 'slide-right', 'scale', 'rotate'
 * @param {number} options.threshold - Intersection threshold (0-1)
 * @param {string} options.rootMargin - Root margin for intersection observer
 * @param {number} options.delay - Delay in milliseconds before animation starts
 * @param {boolean} options.once - Whether to animate only once (default: true)
 */
export const useScrollAnimation = (options = {}) => {
  const elementRef = useRef(null);
  const {
    animationType = 'fade',
    threshold = 0.1,
    rootMargin = '0px 0px -50px 0px',
    delay = 0,
    once = true
  } = options;

  useEffect(() => {
    const element = elementRef.current;
    if (!element) return;

    // Add initial animation class
    element.classList.add(`scroll-animate-${animationType}`);
    element.style.opacity = '0';
    element.style.transition = `all 0.8s cubic-bezier(0.4, 0, 0.2, 1) ${delay}ms`;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setTimeout(() => {
              entry.target.classList.add('animate-in');
              entry.target.style.opacity = '1';
              
              if (once) {
                observer.unobserve(entry.target);
              }
            }, delay);
          } else if (!once) {
            entry.target.classList.remove('animate-in');
            entry.target.style.opacity = '0';
          }
        });
      },
      {
        threshold,
        rootMargin
      }
    );

    observer.observe(element);

    return () => {
      if (element) {
        observer.unobserve(element);
      }
    };
  }, [animationType, threshold, rootMargin, delay, once]);

  return elementRef;
};

/**
 * Hook to observe multiple elements at once
 * Useful for animating lists of items with staggered delays
 */
export const useScrollAnimationList = (items, options = {}) => {
  const {
    animationType = 'fade',
    threshold = 0.1,
    rootMargin = '0px 0px -50px 0px',
    staggerDelay = 100,
    once = true
  } = options;

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry, index) => {
          if (entry.isIntersecting) {
            const delay = index * staggerDelay;
            setTimeout(() => {
              entry.target.classList.add('animate-in');
              entry.target.style.opacity = '1';
              
              if (once) {
                observer.unobserve(entry.target);
              }
            }, delay);
          } else if (!once) {
            entry.target.classList.remove('animate-in');
            entry.target.style.opacity = '0';
          }
        });
      },
      {
        threshold,
        rootMargin
      }
    );

    items.forEach((item) => {
      if (item?.current) {
        item.current.classList.add(`scroll-animate-${animationType}`);
        item.current.style.opacity = '0';
        item.current.style.transition = `all 0.8s cubic-bezier(0.4, 0, 0.2, 1)`;
        observer.observe(item.current);
      }
    });

    return () => {
      items.forEach((item) => {
        if (item?.current) {
          observer.unobserve(item.current);
        }
      });
    };
  }, [items, animationType, threshold, rootMargin, staggerDelay, once]);
};












