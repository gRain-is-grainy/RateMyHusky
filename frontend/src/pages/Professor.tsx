import { useState, useEffect, useRef, useCallback, useMemo, useLayoutEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import Footer from '../components/Footer';
import NotFound from './NotFound';
import FeedbackTab from '../components/FeedbackTab';
import ThemeToggle from '../components/ThemeToggle';
import Dropdown from '../components/Dropdown';
import StarRating from '../components/StarRating';
import RatingBar from '../components/RatingBar';
import { fetchProfessorData } from '../api/api';
import type { ProfessorProfile, ProfessorReview, TraceComment } from '../api/api';
import neuIcon from '../assets/neu-circle-icon.png';
import './Professor.css';

/* ───────── animated number counter ───────── */
const AnimatedNumber = ({
  value, decimals = 2, suffix = '',
}: { value: number | null; decimals?: number; suffix?: string }) => {
  const [display, setDisplay] = useState('—');
  const hasAnimated = useRef(false);
  const ref = useRef<HTMLSpanElement>(null);
  const animate = useCallback(() => {
    if (hasAnimated.current || value === null) return;
    hasAnimated.current = true;
    const duration = 1200;
    const start = performance.now();
    const step = (now: number) => {
      const t = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplay((eased * value).toFixed(decimals) + suffix);
      if (t < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }, [value, decimals, suffix]);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) { animate(); obs.disconnect(); } }, { threshold: 0.5 });
    obs.observe(el);
    return () => obs.disconnect();
  }, [animate]);
  return <span ref={ref}>{display}</span>;
};

/* ───────── sort / filter options ───────── */
const sortOptions = [
  { value: 'newest', label: 'Newest First' },
  { value: 'oldest', label: 'Oldest First' },
  { value: 'highest', label: 'Highest Rated' },
  { value: 'lowest', label: 'Lowest Rated' },
];

const traceSortOptions = [
  { value: 'popular', label: 'Most Popular' },
  { value: 'newest', label: 'Most Recent' },
  { value: 'alphabetical', label: 'A-Z' },
];

const courseFilterAll = { value: '__all__', label: 'All Courses' };

const GRADE_ORDER = ['A+','A','A-','B+','B','B-','C+','C','C-','D+','D','D-','F','W','WF','P','NP','I'];
const GRADE_COLORS: Record<string, string> = {
  'A+':'#1a9850','A':'#27ae60','A-':'#66bd63',
  'B+':'#a6d96a','B':'#d4e858','B-':'#fee08b',
  'C+':'#fdae61','C':'#f39c12','C-':'#e67e22',
  'D+':'#e74c3c','D':'#d73027','D-':'#c0392b',
  'F':'#a50026','W':'#7f8c8d','WF':'#636e72','P':'#2980b9','NP':'#8e44ad','I':'#999',
};

/* ═══════════════════════════════════════ */
const Professor = () => {
  const { slug } = useParams<{ slug: string }>();
  const reviewsRef = useRef<HTMLElement>(null);
  const [showBackToTop, setShowBackToTop] = useState(false);
  const [gradesAnimated, setGradesAnimated] = useState(false);
  const gradesRef = useRef<HTMLDivElement>(null);

  const [profile, setProfile] = useState<ProfessorProfile | null>(null);
  const [reviews, setReviews] = useState<ProfessorReview[]>([]);
  const [traceComments, setTraceComments] = useState<TraceComment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reviewTab, setReviewTab] = useState<'rmp' | 'trace'>('rmp');
  const [sortBy, setSortBy] = useState('newest');
  const [courseFilter, setCourseFilter] = useState('__all__');
  const [visibleReviews, setVisibleReviews] = useState(10);

  // Review tabs pill state
  const [reviewPillStyle, setReviewPillStyle] = useState({ left: 0, width: 0, opacity: 0 });
  const [isReviewPillReady, setIsReviewPillReady] = useState(false);
  const reviewTabsRef = useRef<HTMLDivElement>(null);

  // TRACE specific states
  const [traceSearch, setTraceSearch] = useState('');
  const [traceSort, setTraceSort] = useState('popular');
  const [expandedQuestions, setExpandedQuestions] = useState<Record<string, boolean>>({});
  const [visibleCommentsPerQuestion, setVisibleCommentsPerQuestion] = useState<Record<string, number>>({});

  // Refs for scrolling back to specific questions
  const questionRefs = useRef<Record<string, HTMLDivElement | null>>({});

  /* ── back to top ── */
  useEffect(() => {
    const handler = () => setShowBackToTop(window.scrollY > 300);
    window.addEventListener('scroll', handler, { passive: true });
    return () => window.removeEventListener('scroll', handler);
  }, []);

  const updateReviewPill = useCallback(() => {
    if (!reviewTabsRef.current) return;
    const activeTab = reviewTabsRef.current.querySelector('.prof-review-tab.active') as HTMLElement;
    if (activeTab) {
      setReviewPillStyle({
        left: activeTab.offsetLeft,
        width: activeTab.offsetWidth,
        opacity: 1
      });
    }
  }, []);

  useLayoutEffect(() => {
    updateReviewPill();
  }, [reviewTab, updateReviewPill]);

  useEffect(() => {
    const container = reviewTabsRef.current;
    if (!container) return;

    updateReviewPill();
    const timer = setTimeout(() => setIsReviewPillReady(true), 150);

    const observer = new ResizeObserver(() => {
      setIsReviewPillReady(false);
      updateReviewPill();
      setTimeout(() => setIsReviewPillReady(true), 50);
    });

    observer.observe(container);
    return () => {
      clearTimeout(timer);
      observer.disconnect();
    };
  }, [updateReviewPill]);

  /* ── grade bars animate on scroll ── */
  useEffect(() => {
    const el = gradesRef.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setGradesAnimated(true); obs.disconnect(); } },
      { threshold: 0.3 },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [profile]);

  /* ── data loading ── */
  useEffect(() => {
    if (!slug) {
      setLoading(false);
      setError('Professor not found.');
      return;
    }
    let cancelled = false;
    async function load() {
      if (!slug) return;
      setLoading(true); setError('');
      try {
        const data = await fetchProfessorData(slug);
        if (cancelled) return;
        if (!data) { setError('Professor not found.'); }
        else { 
          setProfile(data); 
          setReviews(data.reviews || []); 
          setTraceComments(data.traceComments || []); 
          
          // Initial expanded state for the first few popular questions
          if (data.traceComments && data.traceComments.length > 0) {
            // We'll set this later after grouping
          }
        }
      } catch { if (!cancelled) setError('Failed to load professor data.'); }
      finally { if (!cancelled) setLoading(false); }
    }
    load();
    return () => { cancelled = true; };
  }, [slug]);

  useEffect(() => { setVisibleReviews(10); }, [sortBy, courseFilter, reviewTab]);

  const courseCodeMap = new Map<string, string>();
  profile?.traceCourses?.forEach((c) => {
    const codeMatch = c.displayName.match(/^([A-Z]+)(\d+)/i);
    if (codeMatch) {
      const fullCode = codeMatch[0].toUpperCase();
      const numberPart = codeMatch[2];
      courseCodeMap.set(fullCode, fullCode);
      if (!courseCodeMap.has(numberPart)) {
        courseCodeMap.set(numberPart, fullCode);
      }
    } else {
      const code = c.displayName.split(':')[0].split(' ')[0];
      if (code) {
        courseCodeMap.set(code.toUpperCase(), code.toUpperCase());
      }
    }
  });

  const getFormattedCourseCode = (courseInput: string) => {
    if (!courseInput) return courseInput;
    const cleanInput = courseInput.replace(/\s+/g, '').toUpperCase();
    
    if (courseCodeMap.has(cleanInput)) {
      return courseCodeMap.get(cleanInput)!;
    }
    
    const numMatch = cleanInput.match(/\d+/);
    if (numMatch) {
      const numberPart = numMatch[0];
      if (courseCodeMap.has(numberPart)) {
        return courseCodeMap.get(numberPart)!;
      }
    }
    
    return courseInput;
  };

  const uniqueCourses = Array.from(new Set(reviews.map((r) => r.course).filter(Boolean)));
  const courseOptions = [courseFilterAll, ...uniqueCourses.map((c) => ({ value: c, label: getFormattedCourseCode(c) }))];

  const filteredReviews = reviews
    .filter((r) => courseFilter === '__all__' || r.course === courseFilter)
    .sort((a, b) => {
      switch (sortBy) {
        case 'oldest': return new Date(a.date).getTime() - new Date(b.date).getTime();
        case 'highest': return b.quality - a.quality;
        case 'lowest': return a.quality - b.quality;
        default: return new Date(b.date).getTime() - new Date(a.date).getTime();
      }
    });

  // Group TRACE comments by question
  const groupedTrace = useMemo(() => {
    const groups: Record<string, TraceComment[]> = {};
    traceComments.forEach(comment => {
      if (!groups[comment.question]) {
        groups[comment.question] = [];
      }
      groups[comment.question].push(comment);
    });

    // Helper to check if a comment is detailed for sorting
    const checkDetailed = (text: string) => text.length > 150 || (text.split(' ').length > 25 && /[.!?]/.test(text));

    return Object.entries(groups)
      .map(([question, comments]) => {
        // Find most recent termId for this question
        const maxTermId = Math.max(...comments.map(c => c.termId || 0));
        
        return {
          question,
          maxTermId,
          // Sort comments: 
          // If 'newest' sort is active, newest termId first
          // Otherwise detailed ones first
          comments: [...comments].sort((a, b) => {
            if (traceSort === 'newest') {
              return (b.termId || 0) - (a.termId || 0);
            }
            const aDet = checkDetailed(a.comment);
            const bDet = checkDetailed(b.comment);
            if (aDet && !bDet) return -1;
            if (!aDet && bDet) return 1;
            return 0;
          }),
          count: comments.length
        };
      })
      .filter(group => {
        if (!traceSearch) return true;
        const searchLower = traceSearch.toLowerCase();
        return group.question.toLowerCase().includes(searchLower) || 
               group.comments.some(c => c.comment.toLowerCase().includes(searchLower));
      })
      .sort((a, b) => {
        // Boost matches in the question title
        if (traceSearch) {
          const aTitleMatch = a.question.toLowerCase().includes(traceSearch.toLowerCase());
          const bTitleMatch = b.question.toLowerCase().includes(traceSearch.toLowerCase());
          if (aTitleMatch && !bTitleMatch) return -1;
          if (!aTitleMatch && bTitleMatch) return 1;
        }

        switch (traceSort) {
          case 'newest': return b.maxTermId - a.maxTermId;
          case 'popular': return b.count - a.count;
          case 'alphabetical': return a.question.localeCompare(b.question);
          default: return 0;
        }
      });
  }, [traceComments, traceSearch, traceSort]);

  const toggleQuestion = (question: string) => {
    setExpandedQuestions(prev => ({
      ...prev,
      [question]: !prev[question]
    }));
    
    if (!visibleCommentsPerQuestion[question]) {
      setVisibleCommentsPerQuestion(prev => ({
        ...prev,
        [question]: 5
      }));
    }
  };

  const showMoreComments = (e: React.MouseEvent, question: string) => {
    e.stopPropagation();
    setVisibleCommentsPerQuestion(prev => ({
      ...prev,
      [question]: (prev[question] || 5) + 10
    }));
  };

  const ratingDistribution = [5,4,3,2,1].map((star) => ({
    star, count: reviews.filter((r) => r.quality === star).length,
  }));
  const maxCount = Math.max(...ratingDistribution.map((d) => d.count), 1);

  const gradeDistribution = (() => {
    const counts: Record<string, number> = {};
    reviews.forEach((r) => {
      const g = r.grade?.trim();
      if (g && g !== 'N/A' && g !== 'Not sure yet' && g !== 'Rather not say') {
        counts[g] = (counts[g] || 0) + 1;
      }
    });
    const total = Object.values(counts).reduce((a, b) => a + b, 0);
    if (total === 0) return [];
    return GRADE_ORDER
      .filter((g) => counts[g])
      .map((g) => ({ grade: g, count: counts[g], pct: (counts[g] / total) * 100, color: GRADE_COLORS[g] || '#999' }));
  })();

  const scrollToReviews = () => {
    reviewsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  if (loading) return (
    <div className="prof-page">
      <div className="prof-loading">
<div className="prof-loading-spinner" /><p>Loading professor data…</p></div>
      <ThemeToggle />
    </div>
  );

  if (error || !profile) return <NotFound />;

  const compareSlug = profile.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

  return (
    <div className="prof-page">
      {/* ════════ HERO ════════ */}
      <header className="prof-hero">
        <div className="prof-hero-bg" style={{ backgroundImage: `url(${neuIcon})` }} />
        <div className="prof-hero-glow" />
        <div className="prof-hero-inner">
          <div className="prof-avatar">
            <span>{profile.name.split(' ').map((n) => n[0]).join('')}</span>
          </div>
          <div className="prof-hero-info">
            <h1 className="prof-name">{profile.name}</h1>
            <p className="prof-dept">{profile.department}</p>
          </div>
        </div>
      </header>

      {/* ════════ STAT CARDS ════════ */}
      <section className="prof-stats">
        <div className="prof-stat-card prof-stat-clickable">
          <span className="prof-stat-value accent"><AnimatedNumber value={profile.avgRating} /></span>
          <span className="prof-stat-label" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            Overall Rating
            {(profile.rmpRating || profile.traceRating) && (
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.6 }}><circle cx="12" cy="12" r="10"></circle><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
            )}
          </span>
          <StarRating rating={profile.avgRating ?? 0} size="lg" />
          {(profile.rmpRating || profile.traceRating) && (
            <div className="prof-stat-breakdown">
              {profile.rmpRating && <span>RMP: {profile.rmpRating.toFixed(2)}</span>}
              {profile.traceRating && <span>TRACE: {profile.traceRating.toFixed(2)}</span>}
            </div>
          )}
        </div>
        <div className="prof-stat-card">
          <span className="prof-stat-value"><AnimatedNumber value={profile.difficulty} /></span>
          <span className="prof-stat-label">Difficulty</span>
          <div className="prof-difficulty-bar"><div className="prof-difficulty-fill" style={{ width: `${((profile.difficulty ?? 0) / 5) * 100}%` }} /></div>
        </div>
        <div className="prof-stat-card">
          <span className="prof-stat-value green">{profile.wouldTakeAgainPct !== null ? <AnimatedNumber value={profile.wouldTakeAgainPct} decimals={0} suffix="%" /> : '—'}</span>
          <span className="prof-stat-label">Would Take Again</span>
        </div>
        <div className="prof-stat-card prof-stat-clickable" onClick={scrollToReviews} title="Jump to reviews">
          <span className="prof-stat-value">{profile.totalRatings.toLocaleString()}</span>
          <span className="prof-stat-label">Total Ratings</span>
          <span className="prof-stat-hint">Click to view ↓</span>
        </div>
      </section>

      {/* ════════ HERO ACTIONS ════════ */}
      <div className="prof-hero-actions-row">
        <Link to={`/compare?prof=${compareSlug}`} className="prof-compare-btn">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
          Compare
        </Link>
        {profile.professorUrl && (
          <a href={profile.professorUrl} target="_blank" rel="noreferrer" className="prof-rmp-btn">
            View on RMP →
          </a>
        )}
      </div>

      {/* ════════ CHARTS ROW ════════ */}
      <section className="prof-section prof-charts-row">
        <div className="prof-chart-card">
          <h3 className="prof-chart-title">Rating Distribution</h3>
          <div className="prof-distribution">
            {ratingDistribution.map((d) => (
              <RatingBar key={d.star} star={d.star} count={d.count} max={maxCount} />
            ))}
          </div>
        </div>
        {gradeDistribution.length > 0 && (
          <div className="prof-chart-card" ref={gradesRef}>
            <h3 className="prof-chart-title">Grade Distribution</h3>
            <div className="prof-grades">
              {gradeDistribution.map((g) => (
                <div key={g.grade} className="prof-grade-row">
                  <span className="prof-grade-label" style={{ color: g.color }}>{g.grade}</span>
                  <div className="prof-grade-track">
                    <div className="prof-grade-fill" style={{ width: gradesAnimated ? `${g.pct}%` : '0%', background: g.color }} />
                  </div>
                  <span className="prof-grade-count">{g.count}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* ════════ COURSES ════════ */}
      {profile.traceCourses && profile.traceCourses.length > 0 && (() => {
        // Strictly extract "Season Year" from messy term titles
        const cleanTerm = (t: string): string => {
          // Extract the season keyword
          const seasonMatch = t.match(/(Spring|Fall|Summer|Winter)/i);
          if (!seasonMatch) return t.trim();
          const season = seasonMatch[1].charAt(0).toUpperCase() + seasonMatch[1].slice(1).toLowerCase();
          // Extract the first valid 4-digit year (2000-2099)
          const yearMatch = t.match(/\b(20\d{2})\b/);
          if (!yearMatch) return season;
          return `${season} ${yearMatch[1]}`;
        };

        // Extract course code: handle both "SCHM2301:02 (...)" and "SCHM2301 (...)" formats
        const extractCode = (displayName: string): string => {
          const match = displayName.match(/^([A-Z]+\d+)/);
          return match ? match[1] : displayName.split(':')[0].split(' ')[0];
        };

        const grouped = new Map<string, typeof profile.traceCourses>();
        profile.traceCourses.forEach((c) => {
          const code = extractCode(c.displayName);
          if (!grouped.has(code)) grouped.set(code, []);
          grouped.get(code)!.push(c);
        });
        return (
          <section className="prof-section">
            <h2 className="prof-section-title">Courses Taught</h2>
            <div className="prof-courses-compact">
              {Array.from(grouped.entries()).map(([code, sections]) => {
                const nameMatch = sections[0].displayName.match(/\((.+?)\)/);
                const courseName = nameMatch ? nameMatch[1] : '';
                const terms = [...new Set(sections.map((s) => cleanTerm(s.termTitle)))]
                  .filter((t) => /\b20\d{2}\b/.test(t))
                  .sort((a, b) => {
                  // Sort by year descending, then season
                  const yearA = parseInt(a.match(/\d{4}/)?.[0] || '0');
                  const yearB = parseInt(b.match(/\d{4}/)?.[0] || '0');
                  if (yearA !== yearB) return yearB - yearA;
                  const order: Record<string, number> = { Spring: 1, Summer: 2, Fall: 3, Winter: 4 };
                  return (order[b.split(' ')[0]] || 0) - (order[a.split(' ')[0]] || 0);
                });
                return (
                  <div key={code} className="prof-course-row">
                    <div className="prof-course-row-main">
                      <span className="prof-course-code">{code}</span>
                      <span className="prof-course-title">{courseName}</span>
                      <span className="prof-course-terms">{sections.length} section{sections.length > 1 ? 's' : ''}</span>
                    </div>
                    <div className="prof-course-term-tags">
                      {terms.map((t) => (<span key={t} className="prof-course-term-tag">{t}</span>))}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        );
      })()}

      {/* ════════ REVIEWS ════════ */}
      <section className="prof-section prof-reviews-section" ref={reviewsRef}>
        <div className="prof-reviews-header">
          <h2 className="prof-section-title">Reviews</h2>
          <div className="prof-review-tabs" ref={reviewTabsRef}>
            <div 
              className={`prof-review-pill-background ${isReviewPillReady ? 'animate' : ''}`}
              style={{
                transform: `translateX(${reviewPillStyle.left}px)`,
                width: `${reviewPillStyle.width}px`,
                opacity: reviewPillStyle.opacity,
                visibility: reviewPillStyle.opacity === 0 ? 'hidden' : 'visible'
              }}
            />
            <button className={`prof-review-tab ${reviewTab === 'rmp' ? 'active' : ''}`} onClick={() => setReviewTab('rmp')}>
              RateMyProfessor ({reviews.length})
            </button>
            <button className={`prof-review-tab ${reviewTab === 'trace' ? 'active' : ''}`} onClick={() => setReviewTab('trace')}>
              TRACE ({traceComments.length})
            </button>
          </div>
        </div>

        {reviewTab === 'rmp' && (<>
          <div className="prof-reviews-filters">
            <Dropdown className="feedback-dropdown" options={sortOptions} value={sortBy} onChange={setSortBy} placeholder="Sort by…" />
            {uniqueCourses.length > 1 && (
              <Dropdown className="feedback-dropdown" options={courseOptions} value={courseFilter} onChange={setCourseFilter} placeholder="Filter by course" />
            )}
          </div>
          <div className="prof-reviews-list">
            {filteredReviews.length === 0 ? <p className="prof-no-reviews">No reviews match the current filters.</p> : (
              filteredReviews.slice(0, visibleReviews).map((r, i) => (
                <div key={i} className="prof-review-card" style={{ animationDelay: `${(i % 10) * 0.04}s`, borderLeftColor: r.quality >= 4 ? '#27ae60' : r.quality >= 3 ? '#f39c12' : '#e74c3c' }}>
                  <div className="prof-review-top">
                    <div className="prof-review-ratings">
                      <div className="prof-review-rating-item">
                        <span className="prof-review-rating-label">Quality</span>
                        <span className="prof-review-rating-value" data-score={r.quality >= 4 ? 'high' : r.quality >= 3 ? 'mid' : 'low'}>{r.quality}</span>
                      </div>
                      <div className="prof-review-rating-item">
                        <span className="prof-review-rating-label">Difficulty</span>
                        <span className="prof-review-rating-value" data-score={r.difficulty <= 2 ? 'high' : r.difficulty <= 3 ? 'mid' : 'low'}>{r.difficulty}</span>
                      </div>
                    </div>
                    <div className="prof-review-meta">
                      {r.course && <span className="prof-review-course">{getFormattedCourseCode(r.course)}</span>}
                      <span className="prof-review-date">{(() => { const d = new Date(r.date); return isNaN(d.getTime()) ? r.date : d.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' }); })()}</span>
                    </div>
                  </div>
                  {r.comment && <p className="prof-review-comment">{r.comment}</p>}
                  <div className="prof-review-bottom">
                    {r.tags && (<div className="prof-review-tags">{r.tags.split('--').map((t: string) => t.trim()).filter(Boolean).map((tag: string, ti: number) => (
                      <span key={ti} className="prof-review-tag">{tag}</span>
                    ))}</div>)}
                    <div className="prof-review-pills">
                      {r.grade && r.grade !== 'N/A' && <span className="prof-review-pill">Grade: {r.grade}</span>}
                      {r.attendance && r.attendance !== 'N/A' && <span className="prof-review-pill">Attendance: {r.attendance === 'true' || r.attendance === 'Mandatory' ? 'Mandatory' : 'Not Mandatory'}</span>}
                      {r.textbook && r.textbook !== 'N/A' && <span className="prof-review-pill">Textbook: {r.textbook === 'true' || r.textbook === 'Yes' ? 'Yes' : 'No'}</span>}
                      {r.online_class && r.online_class !== 'N/A' && <span className="prof-review-pill">{r.online_class === 'true' || r.online_class === 'Yes' ? 'Online' : 'In-Person'}</span>}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
          {visibleReviews < filteredReviews.length && (
            <button className="prof-load-more" onClick={() => setVisibleReviews((v) => v + 10)}>
              Load More Reviews ({filteredReviews.length - visibleReviews} remaining)
            </button>
          )}
        </>)}

        {reviewTab === 'trace' && (
          <div className="prof-trace-container">
            <div className="prof-trace-controls">
              <div className="trace-search-container">
                <span className="trace-search-icon">
                  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                </span>
                <input 
                  type="text" 
                  className="trace-search-input" 
                  placeholder="Search questions or keywords..." 
                  value={traceSearch}
                  onChange={(e) => setTraceSearch(e.target.value)}
                />
              </div>
              <Dropdown 
                className="trace-sort-dropdown"
                options={traceSortOptions}
                value={traceSort}
                onChange={setTraceSort}
              />
            </div>

            <div className="prof-trace-categories">
              {groupedTrace.length === 0 ? (
                <p className="prof-no-reviews">No TRACE questions found matching your search.</p>
              ) : (
                groupedTrace.map((group) => {
                  const isExpanded = expandedQuestions[group.question];
                  const visibleCount = visibleCommentsPerQuestion[group.question] || 5;
                  
                  return (
                    <div 
                      key={group.question} 
                      className={`trace-category-item ${isExpanded ? 'expanded' : ''}`}
                      ref={el => { questionRefs.current[group.question] = el; }}
                    >
                      <div className="trace-category-header" onClick={() => toggleQuestion(group.question)}>
                        <div className="trace-category-title-wrap">
                          <h4 className="trace-category-title">{group.question}</h4>
                          <div className="trace-category-subtitle">
                            <span className="trace-comment-count">{group.count} comment{group.count !== 1 ? 's' : ''}</span>
                          </div>
                        </div>
                        <svg className="trace-chevron" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
                      </div>
                      
                      {isExpanded && (
                        <div className="trace-category-content">
                          {group.comments.slice(0, visibleCount).map((c, ci) => (
                            <div key={ci} className="trace-comment-bubble">
                              {c.comment}
                            </div>
                          ))}
                          
                          <div className="trace-category-actions">
                            {visibleCount < group.count && (
                              <button 
                                className="trace-action-btn primary"
                                onClick={(e) => showMoreComments(e, group.question)}
                              >
                                Show More ({group.count - visibleCount} left)
                              </button>
                            )}
                            
                            {visibleCount > 5 && (
                              <button 
                                className="trace-action-btn"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setVisibleCommentsPerQuestion(prev => ({ ...prev, [group.question]: 5 }));
                                  questionRefs.current[group.question]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                                }}
                              >
                                Show Less
                              </button>
                            )}

                            <button 
                              className="trace-action-btn"
                              onClick={(e) => {
                                e.stopPropagation();
                                toggleQuestion(group.question);
                                questionRefs.current[group.question]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                              }}
                            >
                              Collapse Question
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>
        )}
      </section>

      <Footer />
      <FeedbackTab />
      <ThemeToggle />

      {/* ════════ BACK TO TOP ════════ */}
      <button
        className={`prof-back-to-top ${showBackToTop ? 'visible' : ''}`}
        onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
        aria-label="Back to top"
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="18 15 12 9 6 15" />
        </svg>
      </button>
    </div>
  );
};

export default Professor;