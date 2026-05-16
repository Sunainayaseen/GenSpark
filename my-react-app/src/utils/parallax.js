/**
 * Parallax scrolling utility
 * Adds smooth parallax effects to elements on scroll
 */

export const initParallax = () => {
  const parallaxElements = document.querySelectorAll('[data-parallax]');
  
  if (parallaxElements.length === 0) return;

  const handleScroll = () => {
    const scrollY = window.pageYOffset;
    
    parallaxElements.forEach((element) => {
      const speed = parseFloat(element.dataset.parallax) || 0.5;
      const offset = scrollY * speed;
      
      element.style.transform = `translateY(${offset}px)`;
    });
  };

  // Throttle scroll events for performance
  let ticking = false;
  const onScroll = () => {
    if (!ticking) {
      window.requestAnimationFrame(() => {
        handleScroll();
        ticking = false;
      });
      ticking = true;
    }
  };

  window.addEventListener('scroll', onScroll, { passive: true });
  
  return () => {
    window.removeEventListener('scroll', onScroll);
  };
};

/**
 * Apply parallax to a specific element
 */
export const applyParallax = (element, speed = 0.5) => {
  if (!element) return;

  const handleScroll = () => {
    const scrollY = window.pageYOffset;
    const offset = scrollY * speed;
    element.style.transform = `translateY(${offset}px)`;
  };

  let ticking = false;
  const onScroll = () => {
    if (!ticking) {
      window.requestAnimationFrame(() => {
        handleScroll();
        ticking = false;
      });
      ticking = true;
    }
  };

  window.addEventListener('scroll', onScroll, { passive: true });
  
  return () => {
    window.removeEventListener('scroll', onScroll);
  };
};










