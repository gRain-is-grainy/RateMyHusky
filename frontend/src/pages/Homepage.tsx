/*
Primary Homepage Codespace
*/
import { useState, useEffect, useRef, useCallback, useLayoutEffect } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import SearchBar from '../components/SearchBar';
import Footer from '../components/Footer';
import { fetchStats, fetchColleges, fetchGoatProfessors, fetchRandomProfessor, fetchProfessorsCatalog } from '../api/api';
import type { Stat, Professor } from '../api/api';
import neuIcon from '../assets/neu-circle-icon.png';
import './Homepage.css';

/* ---- animated stat counter ---- */
const AnimatedStat = ({ value, label }: Stat) => {
  const ref = useRef<HTMLDivElement>(null);
  const [display, setDisplay] = useState('0');
  const [hasAnimated, setHasAnimated] = useState(false);

  // Parse "7,600+" → { num: 7600, suffix: "+" }
  const parsed = useRef({ num: 0, suffix: '' });
  useEffect(() => {
    const clean = value.replace(/,/g, '');
    const match = clean.match(/^(\d+)(.*)$/);
    if (match) {
      parsed.current = { num: parseInt(match[1], 10), suffix: match[2] };
    }
  }, [value]);

  const animate = useCallback(() => {
    if (hasAnimated) return;
    setHasAnimated(true);

    const { num, suffix } = parsed.current;
    const duration = 2000;
    const start = performance.now();

    const step = (now: number) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = Math.round(eased * num);
      setDisplay(current.toLocaleString() + suffix);

      if (progress < 1) {
        requestAnimationFrame(step);
      }
    };

    requestAnimationFrame(step);
  }, [hasAnimated]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          animate();
          observer.disconnect();
        }
      },
      { threshold: 0.5 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [animate]);

  return (
    <div className="stat-item" ref={ref}>
      <span className="stat-value">{display}</span>
      <span className="stat-label">{label}</span>
    </div>
  );
};

/* ---- partial star renderer ---- */
const Stars = ({ rating }: { rating: number }) => {
  // Width percentage: e.g. rating 4.3 → 86% of 5 stars
  const pct = (Math.min(Math.max(rating, 0), 5) / 5) * 100;
  return (
    <span className="stars-wrapper">
      <span className="stars-empty">★★★★★</span>
      <span className="stars-filled" style={{ width: `${pct}%` }}>★★★★★</span>
    </span>
  );
};

/* ---- rating cell with hover/click tooltip ---- */
const RatingCell = ({ prof, isOpen, onToggle }: {
  prof: Professor;
  isOpen: boolean;
  onToggle: () => void;
}) => {
  const ref = useRef<HTMLSpanElement>(null);

  // Close on outside click
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onToggle();
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [isOpen, onToggle]);

  return (
    <span
      ref={ref}
      className="goat-col-rating goat-rating-wrapper"
      onClick={(e) => { e.stopPropagation(); onToggle(); }}
    >
      <span className="goat-score">{prof.avgRating?.toFixed(2) ?? '—'}</span>
      <Stars rating={prof.avgRating ?? 0} />
      <span className="goat-rating-hint">ⓘ</span>

      {isOpen && (
        <div className="goat-rating-tooltip">
          <div className="tooltip-row">
            <span className="tooltip-label">RMP</span>
            <span className="tooltip-value">
              {prof.rmpRating !== null ? prof.rmpRating.toFixed(2) : '—'}
            </span>
          </div>
          <div className="tooltip-row">
            <span className="tooltip-label">TRACE</span>
            <span className="tooltip-value">
              {prof.traceRating !== null ? prof.traceRating.toFixed(2) : '—'}
            </span>
          </div>
          <div className="tooltip-divider" />
          <div className="tooltip-row">
            <span className="tooltip-label">Avg Rating</span>
            <span className="tooltip-value tooltip-blended">{prof.avgRating?.toFixed(2) ?? '—'}</span>
          </div>
        </div>
      )}
    </span>
  );
};

const Homepage = () => {
  const navigate = useNavigate();
  const location = useLocation();

  // Scroll to hash anchor (e.g. /#shuffle, /#goated) on navigation
  useEffect(() => {
    if (location.hash) {
      const el = document.getElementById(location.hash.slice(1));
      if (el) {
        setTimeout(() => el.scrollIntoView({ behavior: 'smooth' }), 100);
      }
    }
  }, [location.hash]);
  const [stats, setStats] = useState<Stat[]>([]);
  const [colleges, setColleges] = useState<string[]>([]);
  const [selectedCollege, setSelectedCollege] = useState<string>('');
  const [profs, setProfs] = useState<Professor[]>([]);
  const [loading, setLoading] = useState(true);
  const [profsLoading, setProfsLoading] = useState(false);
  const [shuffling, setShuffling] = useState(false);
  const [openTooltip, setOpenTooltip] = useState<number | null>(null);
  const tabsRef = useRef<HTMLDivElement>(null);
  const [tabsAtEnd, setTabsAtEnd] = useState(false);
  const [tabsAtStart, setTabsAtStart] = useState(true);
  const leaderboardRef = useRef<HTMLDivElement>(null);
  const [leaderFade, setLeaderFade] = useState({ left: false, right: false });

  const updateLeaderFade = useCallback(() => {
    const el = leaderboardRef.current;
    if (!el) return;
    setLeaderFade({
      left: el.scrollLeft > 0,
      right: el.scrollLeft + el.clientWidth < el.scrollWidth - 1,
    });
  }, []);

  useEffect(() => {
    const el = leaderboardRef.current;
    if (!el) return;
    updateLeaderFade();
    el.addEventListener('scroll', updateLeaderFade, { passive: true });
    return () => el.removeEventListener('scroll', updateLeaderFade);
  }, [profs, updateLeaderFade]);

  // Pill animation state
  const [pillStyle, setPillStyle] = useState({ left: 0, width: 0, opacity: 0 });
  const [isPillReady, setIsPillReady] = useState(false);

  // Navigate to professor page
  const handleProfClick = (name: string) => {
    const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
    navigate(`/professors/${slug}`, {
      state: { fromPage: { label: 'GOATED Professors', url: '/#goated' }, goatedCollege: selectedCollege },
    });
  };

  const updatePill = useCallback(() => {
    if (!tabsRef.current) return;
    const activeTab = tabsRef.current.querySelector('.goat-tab.active') as HTMLElement;
    if (activeTab) {
      setPillStyle({
        left: activeTab.offsetLeft,
        width: activeTab.offsetWidth,
        opacity: 1
      });
    }
  }, []);

  // Update pill on selection change
  useLayoutEffect(() => {
    updatePill();
  }, [selectedCollege, updatePill]);

  // Handle initialization and resize via ResizeObserver
  useEffect(() => {
    const container = tabsRef.current;
    if (!container) return;

    updatePill();
    const readyTimer = setTimeout(() => setIsPillReady(true), 150);

    const observer = new ResizeObserver(() => {
      setIsPillReady(false);
      updatePill();
      setTimeout(() => setIsPillReady(true), 50);
    });

    observer.observe(container);
    return () => {
      clearTimeout(readyTimer);
      observer.disconnect();
    };
  }, [updatePill, colleges]);

  // Detect scroll position on college tabs
  useEffect(() => {
    const el = tabsRef.current;
    if (!el) return;

    const checkScroll = () => {
      setTabsAtStart(el.scrollLeft <= 10);
      setTabsAtEnd(el.scrollLeft + el.clientWidth >= el.scrollWidth - 10);
    };

    checkScroll();
    el.addEventListener('scroll', checkScroll);
    window.addEventListener('resize', checkScroll);
    return () => {
      el.removeEventListener('scroll', checkScroll);
      window.removeEventListener('resize', checkScroll);
    };
  }, [colleges]);

  // Initial data load
  useEffect(() => {
    async function init() {
      try {
        const [statsData, collegeData] = await Promise.all([
          fetchStats(),
          fetchColleges(),
        ]);
        setStats(statsData);
        setColleges(collegeData);
        const state = location.state as { goatedCollege?: string } | null;
        const restored = state?.goatedCollege;
        if (restored && collegeData.includes(restored)) {
          setSelectedCollege(restored);
        } else if (collegeData.length > 0) {
          setSelectedCollege(collegeData[0]);
        }
      } catch (err) {
        console.error('Failed to load homepage data:', err);
      } finally {
        setLoading(false);
      }
    }
    init();
  }, []);

  // Load GOAT professors when selected college changes
  useEffect(() => {
    if (!selectedCollege) return;
    let cancelled = false;

    async function loadProfs() {
      setProfsLoading(true);
      setOpenTooltip(null);
      try {
        const data = await fetchGoatProfessors(selectedCollege);
        if (!cancelled) setProfs(data);
      } catch (err) {
        console.error('Failed to load professors:', err);
      } finally {
        if (!cancelled) setProfsLoading(false);
      }
    }
    loadProfs();

    return () => { cancelled = true; };
  }, [selectedCollege]);


  const [slotResult, setSlotResult] = useState<{ name: string; dept: string; college: string; slug: string } | null>(null);
  const [wheelState, setWheelState] = useState<'idle' | 'spinning' | 'result'>('idle');
  const WHEEL_SLICES = 16;
  const SLICE_DEG = 360 / WHEEL_SLICES;
  const [wheelNames, setWheelNames] = useState<string[]>(Array.from({ length: WHEEL_SLICES }, () => ''));
  const [wheelRotation, setWheelRotation] = useState(0);
  const [wheelDurationMs, setWheelDurationMs] = useState(0);

  const realWheelNames = Array.from(new Set(profs.map((p) => p.name).filter(Boolean)));

  type PrefetchedProf = { prof: Awaited<ReturnType<typeof fetchRandomProfessor>>; names: string[] };
  const prefetchedProfRef = useRef<PrefetchedProf | null>(null);
  const prefetchingRef = useRef(false);

  const prefetchNext = useCallback(async () => {
    if (prefetchingRef.current) return;
    prefetchingRef.current = true;
    try {
      const prof = await fetchRandomProfessor();
      const uniqueNames: string[] = [];
      const uniqueSet = new Set<string>();
      const pushUnique = (name: string) => {
        const trimmed = name.trim();
        if (!trimmed || uniqueSet.has(trimmed)) return;
        uniqueSet.add(trimmed);
        uniqueNames.push(trimmed);
      };
      pushUnique(prof.name);
      realWheelNames.forEach(pushUnique);
      if (uniqueNames.length < WHEEL_SLICES) {
        const collegeCatalog = await fetchProfessorsCatalog({
          college: selectedCollege || undefined,
          page: 1,
          limit: 300,
          sort: 'alpha',
        });
        collegeCatalog.professors.forEach((p) => pushUnique(p.name));
      }
      if (uniqueNames.length < WHEEL_SLICES) {
        const globalCatalog = await fetchProfessorsCatalog({ page: 1, limit: 500, sort: 'alpha' });
        globalCatalog.professors.forEach((p) => pushUnique(p.name));
      }
      if (uniqueNames.length >= WHEEL_SLICES) {
        prefetchedProfRef.current = { prof, names: uniqueNames };
      }
    } catch {
      // silently fail — handleShuffle will fall back to fetching itself
    } finally {
      prefetchingRef.current = false;
    }
  }, [realWheelNames, selectedCollege]);

  useEffect(() => { prefetchNext(); }, [prefetchNext]);

  const handleShuffle = async () => {
    if (shuffling) return;
    setShuffling(true);
    setSlotResult(null);
    setWheelState('spinning');

    try {
      let prof: Awaited<ReturnType<typeof fetchRandomProfessor>>;
      let uniqueNames: string[];

      if (prefetchedProfRef.current && prefetchedProfRef.current.names.length >= WHEEL_SLICES) {
        ({ prof, names: uniqueNames } = prefetchedProfRef.current);
        prefetchedProfRef.current = null;
      } else {
        // fallback: fetch now (first click before prefetch completes)
        prof = await fetchRandomProfessor();
        uniqueNames = [];
        const uniqueSet = new Set<string>();
        const pushUnique = (name: string) => {
          const trimmed = name.trim();
          if (!trimmed || uniqueSet.has(trimmed)) return;
          uniqueSet.add(trimmed);
          uniqueNames.push(trimmed);
        };
        pushUnique(prof.name);
        realWheelNames.forEach(pushUnique);
        if (uniqueNames.length < WHEEL_SLICES) {
          const collegeCatalog = await fetchProfessorsCatalog({
            college: selectedCollege || undefined,
            page: 1,
            limit: 300,
            sort: 'alpha',
          });
          collegeCatalog.professors.forEach((p) => pushUnique(p.name));
        }
        if (uniqueNames.length < WHEEL_SLICES) {
          const globalCatalog = await fetchProfessorsCatalog({ page: 1, limit: 500, sort: 'alpha' });
          globalCatalog.professors.forEach((p) => pushUnique(p.name));
        }
        if (uniqueNames.length < WHEEL_SLICES) {
          throw new Error('Not enough unique professor names to build a 16-slice wheel.');
        }
      }

      const slug = prof.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

      const fixedPool = [...uniqueNames].sort(() => Math.random() - 0.5).slice(0, WHEEL_SLICES);
      const shuffled = [...fixedPool].sort(() => Math.random() - 0.5);
      const winnerIndex = Math.max(0, shuffled.indexOf(prof.name));
      setWheelNames(shuffled);

      const currentNormalized = ((wheelRotation % 360) + 360) % 360;
      const winnerCenterAngle = (winnerIndex + 0.5) * SLICE_DEG;
      // In our wheel transform system, 0deg is the top marker position.
      const pointerAngle = 0;
      const targetNormalized = (pointerAngle - winnerCenterAngle + 360) % 360;
      const delta = (targetNormalized - currentNormalized + 360) % 360;
      const extraSpins = 360 * 6;
      const finalRotation = wheelRotation + extraSpins + delta;

      setWheelDurationMs(0);
      await new Promise<void>(r => requestAnimationFrame(() => requestAnimationFrame(() => r())));
      setWheelDurationMs(4800);
      setWheelRotation(finalRotation);

      // Prefetch the next professor while the wheel is spinning
      prefetchNext();

      await new Promise(r => setTimeout(r, 5000));

      setSlotResult({ name: prof.name, dept: prof.dept ?? '', college: prof.college ?? '', slug });
      setWheelState('result');
    } catch (err) {
      console.error('Failed to fetch random professor:', err);
      setWheelState('idle');
    } finally {
      setShuffling(false);
    }
  };

  return (
    <div className="homepage">
      {/* ======== Hero ======== */}
      <main className="homepage-hero">
        <div
          className="hero-bg-pattern"
          style={{ backgroundImage: `url(${neuIcon})` }}
        />
        <h1 className="hero-tagline">
          Find the <span>right professor</span>, every semester
        </h1>
        <p className="hero-subtitle">
          TRACE evaluations and RateMyProfessor ratings, all in one place.
        </p>

        <SearchBar />
      </main>

      {/* ======== Stats Banner ======== */}
      <section className="stats-banner">
        {loading
          ? Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="stat-item">
                <span className="stat-value">—</span>
                <span className="stat-label">Loading…</span>
              </div>
            ))
          : stats.map((s) => (
              <AnimatedStat key={s.label} value={s.value} label={s.label} />
            ))}
      </section>

      {/* ======== GOAT Professors Leaderboard ======== */}
      <section id="goated" className="section goat-section">
        <div className="section-header">
          <h2 className="section-title">GOATED Professors</h2>
        </div>

        <div
          className={`goat-college-tabs${tabsAtStart ? ' scrolled-start' : ''}${tabsAtEnd ? ' scrolled-end' : ''}`}
          ref={tabsRef}
        >
          <div 
            className={`goat-pill-background ${isPillReady ? 'animate' : ''}`}
            style={{
              transform: `translateX(${pillStyle.left}px)`,
              width: `${pillStyle.width}px`,
              opacity: pillStyle.opacity,
              visibility: pillStyle.opacity === 0 ? 'hidden' : 'visible'
            }}
          />
          {colleges.map((c) => (
            <button
              key={c}
              className={`goat-tab ${c === selectedCollege ? 'active' : ''}`}
              onClick={(e) => {
                setSelectedCollege(c);
                const container = tabsRef.current;
                const btn = e.currentTarget;
                if (container) {
                  const fadeWidth = 40;
                  const targetScroll = Math.max(0, btn.offsetLeft - fadeWidth);
                  const maxScroll = container.scrollWidth - container.clientWidth;
                  container.scrollTo({
                    left: Math.min(targetScroll, maxScroll),
                    behavior: 'smooth',
                  });
                }
              }}
            >
              {c}
            </button>
          ))}
        </div>

        <div className={`goat-scroll-wrap${leaderFade.left ? ' fade-left' : ''}${leaderFade.right ? ' fade-right' : ''}`}>
        <div ref={leaderboardRef} className={`goat-leaderboard ${profsLoading ? 'goat-loading' : ''}`}>
          <div className="goat-header-row">
            <span className="goat-col-rank">#</span>
            <span className="goat-col-name">Professor</span>
            <span className="goat-col-dept">Department</span>
            <span className="goat-col-rating">Rating</span>
            <span className="goat-col-reviews">Reviews</span>
          </div>

          {profs.length === 0 && !profsLoading ? (
            <div className="goat-row" style={{ justifyContent: 'center', opacity: 0.6 }}>
              No professors found for this college.
            </div>
          ) : (
            profs.map((p, i) => (
              <div
                key={p.name}
                className={`goat-row ${i < 3 ? 'goat-top3' : ''}`}
                onClick={() => handleProfClick(p.name)}
              >
                <span className="goat-col-rank">
                  {i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : i + 1}
                </span>
                <div className="goat-col-name">
                  <span className="goat-name-text">{p.name}</span>
                </div>
                <span className="goat-col-dept">{p.dept}</span>
                <RatingCell
                  prof={p}
                  isOpen={openTooltip === i}
                  onToggle={() => setOpenTooltip(openTooltip === i ? null : i)}
                />
                <span className="goat-col-reviews">
                  {(p.totalComments ?? 0).toLocaleString()}
                </span>
              </div>
            ))
          )}
        </div>
        </div>

        {selectedCollege && (
          <Link
            to={`/professors?college=${encodeURIComponent(selectedCollege)}&sort=rating`}
            className="goat-view-all"
          >
            View all {selectedCollege} professors →
          </Link>
        )}
      </section>

      {/* ======== Professor Randomizer ======== */}
      <section id="shuffle" className="section randomizer-section">
        <div className="randomizer-content">
          <div className="randomizer-text">
            <h2 className="section-title">🎲 Feeling Lucky?</h2>
            <p className="randomizer-desc">
              Discover a random professor and check out their ratings. You might find your next favorite class.
            </p>
          </div>

          <div className={`wheel-spinner ${wheelState} ${slotResult ? 'has-result' : ''}`}>
            <div className="wheel-pointer" />

            <div className="wheel-shell">
              <div
                className="wheel-disc"
                style={wheelState === 'idle'
                  ? undefined
                  : {
                      transform: `rotate(${wheelRotation}deg)`,
                      transition: wheelDurationMs > 0
                        ? `transform ${wheelDurationMs}ms cubic-bezier(0.14, 0.78, 0.18, 1)`
                        : 'none',
                    }
                }
              >
                <div className="wheel-face" />
                {wheelNames.map((name, i) => (
                  <div
                    key={`${i}-${name || 'blank'}`}
                    className="wheel-slice-name"
                    style={{ transform: `rotate(${i * SLICE_DEG}deg) translateY(var(--wheel-label-radius))` }}
                  >
                    <span>{name}</span>
                  </div>
                ))}
              </div>

              <button
                className={`wheel-center-btn ${slotResult ? 'winner' : ''}`}
                onClick={(e) => {
                  e.stopPropagation();
                  handleShuffle();
                }}
                disabled={shuffling}
              >
                {shuffling ? 'Spinning...' : slotResult ? 'Spin Again' : 'Spin'}
              </button>
            </div>

            {slotResult && (
              <div className="wheel-result-card" onClick={() => navigate(`/professors/${slotResult.slug}`, { state: { fromPage: { label: 'Shuffle Wheel', url: '/#shuffle' } } })}>
                <span className="wheel-result-name">{slotResult.name}</span>
                <span className="wheel-result-sub">{slotResult.dept}</span>
              </div>
            )}
          </div>
        </div>
      </section>

      <Footer />
    </div>
  );
};

export default Homepage;