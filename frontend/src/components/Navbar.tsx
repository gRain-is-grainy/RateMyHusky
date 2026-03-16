import { useState, useEffect, useLayoutEffect, useRef, useCallback } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import SignInModal from './SignInModal';
import './Navbar.css';

const Navbar = () => {
  const { user, loading: authLoading, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const [showSignIn, setShowSignIn] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);
  const [pillStyle, setPillStyle] = useState({ left: 0, width: 0, opacity: 0 });
  const [isReady, setIsReady] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const location = useLocation();

  const updatePill = useCallback(() => {
    if (!containerRef.current) return;
    const activeLink = containerRef.current.querySelector('.nav-link.active') as HTMLElement;
    
    if (activeLink) {
      setPillStyle({
        left: activeLink.offsetLeft,
        width: activeLink.offsetWidth,
        opacity: 1
      });
    } else {
      setPillStyle(prev => ({ ...prev, opacity: 0 }));
    }
  }, []);

  // Track route changes
  useLayoutEffect(() => {
    updatePill();
  }, [location.pathname, updatePill]);

  // Handle initialization and resize via ResizeObserver
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // Measure initially
    updatePill();

    // Enable animations after first layout
    const readyTimer = setTimeout(() => setIsReady(true), 100);

    const observer = new ResizeObserver(() => {
      // Temporarily disable animation during resize for smoothness
      setIsReady(false);
      updatePill();
      // Re-enable after resize settles
      setTimeout(() => setIsReady(true), 50);
    });

    observer.observe(container);

    return () => {
      clearTimeout(readyTimer);
      observer.disconnect();
    };
  }, [updatePill]);

  // Close user dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setShowUserMenu(false);
      }
    };
    if (showUserMenu) document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showUserMenu]);

  return (
    <>
    <nav className="navbar">
      <Link to="/" className="navbar-logo">
        <span>Rate</span>MyHusky
      </Link>

      {/* Hamburger button — mobile only */}
      <button
        className={`hamburger ${menuOpen ? 'open' : ''}`}
        onClick={() => setMenuOpen(!menuOpen)}
        aria-label="Toggle menu"
      >
        <span />
        <span />
        <span />
      </button>

      {/* Nav links — slides in on mobile */}
      <div className={`navbar-right ${menuOpen ? 'show' : ''}`}>
        <div className="nav-links-container" ref={containerRef}>
          <div 
            className={`nav-pill-background ${isReady ? 'animate' : ''}`}
            style={{
              transform: `translateX(${pillStyle.left}px)`,
              width: `${pillStyle.width}px`,
              opacity: pillStyle.opacity,
              visibility: pillStyle.opacity === 0 ? 'hidden' : 'visible'
            }}
          />
          <NavLink to="/professors" className="nav-link" onClick={() => setMenuOpen(false)}>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
              <circle cx="9" cy="7" r="4" />
              <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
              <path d="M16 3.13a4 4 0 0 1 0 7.75" />
            </svg>
            Professors
          </NavLink>
          <NavLink to="/courses" className="nav-link" onClick={() => setMenuOpen(false)}>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
              <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
            </svg>
            Courses
          </NavLink>
          <NavLink to="/compare" className="nav-link" onClick={() => setMenuOpen(false)}>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="20" x2="18" y2="10" />
              <line x1="12" y1="20" x2="12" y2="4" />
              <line x1="6" y1="20" x2="6" y2="14" />
            </svg>
            Compare
          </NavLink>
        </div>
        {authLoading ? null : user ? (
          <div className="navbar-user" ref={userMenuRef}>
            <button className="navbar-user-btn" onClick={() => setShowUserMenu(v => !v)}>
              {user.picture && <img src={user.picture} alt="" className="navbar-user-avatar" referrerPolicy="no-referrer" />}
              <span className="navbar-user-name">{user.name.split(' ')[0]}</span>
            </button>
            {showUserMenu && (
              <div className="navbar-user-dropdown">
                <p className="navbar-user-email">{user.email}</p>
                <button className="navbar-user-signout" onClick={() => { logout(); setShowUserMenu(false); setMenuOpen(false); }}>Sign Out</button>
              </div>
            )}
          </div>
        ) : (
          <button className="signin-btn" onClick={() => { setShowSignIn(true); setMenuOpen(false); }}>Sign In</button>
        )}
      </div>

      {/* Overlay behind mobile menu */}
      {menuOpen && <div className="navbar-overlay" onClick={() => setMenuOpen(false)} />}

    </nav>
    <SignInModal open={showSignIn} onClose={() => setShowSignIn(false)} />
    </>
  );
};

export default Navbar;