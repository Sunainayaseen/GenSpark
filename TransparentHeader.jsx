import { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import './TransparentHeader.css';

const TransparentHeader = () => {
  const [isScrolled, setIsScrolled] = useState(false);
  const location = useLocation();

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 50);
    };

    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <header className={`header ${isScrolled ? 'scrolled' : ''}`}>
      <div className="container">
        <div className="header-content">
          {/* LEFT: LOGO + TEXT */}
          <Link to="/" className="logo">
            <img 
              src="/logo.png" 
              alt="Logo" 
              className="logo-image"
            />
            <span className="logo-text">GenSpark Builds</span>
          </Link>

          {/* CENTER: NAVIGATION LINKS */}
          <nav className="nav">
            <Link 
              to="/" 
              className={location.pathname === '/' ? 'active' : ''}
            >
              Home
            </Link>
            <Link 
              to="/builds"
              className={location.pathname === '/builds' ? 'active' : ''}
            >
              Builds
            </Link>
            <Link 
              to="/blogs"
              className={location.pathname === '/blogs' ? 'active' : ''}
            >
              Blogs
            </Link>
            <Link 
              to="/about"
              className={location.pathname === '/about' ? 'active' : ''}
            >
              About
            </Link>
            <Link 
              to="/contact"
              className={location.pathname === '/contact' ? 'active' : ''}
            >
              Contact
            </Link>
          </nav>

          {/* RIGHT: BUTTONS */}
          <div className="header-buttons">
            <button className="btn btn-secondary">Login</button>
            <button className="btn btn-primary">Sign Up</button>
          </div>
        </div>
      </div>
    </header>
  );
};

export default TransparentHeader;

