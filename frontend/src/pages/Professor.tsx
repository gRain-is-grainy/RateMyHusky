import { useState, useEffect, useRef, useCallback, useMemo, useLayoutEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import Footer from '../components/Footer';
import NotFound from './NotFound';
import ThemeToggle from '../components/ThemeToggle';
import Dropdown from '../components/Dropdown';
import StarRating from '../components/StarRating';
import RatingBar from '../components/RatingBar';
import { fetchProfessorData } from '../api/api';
import type { ProfessorProfile, ProfessorReview, TraceComment } from '../api/api';
import { useAuth } from '../context/AuthContext';
import SignInModal from '../components/SignInModal';
import neuIcon from '../assets/neu-circle-icon.png';
import './Professor.css';

/* ───────── animated number counter ───────── */
const AnimatedNumber = ({
  value, decimals = 2, suffix = '',
}: { value: number | null; decimals?: number; suffix?: string }) => {
  const [display, setDisplay] = useState(value === null ? '—' : '0' + suffix);
  const hasAnimated = useRef(false);
  const prevValue = useRef<number | null>(null);
  const ref = useRef<HTMLSpanElement>(null);

  const animate = useCallback((from: number, to: number) => {
    const duration = 1000;
    const start = performance.now();
    const step = (now: number) => {
      const t = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      const current = from + (to - from) * eased;
      setDisplay(current.toFixed(decimals) + suffix);
      if (t < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }, [decimals, suffix]);

  useEffect(() => {
    if (value === null) {
      prevValue.current = null;
      return;
    }
    if (!hasAnimated.current) return;
    if (prevValue.current !== value) {
      animate(prevValue.current || 0, value);
      prevValue.current = value;
    }
  }, [value, animate]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(([e]) => { 
      if (e.isIntersecting && !hasAnimated.current && value !== null) { 
        hasAnimated.current = true;
        animate(0, value);
        prevValue.current = value;
        obs.disconnect(); 
      } 
    }, { threshold: 0.5 });
    obs.observe(el);
    return () => obs.disconnect();
  }, [animate, value]);

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

// Strictly extract "Season Year" from messy term titles
const cleanTerm = (t: string): string => {
  const seasonMatch = t.match(/(Spring|Fall|Summer|Winter)/i);
  if (!seasonMatch) return t.trim();
  const season = seasonMatch[1].charAt(0).toUpperCase() + seasonMatch[1].slice(1).toLowerCase();
  // Try standard 4-digit year first (e.g. "Fall 2019")
  const yearMatch = t.match(/\b(20\d{2})\b/);
  if (yearMatch) return `${season} ${yearMatch[1]}`;
  // Fallback: extract year from 6-digit term codes like "202130" → "2021"
  const termCodeMatch = t.match(/(20\d{2})\d{2}/);
  if (termCodeMatch) return `${season} ${termCodeMatch[1]}`;
  return season;
};

const formatReviewDate = (dateStr: string) => {
  if (!dateStr) return '';
  // Convert "2022-12-11 18:36:58 +0000 UTC" to "2022-12-11T18:36:58Z"
  const normalized = dateStr.replace(' +0000 UTC', '').replace(' ', 'T') + 'Z';
  const date = new Date(normalized);
  if (isNaN(date.getTime())) return dateStr;
  return date.toLocaleDateString('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric'
  });
};

const GRADE_ORDER = ['A+','A','A-','B+','B','B-','C+','C','C-','D+','D','D-','F','W','WF','P','NP','I'];
const GRADE_COLORS: Record<string, string> = {
  'A+':'#1a9850','A':'#27ae60','A-':'#66bd63',
  'B+':'#a6d96a','B':'#d4e858','B-':'#fee08b',
  'C+':'#fdae61','C':'#f39c12','C-':'#e67e22',
  'D+':'#e74c3c','D':'#d73027','D-':'#c0392b',
  'F':'#a50026','W':'#7f8c8d','WF':'#636e72','P':'#2980b9','NP':'#8e44ad','I':'#999',
};

/* ───────── near-duplicate detection ───────── */
function normalizeText(s: string): string {
  return s.toLowerCase().replace(/\s+/g, ' ').trim();
}

function deduplicateByText<T>(items: T[], getText: (item: T) => string): T[] {
  const seen = new Set<string>();
  const result: T[] = [];
  for (const item of items) {
    const raw = getText(item);
    if (!raw.trim()) { result.push(item); continue; }
    // Use a truncated normalized form as a fingerprint — catches exact and near-exact dupes
    const norm = normalizeText(raw);
    // Check exact match first
    if (seen.has(norm)) continue;
    // Check prefix-based match (catches 95%+ similar: same text with minor trailing differences)
    const prefix = norm.slice(0, Math.floor(norm.length * 0.9));
    let isDupe = false;
    for (const s of seen) {
      if (s.startsWith(prefix) || norm.startsWith(s.slice(0, Math.floor(s.length * 0.9)))) {
        // Confirm length similarity (within 10%)
        const ratio = Math.min(s.length, norm.length) / Math.max(s.length, norm.length);
        if (ratio >= 0.9) { isDupe = true; break; }
      }
    }
    if (!isDupe) {
      seen.add(norm);
      result.push(item);
    }
  }
  return result;
}

/* ═══════════════════════════════════════ */
const Professor = () => {
  const { slug } = useParams<{ slug: string }>();
  const { user } = useAuth();
  const [showSignIn, setShowSignIn] = useState(false);
  const reviewsRef = useRef<HTMLElement>(null);
  const chartsRef = useRef<HTMLElement>(null);
  const gradesRef = useRef<HTMLDivElement>(null);
  const reviewTabsRef = useRef<HTMLDivElement>(null);
  const questionRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const [profile, setProfile] = useState<ProfessorProfile | null>(null);
  const [reviews, setReviews] = useState<ProfessorReview[]>([]);
  const [traceComments, setTraceComments] = useState<TraceComment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reviewTab, setReviewTab] = useState<'rmp' | 'trace'>('rmp');
  const [sortBy, setSortBy] = useState('newest');
  const [visibleReviews, setVisibleReviews] = useState(10);
  const [selectedCourses, setSelectedCourses] = useState<Set<string>>(new Set());
  const [showBackToTop, setShowBackToTop] = useState(false);
  const [gradesAnimated, setGradesAnimated] = useState(false);
  const [reviewPillStyle, setReviewPillStyle] = useState({ left: 0, width: 0, opacity: 0 });
  const [isReviewPillReady, setIsReviewPillReady] = useState(false);
  const [traceSearch, setTraceSearch] = useState('');
  const [traceSort, setTraceSort] = useState('popular');
  const [expandedQuestions, setExpandedQuestions] = useState<Record<string, boolean>>({});
  const [visibleCommentsPerQuestion, setVisibleCommentsPerQuestion] = useState<Record<string, number>>({});

  /* ── review pill ── */
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
    if (!loading) {
      updateReviewPill();
    }
  }, [reviewTab, updateReviewPill, loading]);

  useEffect(() => {
    const container = reviewTabsRef.current;
    if (!container || loading) return;

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
  }, [updateReviewPill, loading]);

  /* ── data loading ── */
  useEffect(() => {
    if (!slug) {
      setLoading(false);
      setError('Professor not found.');
      return;
    }
    let cancelled = false;
    async function load() {
      setLoading(true); setError('');
      try {
        const data = await fetchProfessorData(slug!);
        if (cancelled) return;
        if (!data) {
          setError('Professor not found.');
        } else { 
          setProfile(data); 
          setReviews(data.reviews || []); 
          setTraceComments(data.traceComments || []); 
        }
      } catch { if (!cancelled) setError('Failed to load professor data.'); }
      finally { if (!cancelled) setLoading(false); }
    }
    load();
    return () => { cancelled = true; };
  }, [slug]);

  /* ── back to top ── */
  useEffect(() => {
    const handler = () => setShowBackToTop(window.scrollY > 300);
    window.addEventListener('scroll', handler, { passive: true });
    return () => window.removeEventListener('scroll', handler);
  }, []);

  /* ── logic ── */
  const courseCodeMap = useMemo(() => {
    const map = new Map<string, string>();
    profile?.traceCourses?.forEach((c) => {
      const codeMatch = c.displayName.match(/^([A-Z]+)(\d+)/i);
      if (codeMatch) {
        const fullCode = codeMatch[0].toUpperCase();
        map.set(fullCode, fullCode);
        map.set(codeMatch[2], fullCode);
      } else {
        const code = c.displayName.split(':')[0].split(' ')[0].toUpperCase();
        if (code) map.set(code, code);
      }
    });
    return map;
  }, [profile]);

  const getFormattedCourseCode = useCallback((input: string) => {
    if (!input) return '';
    const clean = input.replace(/\s+/g, '').toUpperCase();
    if (courseCodeMap.has(clean)) return courseCodeMap.get(clean)!;
    const match = clean.match(/\d+/);
    if (match && courseCodeMap.has(match[0])) return courseCodeMap.get(match[0])!;
    return clean;
  }, [courseCodeMap]);

  const allCourseCodes = useMemo(() => {
    const codes = new Set<string>();
    profile?.traceCourses?.forEach(c => {
      const m = c.displayName.match(/^([A-Z]+\d+)/);
      const code = (m ? m[1] : c.displayName.split(':')[0].split(' ')[0]).toUpperCase();
      if (code) codes.add(code);
    });
    reviews.forEach(r => {
      const code = getFormattedCourseCode(r.course);
      if (code) codes.add(code.toUpperCase());
    });
    return Array.from(codes).sort();
  }, [profile, reviews, getFormattedCourseCode]);

  const hasInitializedSelection = useRef(false);
  useEffect(() => {
    if (allCourseCodes.length > 0 && !hasInitializedSelection.current) {
      setSelectedCourses(new Set(allCourseCodes));
      hasInitializedSelection.current = true;
    }
  }, [allCourseCodes]);

  const filteredRmpReviews = useMemo(() => {
    const filtered = reviews.filter(r => selectedCourses.has(getFormattedCourseCode(r.course).toUpperCase()));
    return deduplicateByText(filtered, r => r.comment);
  }, [reviews, selectedCourses, getFormattedCourseCode]);

  const filteredTraceCourses = useMemo(() => {
    return (profile?.traceCourses || []).filter(c => {
      const m = c.displayName.match(/^([A-Z]+\d+)/);
      const code = (m ? m[1] : c.displayName.split(':')[0].split(' ')[0]).toUpperCase();
      return selectedCourses.has(code);
    });
  }, [profile, selectedCourses]);

  const stats = useMemo(() => {
    if (!profile) return null;

    const allSelected = allCourseCodes.length > 0 && selectedCourses.size === allCourseCodes.length;

    const rmpRating = filteredRmpReviews.length > 0
      ? filteredRmpReviews.reduce((acc, r) => acc + r.quality, 0) / filteredRmpReviews.length
      : null;
    
    let traceSum = 0, traceWeight = 0;
    filteredTraceCourses.forEach(c => {
      const overall = c.scores.find(s => {
        const q = s.question.toLowerCase().replace(/\s+/g, ' ');
        return q === 'overall rating of teaching' || q.includes('overall rating') || q.includes('overall');
      });
      if (overall) {
        const weight = overall.totalResponses ?? overall.completed;
        if (weight > 0) {
          traceSum += overall.mean * weight;
          traceWeight += weight;
        }
      }
    });

    const traceRating = traceWeight > 0 ? traceSum / traceWeight : null;

    let avgRating = 0;
    if (rmpRating !== null && traceRating !== null) {
      avgRating = (rmpRating + traceRating) / 2;
    } else if (rmpRating !== null) {
      avgRating = rmpRating;
    } else if (traceRating !== null) {
      avgRating = traceRating;
    }

    if (allSelected) {
      return {
        avgRating: profile.avgRating,
        rmpRating: profile.rmpRating,
        traceRating: profile.traceRating,
        difficulty: profile.difficulty ?? 0,
        totalRatings: profile.totalRatings,
        wouldTakeAgainPct: profile.wouldTakeAgainPct,
      };
    }

    return {
      avgRating,
      rmpRating,
      traceRating,
      difficulty: filteredRmpReviews.length > 0
        ? filteredRmpReviews.reduce((acc, r) => acc + r.difficulty, 0) / filteredRmpReviews.length
        : 0,
      totalRatings: filteredRmpReviews.length + traceWeight,
      wouldTakeAgainPct: profile.wouldTakeAgainPct,
    };
  }, [profile, filteredRmpReviews, filteredTraceCourses, allCourseCodes, selectedCourses]);

  const ratingDistribution = useMemo(() => {
    const counts = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 };

    // RMP
    filteredRmpReviews.forEach(r => {
      if (r.quality >= 1 && r.quality <= 5) {
        const q = Math.round(r.quality) as 1 | 2 | 3 | 4 | 5;
        counts[q]++;
      }
    });

    // TRACE
    filteredTraceCourses.forEach(c => {
      const overall = c.scores.find(s => {
        const q = s.question.toLowerCase().replace(/\s+/g, ' ');
        return q === 'overall rating of teaching' || q.includes('overall rating') || q.includes('overall');
      });
      if (overall) {
        counts[1] += overall.count1 ?? 0;
        counts[2] += overall.count2 ?? 0;
        counts[3] += overall.count3 ?? 0;
        counts[4] += overall.count4 ?? 0;
        counts[5] += overall.count5 ?? 0;
      }
    });

    return [5, 4, 3, 2, 1].map(star => ({
      star,
      count: counts[star as 1 | 2 | 3 | 4 | 5],
    }));
  }, [filteredRmpReviews, filteredTraceCourses]);

  const maxCount = useMemo(() => Math.max(...ratingDistribution.map(d => d.count), 1), [ratingDistribution]);

  const gradeDistribution = useMemo(() => {
    const counts: Record<string, number> = {};
    filteredRmpReviews.forEach(r => {
      const g = r.grade?.trim();
      if (g && g !== 'N/A' && g !== 'Not sure yet' && g !== 'Rather not say') {
        counts[g] = (counts[g] || 0) + 1;
      }
    });
    const total = Object.values(counts).reduce((a, b) => a + b, 0);
    if (total === 0) return [];
    return GRADE_ORDER.filter(g => counts[g]).map(g => ({
      grade: g,
      count: counts[g],
      pct: (counts[g] / total) * 100,
      color: GRADE_COLORS[g] || '#999'
    }));
  }, [filteredRmpReviews]);

  useEffect(() => {
    const el = gradesRef.current;
    if (!el) return;
    const obs = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) {
        setGradesAnimated(true);
        obs.disconnect();
      }
    }, { threshold: 0.3 });
    obs.observe(el);
    return () => obs.disconnect();
  }, [profile, gradeDistribution.length]);

  const sortedReviews = useMemo(() => {
    return [...filteredRmpReviews].sort((a, b) => {
      if (sortBy === 'oldest') return new Date(a.date).getTime() - new Date(b.date).getTime();
      if (sortBy === 'highest') return b.quality - a.quality;
      if (sortBy === 'lowest') return a.quality - b.quality;
      return new Date(b.date).getTime() - new Date(a.date).getTime();
    });
  }, [filteredRmpReviews, sortBy]);

  const termIdMap = useMemo(() => {
    const map = new Map<number, string>();
    profile?.traceCourses?.forEach(c => {
      if (!map.has(c.termId)) map.set(c.termId, c.termTitle);
    });
    return map;
  }, [profile]);

  // Map courseUrl → course code for TRACE comments
  const commentCourseMap = useMemo(() => {
    const map = new Map<string, string>();
    if (!profile?.traceCourses) return map;

    // Build courseId → code lookup
    const idToCode = new Map<number, string>();
    profile.traceCourses.forEach(c => {
      const m = c.displayName.match(/^([A-Z]+\d+)/i);
      const code = m ? m[1].toUpperCase() : '';
      if (code) idToCode.set(c.courseId, code);
    });

    // For each trace comment, extract courseId from URL and map to code
    traceComments.forEach(c => {
      if (c.courseUrl) {
        const spMatches = c.courseUrl.match(/sp=(\d+)/g);
        if (spMatches && spMatches.length >= 1) {
          const courseId = parseInt(spMatches[0].replace('sp=', ''));
          const code = idToCode.get(courseId);
          if (code) {
            map.set(c.courseUrl, code);
          }
        }
      }
    });

    return map;
  }, [profile, traceComments]);

  const groupedTrace = useMemo(() => {
    const groups: Record<string, TraceComment[]> = {};
    const ids = new Set(filteredTraceCourses.map(c => c.termId));
    traceComments.forEach(c => {
      if (ids.has(c.termId)) {
        if (!groups[c.question]) groups[c.question] = [];
        groups[c.question].push(c);
      }
    });
    // Deduplicate near-identical comments within each question group
    for (const q of Object.keys(groups)) {
      groups[q] = deduplicateByText(groups[q], c => c.comment);
    }
    const searchLower = traceSearch.toLowerCase();
    return Object.entries(groups).map(([q, cs]) => ({
      question: q,
      maxTermId: Math.max(...cs.map(c => c.termId || 0)),
      count: cs.length,
      comments: [...cs].sort((a, b) => {
        // If searching, boost comments containing the search term
        if (searchLower) {
          const aMatch = a.comment.toLowerCase().includes(searchLower);
          const bMatch = b.comment.toLowerCase().includes(searchLower);
          if (aMatch && !bMatch) return -1;
          if (!aMatch && bMatch) return 1;
        }
        if (traceSort === 'newest') return (b.termId || 0) - (a.termId || 0);
        return b.comment.length - a.comment.length;
      }),
    })).filter(g => 
      !traceSearch || 
      g.question.toLowerCase().includes(searchLower) ||
      g.comments.some(c => c.comment.toLowerCase().includes(searchLower))
    ).sort((a, b) => {
      if (traceSearch) {
        const aM = a.question.toLowerCase().includes(searchLower);
        const bM = b.question.toLowerCase().includes(searchLower);
        if (aM && !bM) return -1;
        if (!aM && bM) return 1;
      }
      if (traceSort === 'newest') return b.maxTermId - a.maxTermId;
      if (traceSort === 'popular') return b.count - a.count;
      return a.question.localeCompare(b.question);
    });
  }, [traceComments, traceSearch, traceSort, filteredTraceCourses]);

  const toggleCourse = (code: string) => {
    setSelectedCourses(prev => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  };

  const toggleQuestion = (q: string) => {
    const wasExpanded = expandedQuestions[q];
    setExpandedQuestions(p => ({ ...p, [q]: !wasExpanded }));
    // Always reset to 5 when opening (or reopening)
    if (!wasExpanded) {
      setVisibleCommentsPerQuestion(p => ({ ...p, [q]: 5 }));
    }
  };

  const showMoreComments = (e: React.MouseEvent, q: string) => {
    e.stopPropagation();
    setVisibleCommentsPerQuestion(p => ({ ...p, [q]: (p[q] || 5) + 10 }));
  };

  useEffect(() => { setVisibleReviews(10); }, [sortBy, reviewTab, selectedCourses.size]);

  if (loading) return (
    <div className="prof-page">
      <div className="prof-loading">
        <div className="prof-loading-spinner" />
        <p>Loading professor data…</p>
      </div>
      <ThemeToggle />
    </div>
  );

  if (error || !profile || !stats) return <NotFound />;

  return (
    <div className="prof-page">
      <header className="prof-hero">
        <div className="prof-hero-bg" style={{ backgroundImage: `url(${neuIcon})` }} />
        <div className="prof-hero-glow" />
        <div className="prof-hero-inner">
          <div className="prof-avatar">
            {profile.imageUrl ? (
              <img
                src={profile.imageUrl}
                alt={profile.name}
                className="prof-avatar-img"
                onError={(e) => {
                  const target = e.currentTarget;
                  target.style.display = 'none';
                  const initials = target.parentElement?.querySelector('.prof-avatar-initials') as HTMLElement;
                  if (initials) initials.style.display = 'flex';
                }}
              />
            ) : null}
            <span
              className="prof-avatar-initials"
              style={profile.imageUrl ? { display: 'none' } : undefined}
            >
              {profile.name.split(' ').map(n => n[0]).join('')}
            </span>
          </div>
          <div className="prof-hero-info">
            <h1 className="prof-name">{profile.name}</h1>
            <p className="prof-dept">{profile.department}</p>
          </div>
        </div>
      </header>

      <section className="prof-stats">
        <div className="prof-stat-card prof-stat-clickable">
          <span className="prof-stat-value"><AnimatedNumber value={stats.avgRating} /></span>
          <span className="prof-stat-label" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px' }}>
            Overall Rating
            {(stats.rmpRating !== null || stats.traceRating !== null) && (
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.6 }}><circle cx="12" cy="12" r="10"></circle><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
            )}
          </span>
          <StarRating rating={stats.avgRating ?? 0} size="lg" />
          {(stats.rmpRating !== null || stats.traceRating !== null) && (
            <div className="prof-stat-breakdown">
              {stats.rmpRating !== null && <span>RMP: {stats.rmpRating.toFixed(2)}</span>}
              {stats.traceRating !== null && <span>TRACE: {stats.traceRating.toFixed(2)}</span>}
            </div>
          )}
        </div>
        <div className="prof-stat-card">
          <span className="prof-stat-value"><AnimatedNumber value={stats.difficulty} /></span>
          <span className="prof-stat-label">Difficulty</span>
          <div className="prof-difficulty-bar">
            <div className="prof-difficulty-fill" style={{ 
              width: `${((stats.difficulty ?? 0) / 5) * 100}%`,
              background: (() => {
                const d = stats.difficulty ?? 0;
                if (d <= 1.5) return '#27ae60';
                if (d <= 2.5) return '#66bd63';
                if (d <= 3.0) return '#f39c12';
                if (d <= 3.5) return '#e67e22';
                if (d <= 4.0) return '#e74c3c';
                return '#c0392b';
              })()
            }} />
          </div>
        </div>
        <div className="prof-stat-card">
          <span className="prof-stat-value green">
            {stats.wouldTakeAgainPct !== null ? <AnimatedNumber value={stats.wouldTakeAgainPct} decimals={0} suffix="%" /> : '—'}
          </span>
          <span className="prof-stat-label">Would Take Again</span>
        </div>
        <div className="prof-stat-card prof-stat-clickable" onClick={() => chartsRef.current?.scrollIntoView({ behavior: 'smooth' })}>
          <span className="prof-stat-value">{stats.totalRatings.toLocaleString()}</span>
          <span className="prof-stat-label">Total Ratings</span>
          <span className="prof-stat-hint">View distribution ↓</span>
        </div>
        <div className="prof-stat-card prof-stat-clickable" onClick={() => reviewsRef.current?.scrollIntoView({ behavior: 'smooth' })}>
          <span className="prof-stat-value">{(filteredRmpReviews.length + groupedTrace.reduce((acc, g) => acc + g.count, 0)).toLocaleString()}</span>
          <span className="prof-stat-label">Total Comments</span>
          <span className="prof-stat-hint">Read reviews ↓</span>
        </div>
      </section>

      <div className="prof-hero-actions-row">
        <Link 
          to={`/compare?a=${profile.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')}`} 
          className="prof-compare-btn"
        >
          Compare
        </Link>
        {profile.professorUrl && (
          <a href={profile.professorUrl} target="_blank" rel="noreferrer" className="prof-rmp-btn">
            View on RMP →
          </a>
        )}
      </div>

      <section className="prof-section prof-charts-row" ref={chartsRef}>
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

      {allCourseCodes.length > 0 && (() => {
        const grouped = new Map<string, typeof profile.traceCourses>();
        profile.traceCourses?.forEach(c => {
          const match = c.displayName.match(/^([A-Z]+\d+)/);
          const code = (match ? match[1] : c.displayName.split(':')[0].split(' ')[0]).toUpperCase();
          if (!grouped.has(code)) grouped.set(code, []);
          grouped.get(code)!.push(c);
        });
        reviews.forEach(r => {
          const code = getFormattedCourseCode(r.course).toUpperCase();
          if (code && !grouped.has(code)) grouped.set(code, []);
        });
        const sorted = Array.from(grouped.entries()).sort(([a], [b]) => a.localeCompare(b));
        return (
          <section className="prof-section">
            <div className="prof-section-header">
              <h2 className="prof-section-title">Courses Taught</h2>
              <div className="prof-section-actions">
                <button className="prof-action-link" onClick={() => setSelectedCourses(new Set(allCourseCodes))}>Select All</button>
                <button className="prof-action-link" onClick={() => setSelectedCourses(new Set())}>Clear All</button>
              </div>
            </div>
            <div className="prof-courses-compact">
              {sorted.map(([code, sections]) => {
                const nameMatch = sections[0]?.displayName.match(/\((.+?)\)/);
                const courseName = nameMatch ? nameMatch[1] : '';
                const terms = [...new Set(sections.map(s => cleanTerm(s.termTitle)))].filter(t => /\b20\d{2}\b/.test(t)).sort((a, b) => {
                  const yA = parseInt(a.match(/\d{4}/)?.[0] || '0');
                  const yB = parseInt(b.match(/\d{4}/)?.[0] || '0');
                  if (yA !== yB) return yB - yA;
                  const order: Record<string, number> = { Spring: 1, Summer: 2, Fall: 3, Winter: 4 };
                  const seasonA = a.split(' ')[0];
                  const seasonB = b.split(' ')[0];
                  return (order[seasonB] || 0) - (order[seasonA] || 0);
                });
                const isSelected = selectedCourses.has(code);
                return (
                  <div 
                    key={code} 
                    className={`prof-course-row ${isSelected ? 'selected' : ''}`} 
                    onClick={() => toggleCourse(code)}
                  >
                    <div className="prof-course-row-main">
                      <span className="prof-course-code">{code}</span>
                      <span className="prof-course-title">{courseName || 'Course data from reviews'}</span>
                      <span className="prof-course-terms">
                        {sections.length > 0 ? `${sections.length} section${sections.length > 1 ? 's' : ''}` : 'RMP reviews only'}
                      </span>
                    </div>
                    {terms.length > 0 && (
                      <div className="prof-course-term-tags">
                        {terms.map(t => <span key={t} className="prof-course-term-tag">{t}</span>)}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </section>
        );
      })()}

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
              RateMyProfessor ({filteredRmpReviews.length})
            </button>
            <button className={`prof-review-tab ${reviewTab === 'trace' ? 'active' : ''}`} onClick={() => setReviewTab('trace')}>
              TRACE ({groupedTrace.reduce((acc, g) => acc + g.count, 0)})
            </button>
          </div>
        </div>

        {reviewTab === 'rmp' && (
          <>
            <div className="prof-reviews-filters">
              <Dropdown className="feedback-dropdown" options={sortOptions} value={sortBy} onChange={setSortBy} placeholder="Sort by…" />
            </div>
            <div className="prof-reviews-list">
              {sortedReviews.length === 0 ? (
                <p className="prof-no-reviews">No reviews match current filters.</p>
              ) : (
                sortedReviews.slice(0, visibleReviews).map((r, i) => (
                  <div key={i} className="prof-review-card" style={{ borderLeftColor: r.quality >= 4 ? '#27ae60' : r.quality >= 3 ? '#f39c12' : '#e74c3c' }}>
                    <div className="prof-review-top">
                      <div className="prof-review-ratings">
                        <div className="prof-review-rating-item">
                          <span className="prof-review-rating-label">Quality</span>
                          <span className="prof-review-rating-value" data-score={String(r.quality)}>{r.quality}</span>
                        </div>
                        <div className="prof-review-rating-item">
                          <span className="prof-review-rating-label">Difficulty</span>
                          <span className="prof-review-rating-value" data-score={String(6 - r.difficulty)}>{r.difficulty}</span>
                        </div>
                      </div>
                      <div className="prof-review-meta">
                        <span className="prof-review-course">{getFormattedCourseCode(r.course)}</span>
                        <span className="prof-review-date">{formatReviewDate(r.date)}</span>
                      </div>
                    </div>
                    {r.comment && <p className="prof-review-comment">{r.comment}</p>}
                    <div className="prof-review-bottom">
                      {r.tags && (
                        <div className="prof-review-tags">
                          {r.tags.split('--').map(t => t.trim()).filter(Boolean).map((t, ti) => (
                            <span key={ti} className="prof-review-tag">{t}</span>
                          ))}
                        </div>
                      )}
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
            {visibleReviews < sortedReviews.length && (
              <button className="prof-load-more" onClick={() => setVisibleReviews(v => v + 10)}>
                Load More
              </button>
            )}
          </>
        )}

        {reviewTab === 'trace' && (
          <div className="prof-trace-container">
            {user && (
              <div className="prof-trace-controls">
                <div className="trace-search-container">
                  <input
                    type="text"
                    className="trace-search-input"
                    placeholder="Search comments or questions..."
                    value={traceSearch}
                    onChange={e => setTraceSearch(e.target.value)}
                  />
                </div>
                <Dropdown className="trace-sort-dropdown" options={traceSortOptions} value={traceSort} onChange={setTraceSort} />
              </div>
            )}
            <div className="prof-trace-categories">
              {groupedTrace.map(g => {
                const isExpanded = expandedQuestions[g.question];
                const visibleCount = visibleCommentsPerQuestion[g.question] || 5;
                return (
                  <div key={g.question} className={`trace-category-item ${isExpanded ? 'expanded' : ''}`} ref={el => { questionRefs.current[g.question] = el; }}>
                    <div className="trace-category-header" onClick={() => toggleQuestion(g.question)}>
                      <div className="trace-category-title-wrap">
                        <h4 className="trace-category-title">{g.question}</h4>
                        <div className="trace-category-subtitle">
                          <span className="trace-comment-count">{g.count} comments</span>
                        </div>
                      </div>
                      <svg className="trace-chevron" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
                    </div>
                    {isExpanded && !user && (
                      <div className="trace-category-paywall">
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="paywall-lock-icon-sm">
                          <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                          <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                        </svg>
                        <p>Sign in with your <strong>husky.neu.edu</strong> account to read these comments.</p>
                        <button className="paywall-signin-btn small" onClick={(e) => { e.stopPropagation(); setShowSignIn(true); }}>Sign In</button>
                      </div>
                    )}
                    {isExpanded && user && (
                      <div className="trace-category-content">
                        {g.comments.slice(0, visibleCount).map((c, ci) => {
                          const termRaw = termIdMap.get(c.termId) || '';
                          const term = cleanTerm(termRaw);
                          const hasYear = /\b20\d{2}\b/.test(term);
                          return (
                          <div
                            key={ci}
                            className={`trace-comment-bubble ${c.courseUrl ? 'clickable' : ''}`}
                            onClick={() => c.courseUrl && window.open(c.courseUrl, '_blank')}
                            title={c.courseUrl ? "Click to view original TRACE report" : ""}
                          >
                            <div className="trace-comment-meta">
                              {hasYear && <span className="trace-comment-term">{term}</span>}
                              {(() => {
                                const courseCode = commentCourseMap.get(c.courseUrl || '') || commentCourseMap.get(String(c.termId)) || '';
                                return courseCode ? <span className="trace-comment-course">{courseCode}</span> : null;
                              })()}
                            </div>
                            {c.comment}
                          </div>
                          );
                        })}
                        <div className="trace-category-actions">
                          {visibleCount < g.count && (
                            <button className="trace-action-btn primary" onClick={e => showMoreComments(e, g.question)}>Show More ({g.count - visibleCount} left)</button>
                          )}
                          {visibleCount > 5 && (
                            <button className="trace-action-btn" onClick={e => { e.stopPropagation(); setVisibleCommentsPerQuestion(p => ({ ...p, [g.question]: 5 })); questionRefs.current[g.question]?.scrollIntoView({ behavior: 'smooth', block: 'center' }); }}>Show Less</button>
                          )}
                          <button className="trace-action-btn" onClick={e => { e.stopPropagation(); toggleQuestion(g.question); questionRefs.current[g.question]?.scrollIntoView({ behavior: 'smooth', block: 'center' }); }}>Collapse</button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </section>

      <Footer />
      <ThemeToggle />
      <SignInModal open={showSignIn} onClose={() => setShowSignIn(false)} />
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