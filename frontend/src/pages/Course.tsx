import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import StarRating from '../components/StarRating';
import NotFound from './NotFound';
import { fetchCourseData } from '../api/api';
import type { CourseDetail } from '../api/api';
import Footer from '../components/Footer';
import { getInitials } from '../utils/nameUtils';
import { termSortKey } from '../utils/termUtils';
import SectionHistoryChart from '../components/SectionHistoryChart';
import Breadcrumbs from '../components/Breadcrumbs';
import './Course.css';

const INITIAL_INSTRUCTORS_VISIBLE = 5;
const INSTRUCTORS_VISIBLE_STEP = 5;

const Course = () => {
	const { code = '' } = useParams<{ code: string }>();
	const [course, setCourse] = useState<CourseDetail | null>(null);
	const [loading, setLoading] = useState(true);
	const [notFound, setNotFound] = useState(false);
	const [visibleInstructorCount, setVisibleInstructorCount] = useState(INITIAL_INSTRUCTORS_VISIBLE);
	const [showBackToTop, setShowBackToTop] = useState(false);

	useEffect(() => {
		let cancelled = false;

		const load = async () => {
			setLoading(true);
			setNotFound(false);
			const data = await fetchCourseData(code);
			if (cancelled) return;
			if (!data) {
				setCourse(null);
				setNotFound(true);
			} else {
				setCourse(data);
			}
			setLoading(false);
		};

		load();
		return () => {
			cancelled = true;
		};
	}, [code]);

	useEffect(() => {
		setVisibleInstructorCount(INITIAL_INSTRUCTORS_VISIBLE);
	}, [course?.summary.code]);

	useEffect(() => {
		const handler = () => setShowBackToTop(window.scrollY > 300);
		window.addEventListener('scroll', handler, { passive: true });
		handler();
		return () => window.removeEventListener('scroll', handler);
	}, []);

	const recentInstructors = useMemo(() => {
		if (!course) return [];
		const currentYear = new Date().getFullYear();
		const instructorLatestTermId = new Map<string, number>();

		const getInstructorsWithinYears = (yearsBack: number) => {
			const cutoffYear = currentYear - yearsBack;
			const recentNames = new Set<string>();
			for (const section of course.sections) {
				const yearMatch = section.termTitle.match(/\b(20\d{2})\b/);
				if (yearMatch && parseInt(yearMatch[1]) >= cutoffYear) {
					recentNames.add(section.instructor);
					const prev = instructorLatestTermId.get(section.instructor) ?? 0;
					const cur = termSortKey(section.termTitle);
					if (cur > prev) instructorLatestTermId.set(section.instructor, cur);
				}
			}
			return course.instructors.filter(inst => recentNames.has(inst.name));
		};

		// Start with 1 year, expand until at least 5 or no more data
		let result = getInstructorsWithinYears(1);
		let yearsBack = 1;
		const maxYear = currentYear - 2000 + 1; // won't go past year 2000
		while (result.length < 5 && yearsBack < maxYear) {
			yearsBack++;
			result = getInstructorsWithinYears(yearsBack);
		}

		const sorted = result.sort((a, b) => {
			const aTermId = instructorLatestTermId.get(a.name) ?? 0;
			const bTermId = instructorLatestTermId.get(b.name) ?? 0;
			if (bTermId !== aTermId) return bTermId - aTermId;
			const aRating = a.avgRating ?? -1;
			const bRating = b.avgRating ?? -1;
			return bRating - aRating;
		});

		if (sorted.length > 10) {
			return sorted
				.sort((a, b) => (b.avgRating ?? -1) - (a.avgRating ?? -1))
				.slice(0, 10);
		}
		return sorted;
	}, [course]);

	const avgDifficulty = useMemo(() => {
		if (!course) return null;
		const valid = course.instructors.filter(i => i.difficulty != null);
		if (!valid.length) return null;
		return valid.reduce((sum, i) => sum + i.difficulty!, 0) / valid.length;
	}, [course]);

	const avgHoursPerWeek = useMemo(() => {
		if (!course) return null;
		const q = course.questionScores.find(s => s.question.toLowerCase().includes('hours per week'));
		return q?.avgRating ?? null;
	}, [course]);

	if (loading) {
		return (
			<div className="course-page">
				<div className="course-shell">
					<div className="course-loading">Loading course data...</div>
				</div>
			</div>
		);
	}

	if (notFound || !course) {
		return <NotFound />;
	}

	const summary = course.summary;
	const visibleInstructors = course.instructors.slice(0, visibleInstructorCount);
	const hasMoreInstructors = visibleInstructorCount < course.instructors.length;
	const canCollapseInstructors = visibleInstructorCount > INITIAL_INSTRUCTORS_VISIBLE;
	const hasExpandableInstructors = course.instructors.length > INITIAL_INSTRUCTORS_VISIBLE;

	return (
		<div className="course-page">
			<div className="course-shell">
				<Breadcrumbs items={[
					{ label: 'Courses', to: '/courses' },
					{ label: summary.code },
				]} />

				<header className="course-hero">
					<div>
						<p className="course-code">{summary.code}</p>
						<h1>{summary.name}</h1>
						<p className="course-dept">{summary.department}</p>
					</div>
				</header>

				<section className="course-stats-grid">
					<RatingStatCard avgRating={summary.avgRating} />
					<DifficultyStatCard value={avgDifficulty} />
					<StatCard label="Avg Hrs / Week" value={avgHoursPerWeek != null ? `${avgHoursPerWeek.toFixed(1)}h` : 'N/A'} />
					<StatCard label="Instructors" value={summary.totalInstructors.toLocaleString()} />
					<StatCard label="Avg Enrollment" value={summary.totalSections > 0 ? Math.round(summary.totalEnrollment / summary.totalSections).toLocaleString() : 'N/A'} />
					<StatCard label="Last Taught" value={summary.latestTermTitle || 'Unknown'} />
				</section>

				{recentInstructors.length > 0 && (
					<section className="course-panel">
						<div className="course-panel-header">
							<h2>Recent Professors</h2>
						</div>
						<div className="course-top-prof-grid">
							{recentInstructors.map((prof, index) => (
								<Link
									to={prof.slug ? `/professors/${prof.slug}` : '#'}
									state={prof.slug ? { fromPage: { label: `${code.toUpperCase()} – ${summary.name}`, url: `/courses/${code}` } } : undefined}
									className={`course-top-prof-card${prof.slug ? '' : ' disabled'}`}
									key={`${prof.name}-${index}`}
									aria-label={prof.slug ? `View ${prof.name}` : `${prof.name} profile unavailable`}
									onClick={(e) => {
										if (!prof.slug) e.preventDefault();
									}}
								>
										{prof.imageUrl ? (
										<img
											className="course-top-prof-avatar course-top-prof-photo"
											src={prof.imageUrl}
											alt={prof.name}
										/>
									) : (
										<div className="course-top-prof-avatar" aria-hidden="true">
											{getInitials(prof.name)}
										</div>
									)}
									<div className="course-top-prof-body">
										<h3 className="course-top-prof-name">{prof.name}</h3>
										<div className="course-top-prof-rating">
											{prof.avgRating != null ? (
												<>
													<span className="prof-avg-num">{prof.avgRating.toFixed(2)}</span>
													<StarRating rating={prof.avgRating} size="sm" />
												</>
											) : (
												<span>N/A</span>
											)}
										</div>
										<div className="course-top-prof-meta">
											<span>{prof.totalReviews.toLocaleString()} ratings</span>
											<span>{prof.totalComments.toLocaleString()} comments</span>
											<span>{prof.wouldTakeAgainPct != null ? `${Math.round(prof.wouldTakeAgainPct)}% would take again` : '—'}</span>
										</div>
									</div>
								</Link>
							))}
						</div>
					</section>
				)}

				<section className="course-panel">
					<div className="course-panel-header">
						<h2>Instructor Breakdown</h2>
					</div>
					<div className="course-table-wrap">
						<table className="course-table instructor-table">
							<thead>
								<tr>
									<th>Instructor</th>
									<th>Avg Rating</th>
									<th>Sections</th>
									<th>Enrollment</th>
									<th>Responses</th>
								</tr>
							</thead>
							<tbody>
								{visibleInstructors.map((row) => (
									<tr key={row.name}>
										<td>{row.name}</td>
										<td>{row.avgRating != null ? row.avgRating.toFixed(2) : 'N/A'}</td>
										<td>{row.sections}</td>
										<td>{row.totalEnrollment}</td>
										<td>{row.totalResponses}</td>
									</tr>
								))}
							</tbody>
						</table>
					</div>
					{hasExpandableInstructors && (
						<div className="course-expand-controls" aria-label="Instructor table controls">
							<button
								type="button"
								className="course-expand-btn"
								aria-label="Collapse instructors"
								title="Collapse instructors"
								disabled={!canCollapseInstructors}
								onClick={() => setVisibleInstructorCount(INITIAL_INSTRUCTORS_VISIBLE)}
							>
								<span className="visually-hidden">Collapse instructors</span>
								<span className="course-expand-chevron up" aria-hidden="true" />
							</button>
							<button
								type="button"
								className="course-expand-btn"
								aria-label="Show more instructors"
								title="Show more instructors"
								disabled={!hasMoreInstructors}
								onClick={() =>
									setVisibleInstructorCount((prev) =>
										Math.min(prev + INSTRUCTORS_VISIBLE_STEP, course.instructors.length)
									)
								}
							>
								<span className="visually-hidden">Show more instructors</span>
								<span className="course-expand-chevron down" aria-hidden="true" />
							</button>
						</div>
					)}
				</section>

				<section className="course-panel">
					<div className="course-panel-header">
						<h2>Rating History</h2>
					</div>
					<SectionHistoryChart sections={course.sections} />
				</section>

			</div>
			<button
			className={`back-to-top ${showBackToTop ? 'visible' : ''}`}
			onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
			aria-label="Back to top"
		>
			<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
				<polyline points="18 15 12 9 6 15" />
			</svg>
		</button>
		<Footer />
		</div>
	);
};

function RatingStatCard({ avgRating }: { avgRating: number | null }) {
	return (
		<article className="course-stat-card">
			<strong className="course-stat-value">{avgRating != null ? avgRating.toFixed(2) : '—'}</strong>
			<span className="course-stat-label" style={{ display: 'block', textAlign: 'center', position: 'relative' }}>
				Overall Rating
				{avgRating != null && (
					<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ position: 'absolute', top: '50%', transform: 'translateY(-50%)', marginLeft: '4px', opacity: 0.6 }}><circle cx="12" cy="12" r="10" /><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" /><line x1="12" y1="17" x2="12.01" y2="17" /></svg>
				)}
			</span>
			<StarRating rating={avgRating ?? 0} size="lg" />
			{avgRating != null && (
				<div className="course-stat-breakdown">
					<span>TRACE: {avgRating.toFixed(2)}</span>
				</div>
			)}
		</article>
	);
}

function StatCard({ label, value }: { label: string; value: string }) {
	return (
		<article className="course-stat-card">
			<strong className="course-stat-value">{value}</strong>
			<span className="course-stat-label">{label}</span>
		</article>
	);
}

function DifficultyStatCard({ value }: { value: number | null }) {
	const color = value == null ? '#eee'
		: value <= 1.5 ? '#27ae60'
		: value <= 2.5 ? '#66bd63'
		: value <= 3.0 ? '#f39c12'
		: value <= 3.5 ? '#e67e22'
		: value <= 4.0 ? '#e74c3c'
		: '#c0392b';
	return (
		<article className="course-stat-card">
			<strong className="course-stat-value">{value != null ? value.toFixed(2) : '—'}</strong>
			<span className="course-stat-label">Avg Difficulty</span>
			<div className="course-difficulty-bar">
				<div className="course-difficulty-fill" style={{ width: `${((value ?? 0) / 5) * 100}%`, background: color }} />
			</div>
		</article>
	);
}

export default Course;
