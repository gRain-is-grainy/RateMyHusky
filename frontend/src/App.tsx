import { useEffect, useRef } from 'react';
import { BrowserRouter as Router, Routes, Route, useLocation } from 'react-router-dom';
import { Analytics } from '@vercel/analytics/react';
import { SpeedInsights } from '@vercel/speed-insights/react';
import { AuthProvider } from './context/AuthContext';
import Homepage from './pages/Homepage';
import Professor from './pages/Professor';
import ProfessorCatalog from './pages/ProfessorCatalog';
import Compare from './pages/Compare';
import NotFound from './pages/NotFound';
import Navbar from './components/Navbar';
import FeedbackTab from './components/FeedbackTab';
import ThemeToggle from './components/ThemeToggle';
import './App.css';

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}

function AnimatedRoutes() {
  const location = useLocation();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.classList.remove('page-fade-in');
    // Force reflow so the animation restarts
    void el.offsetWidth;
    el.classList.add('page-fade-in');
  }, [location.pathname]);

  return (
    <div ref={ref} className="page-transition-wrapper page-fade-in">
      <Routes location={location}>
        <Route path="/" element={<Homepage />} />
        <Route path="/professors" element={<ProfessorCatalog />} />
        <Route path="/professors/:slug" element={<Professor />} />
        <Route path="/compare" element={<Compare />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <Router>
        <ScrollToTop />
        <Navbar />
        <AnimatedRoutes />
        <FeedbackTab />
        <ThemeToggle />
      </Router>
      <Analytics />
      <SpeedInsights />
    </AuthProvider>
  );
}

export default App;
