/**
 * Global scroll animation utility
 * Supports data-scroll, data-delay, data-duration, and scroll-stagger for children
 * Usage: <div data-scroll="fade-up" data-delay="100">...</div>
 *        <div class="scroll-stagger">...children animate in sequence...</div>
 */

const STAGGER_CHILD_DELAY = 80;
const DEFAULT_DURATION = 700;

export const initScrollAnimations = () => {
  if (window.scrollAnimationsInitialized) return;
  window.scrollAnimationsInitialized = true;

  const observerOptions = {
    threshold: 0.08,
    rootMargin: '0px 0px 100px 0px'
  };

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      const el = entry.target;

      // Stagger container: reveal children with delay
      if (el.classList.contains('scroll-stagger')) {
        if (el.classList.contains('scroll-stagger-visible')) return;
        el.classList.add('scroll-stagger-visible');
        if (el.dataset.once !== 'false') observer.unobserve(el);
        return;
      }

      // data-scroll element
      if (!el.dataset.scroll) return;
      if (el.classList.contains('animate-in')) return;

      const animationType = el.dataset.scroll || 'fade-up';
      const delay = parseInt(el.dataset.delay, 10) || 0;
      const once = el.dataset.once !== 'false';
      const duration = parseInt(el.dataset.duration, 10) || DEFAULT_DURATION;

      el.classList.add(`scroll-animate-${animationType}`);
      el.style.opacity = '0';
      el.style.transitionDuration = `${duration}ms`;

      setTimeout(() => {
        el.classList.add('animate-in');
        el.style.opacity = '1';
        if (once) observer.unobserve(el);
      }, delay);
    });
  }, observerOptions);

  const observeElements = () => {
    document.querySelectorAll('[data-scroll]').forEach((el) => {
      if (!el.classList.contains('scroll-animate-initialized')) {
        el.classList.add('scroll-animate-initialized');
        observer.observe(el);
      }
    });
    document.querySelectorAll('.scroll-stagger').forEach((el) => {
      if (!el.classList.contains('scroll-stagger-initialized')) {
        el.classList.add('scroll-stagger-initialized');
        observer.observe(el);
      }
    });
  };

  observeElements();
  const mutationObserver = new MutationObserver(() => { setTimeout(observeElements, 120); });
  const target = document.body;
  mutationObserver.observe(target, { childList: true, subtree: true });

  return () => {
    observer.disconnect();
    mutationObserver.disconnect();
    window.scrollAnimationsInitialized = false;
  };
};

/**
 * Apply scroll animations to a specific element
 */
export const animateOnScroll = (element, options = {}) => {
  if (!element) return;

  const {
    animationType = 'fade-up',
    threshold = 0.1,
    rootMargin = '0px 0px -50px 0px',
    delay = 0,
    once = true
  } = options;

  element.classList.add(`scroll-animate-${animationType}`);
  element.style.opacity = '0';

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
    { threshold, rootMargin }
  );

  observer.observe(element);

  return () => observer.unobserve(element);
};

