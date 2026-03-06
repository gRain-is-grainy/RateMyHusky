import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import Footer from '../components/Footer';
import FeedbackTab from '../components/FeedbackTab';
import ThemeToggle from '../components/ThemeToggle';
import Dropdown from '../components/Dropdown';
import RatingBadge from '../components/RatingBadge';
import StarRating from '../components/StarRating';
import RatingBar from '../components/RatingBar';
import {
  fetchProfessorData,
} from '../api/api';
import type { ProfessorProfile, ProfessorReview, TraceComment, TraceCourseScore } from '../api/api';
import './Professor.css';

/* ───────── animated number counter ───────── */
const AnimatedNumber = ({
  value,
  decimals = 2,
  suffix = '',
}: {
  value: number | null;
  decimals?: number;
  suffix?: string;
}) => {
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
    const obs = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          animate();
          obs.disconnect();
        }
      },
      { threshold: 0.5 },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [animate]);

  return <span ref={ref}>{display}</span>;
};

/* ───────── review sort options ───────── */
const sortOptions = [
  { value: 'newest', label: 'Newest First' },
  { value: 'oldest', label: 'Oldest First' },
  { value: 'highest', label: 'Highest Rated' },
  { value: 'lowest', label: 'Lowest Rated' },
];

const courseFilterAll = { value: '__all__', label: 'All Courses' };

/* ───────── tag pill colours ───────── */
const tagColors: Record<string, string> = {
  'Tough Grader': '#e74c3c',
  'Get Ready To Read': '#8e44ad',
  'Participation Matters': '#2980b9',
  'Group Projects': '#16a085',
  'Amazing Lectures': '#27ae60',
  'Clear Grading Criteria': '#2ecc71',
  'Gives Good Feedback': '#1abc9c',
  'Inspirational': '#f39c12',
  'Lots Of Homework': '#e67e22',
  'Hilarious': '#f1c40f',
  "Caring": '#3498db',
  'Respected': '#9b59b6',
  'Lecture Heavy': '#34495e',
  'Test Heavy': '#c0392b',
  'Graded By Few Things': '#d35400',
  'Accessible Outside Class': '#0984e3',
  'Online Savvy': '#6c5ce7',
};

const getTagColor = (tag: string) => tagColors[tag] || '#888';

/* ═══════════════════════════════════════
   PROFESSOR PAGE
   ═══════════════════════════════════════ */
const Professor = () => {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();

  const [profile, setProfile] = useState<ProfessorProfile | null>(null);
  const [reviews, setReviews] = useState<ProfessorReview[]>([]);
  const [traceComments, setTraceComments] = useState<TraceComment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  /* review tab + filters */
  const [reviewTab, setReviewTab] = useState<'rmp' | 'trace'>('rmp');
  const [sortBy, setSortBy] = useState('newest');
  const [courseFilter, setCourseFilter] = useState('__all__');
  const [visibleReviews, setVisibleReviews] = useState(10);

  /* trace course expand */
  const [expandedCourse, setExpandedCourse] = useState<number | null>(null);

  /* ───── data loading ───── */
  useEffect(() => {
    if (!slug) return;
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError('');
      try {
        const data = await fetchProfessorData(slug as string);
        if (cancelled) return;
        if (!data) {
          setError('Professor not found.');
        } else {
          setProfile(data);
          setReviews(data.reviews || []);
          setTraceComments(data.traceComments || []);
        }
      } catch {
        if (!cancelled) setError('Failed to load professor data.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [slug]);

  /* reset visible count on filter change */
  useEffect(() => {
    setVisibleReviews(10);
  }, [sortBy, courseFilter, reviewTab]);

  /* ───── derived data ───── */
  const uniqueCourses = Array.from(new Set(reviews.map((r) => r.course).filter(Boolean)));
  const courseOptions = [courseFilterAll, ...uniqueCourses.map((c) => ({ value: c, label: c }))];

  const filteredReviews = reviews
    .filter((r) => courseFilter === '__all__' || r.course === courseFilter)
    .sort((a, b) => {
      switch (sortBy) {
        case 'oldest':
          return new Date(a.date).getTime() - new Date(b.date).getTime();
        case 'highest':
          return b.quality - a.quality;
        case 'lowest':
          return a.quality - b.quality;
        default:
          return new Date(b.date).getTime() - new Date(a.date).getTime();
      }
    });

  const ratingDistribution = [5, 4, 3, 2, 1].map((star) => ({
    star,
    count: reviews.filter((r) => r.quality === star).length,
  }));
  const maxCount = Math.max(...ratingDistribution.map((d) => d.count), 1);

  /* ───── loading / error states ───── */
  if (loading) {
    return (
      <div className="prof-page">
        <Navbar />
        <div className="prof-loading">
          <div className="prof-loading-spinner" />
          <p>Loading professor data…</p>
        </div>
        <ThemeToggle />
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="prof-page">
        <Navbar />
        <div className="prof-error">
          <span className="prof-error-icon">🔍</span>
          <h2>Professor Not Found</h2>
          <p>{error || "We couldn't find that professor."}</p>
          <button className="prof-back-btn" onClick={() => navigate('/')}>
            Back to Home
          </button>
        </div>
        <Footer />
        <ThemeToggle />
      </div>
    );
  }

  return (
    <div className="prof-page">
      <Navbar />

      {/* ════════ Hero ════════ */}
      <header className="prof-hero">
        <div className="prof-hero-inner">
          {/* avatar placeholder */}
          <div className="prof-avatar">
            <span>{profile.name.split(' ').map((n) => n[0]).join('')}</span>
          </div>

          <div className="prof-hero-info">
            <h1 className="prof-name">{profile.name}</h1>
            <p className="prof-dept">{profile.department}</p>

            <div className="prof-hero-badges">
              <RatingBadge label="Overall" value={profile.avgRating} size="lg" />
              <RatingBadge label="RMP" value={profile.rmpRating} size="md" />
              <RatingBadge label="TRACE" value={profile.traceRating} size="md" />
            </div>
          </div>
        </div>
      </header>

      {/* ════════ Stats Cards ════════ */}
      <section className="prof-stats">
        <div className="prof-stat-card">
          <span className="prof-stat-value accent">
            <AnimatedNumber value={profile.avgRating} />
          </span>
          <span className="prof-stat-label">Overall Rating</span>
          <StarRating rating={profile.avgRating ?? 0} />
        </div>

        <div className="prof-stat-card">
          <span className="prof-stat-value">
            <AnimatedNumber value={profile.difficulty} />
          </span>
          <span className="prof-stat-label">Difficulty</span>
          <div className="prof-difficulty-bar">
            <div
              className="prof-difficulty-fill"
              style={{ width: `${((profile.difficulty ?? 0) / 5) * 100}%` }}
            />
          </div>
        </div>

        <div className="prof-stat-card">
          <span className="prof-stat-value green">
            {profile.wouldTakeAgainPct !== null
              ? <AnimatedNumber value={profile.wouldTakeAgainPct} decimals={0} suffix="%" />
              : '—'}
          </span>
          <span className="prof-stat-label">Would Take Again</span>
        </div>

        <div className="prof-stat-card">
          <span className="prof-stat-value">
            {profile.totalRatings.toLocaleString()}
          </span>
          <span className="prof-stat-label">Total Ratings</span>
        </div>
      </section>

      {/* ════════ Rating Distribution ════════ */}
      <section className="prof-section">
        <h2 className="prof-section-title">Rating Distribution</h2>
        <div className="prof-distribution">
          {ratingDistribution.map((d) => (
            <RatingBar key={d.star} star={d.star} count={d.count} max={maxCount} />
          ))}
        </div>
      </section>

      {/* ════════ Courses (TRACE) ════════ */}
      {profile.traceCourses && profile.traceCourses.length > 0 && (
        <section className="prof-section">
          <h2 className="prof-section-title">Courses Taught</h2>
          <div className="prof-courses-grid">
            {profile.traceCourses.map((course, idx) => (
              <div
                key={`${course.courseId}-${course.termId}`}
                className={`prof-course-card ${expandedCourse === idx ? 'expanded' : ''}`}
                style={{ animationDelay: `${idx * 0.04}s` }}
                onClick={() => setExpandedCourse(expandedCourse === idx ? null : idx)}
              >
                <div className="prof-course-header">
                  <span className="prof-course-name">{course.displayName}</span>
                  <span className="prof-course-term">{course.termTitle}</span>
                </div>
                <div className="prof-course-meta">
                  <span className="prof-course-dept">{course.departmentName}</span>
                  <span className="prof-course-enrollment">
                    {course.enrollment} enrolled
                  </span>
                </div>
                {expandedCourse === idx && course.scores && course.scores.length > 0 && (
                  <div className="prof-course-scores">
                    {course.scores.map((s: TraceCourseScore, si: number) => (
                      <div key={si} className="prof-score-row">
                        <span className="prof-score-question">{s.question}</span>
                        <span className="prof-score-mean">{s.mean.toFixed(2)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ════════ Reviews ════════ */}
      <section className="prof-section prof-reviews-section">
        <div className="prof-reviews-header">
          <h2 className="prof-section-title">Reviews</h2>

          <div className="prof-review-tabs">
            <button
              className={`prof-review-tab ${reviewTab === 'rmp' ? 'active' : ''}`}
              onClick={() => setReviewTab('rmp')}
            >
              RateMyProfessor ({reviews.length})
            </button>
            <button
              className={`prof-review-tab ${reviewTab === 'trace' ? 'active' : ''}`}
              onClick={() => setReviewTab('trace')}
            >
              TRACE ({traceComments.length})
            </button>
          </div>
        </div>

        {/* ── RMP reviews ── */}
        {reviewTab === 'rmp' && (
          <>
            <div className="prof-reviews-filters">
              <Dropdown
                className="feedback-dropdown"
                options={sortOptions}
                value={sortBy}
                onChange={setSortBy}
                placeholder="Sort by…"
              />
              {uniqueCourses.length > 1 && (
                <Dropdown
                  className="feedback-dropdown"
                  options={courseOptions}
                  value={courseFilter}
                  onChange={setCourseFilter}
                  placeholder="Filter by course"
                />
              )}
            </div>

            <div className="prof-reviews-list">
              {filteredReviews.length === 0 ? (
                <p className="prof-no-reviews">No reviews match the current filters.</p>
              ) : (
                filteredReviews.slice(0, visibleReviews).map((r, i) => (
                  <div
                    key={i}
                    className="prof-review-card"
                    style={{ animationDelay: `${(i % 10) * 0.04}s` }}
                  >
                    <div className="prof-review-top">
                      <div className="prof-review-ratings">
                        <div className="prof-review-rating-item">
                          <span className="prof-review-rating-label">Quality</span>
                          <span
                            className="prof-review-rating-value"
                            data-score={r.quality >= 4 ? 'high' : r.quality >= 3 ? 'mid' : 'low'}
                          >
                            {r.quality}
                          </span>
                        </div>
                        <div className="prof-review-rating-item">
                          <span className="prof-review-rating-label">Difficulty</span>
                          <span
                            className="prof-review-rating-value"
                            data-score={r.difficulty <= 2 ? 'high' : r.difficulty <= 3 ? 'mid' : 'low'}
                          >
                            {r.difficulty}
                          </span>
                        </div>
                      </div>

                      <div className="prof-review-meta">
                        {r.course && <span className="prof-review-course">{r.course}</span>}
                        <span className="prof-review-date">{r.date}</span>
                      </div>
                    </div>

                    {r.comment && <p className="prof-review-comment">{r.comment}</p>}

                    <div className="prof-review-bottom">
                      {r.tags && (
                        <div className="prof-review-tags">
                          {r.tags.split(',').map((tag: string) => tag.trim()).filter(Boolean).map((tag: string, ti: number) => (
                            <span
                              key={ti}
                              className="prof-review-tag"
                              style={{ '--tag-color': getTagColor(tag) } as React.CSSProperties}
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}

                      <div className="prof-review-pills">
                        {r.grade && r.grade !== 'N/A' && (
                          <span className="prof-review-pill">Grade: {r.grade}</span>
                        )}
                        {r.attendance && r.attendance !== 'N/A' && (
                          <span className="prof-review-pill">
                            Attendance: {r.attendance === 'true' || r.attendance === 'Mandatory' ? 'Mandatory' : 'Not Mandatory'}
                          </span>
                        )}
                        {r.textbook && r.textbook !== 'N/A' && (
                          <span className="prof-review-pill">
                            Textbook: {r.textbook === 'true' || r.textbook === 'Yes' ? 'Yes' : 'No'}
                          </span>
                        )}
                        {r.online_class && r.online_class !== 'N/A' && (
                          <span className="prof-review-pill">
                            {r.online_class === 'true' || r.online_class === 'Yes' ? 'Online' : 'In-Person'}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>

            {visibleReviews < filteredReviews.length && (
              <button
                className="prof-load-more"
                onClick={() => setVisibleReviews((v) => v + 10)}
              >
                Load More Reviews ({filteredReviews.length - visibleReviews} remaining)
              </button>
            )}
          </>
        )}

        {/* ── TRACE comments ── */}
        {reviewTab === 'trace' && (
          <div className="prof-reviews-list">
            {traceComments.length === 0 ? (
              <p className="prof-no-reviews">No TRACE comments available.</p>
            ) : (
              traceComments.slice(0, visibleReviews).map((c, i) => (
                <div
                  key={i}
                  className="prof-review-card trace-card"
                  style={{ animationDelay: `${(i % 10) * 0.04}s` }}
                >
                  <span className="prof-trace-question">{c.question}</span>
                  <p className="prof-review-comment">{c.comment}</p>
                </div>
              ))
            )}
            {visibleReviews < traceComments.length && (
              <button
                className="prof-load-more"
                onClick={() => setVisibleReviews((v) => v + 10)}
              >
                Load More ({traceComments.length - visibleReviews} remaining)
              </button>
            )}
          </div>
        )}
      </section>

      {/* ════════ RMP Link ════════ */}
      {profile.professorUrl && (
        <section className="prof-section prof-external-link">
          <a
            href={profile.professorUrl}
            target="_blank"
            rel="noreferrer"
            className="prof-rmp-link"
          >
            View on RateMyProfessors →
          </a>
        </section>
      )}

      <Footer />
      <FeedbackTab />
      <ThemeToggle />
    </div>
  );
};

export default Professor;