import { memo } from 'react';
import { Link } from 'react-router-dom';
import { prefetchRoute } from '../utils/routePrefetch';

/**
 * Router Link that prefetches the route chunk on hover/focus/touch.
 */
function NavLinkPrefetch({ to, children, className, onClick, ...rest }) {
  const path = typeof to === 'string' ? to : to?.pathname || '/';

  const warm = () => prefetchRoute(path);

  return (
    <Link
      to={to}
      className={className}
      onMouseEnter={warm}
      onFocus={warm}
      onTouchStart={warm}
      onClick={(e) => {
        warm();
        onClick?.(e);
      }}
      {...rest}
    >
      {children}
    </Link>
  );
}

export default memo(NavLinkPrefetch);
