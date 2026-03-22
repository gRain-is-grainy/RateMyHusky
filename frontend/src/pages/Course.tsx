import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import ThemeToggle from '../components/ThemeToggle';
import StarRating from '../components/StarRating';
import NotFound from './NotFound';
import { fetchCourseData } from '../api/api';
import type { CourseDetail } from '../api/api';
import Footer from '../components/Footer';
import './Course.css';

const INITIAL_INSTRUCTORS_VISIBLE = 5;
const INSTRUCTORS_VISIBLE_STEP = 5;
const INITIAL_SECTIONS_VISIBLE = 8;
const SECTIONS_VISIBLE_STEP = 8;

const Course = () => {
	const { code = '' } = useParams<{ code: string }>();
	const [course, setCourse] = useState<CourseDetail | null>(null);
	const [loading, setLoading] = useState(true);
	const [notFound, setNotFound] = useState(false);
	const [visibleInstructorCount, setVisibleInstructorCount] = useState(INITIAL_INSTRUCTORS_VISIBLE);
	const [visibleSectionCount, setVisibleSectionCount] = useState(INITIAL_SECTIONS_VISIBLE);

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
		setVisibleSectionCount(INITIAL_SECTIONS_VISIBLE);
	}, [course?.summary.code]);

	const topInstructors = useMemo(() => {
		if (!course) return [];
		return [...course.instructors]
			.sort((a, b) => {
				const aRating = a.avgRating ?? -1;
				const bRating = b.avgRating ?? -1;
				if (bRating !== aRating) return bRating - aRating;
				if (b.totalResponses !== a.totalResponses) return b.totalResponses - a.totalResponses;
				return b.sections - a.sections;
			})
			.slice(0, 10);
	}, [course]);

	if (loading) {
		return (
			<div className="course-page">
				<ThemeToggle />
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
	const visibleSections = course.sections.slice(0, visibleSectionCount);
	const hasMoreInstructors = visibleInstructorCount < course.instructors.length;
	const hasMoreSections = visibleSectionCount < course.sections.length;
	const canCollapseInstructors = visibleInstructorCount > INITIAL_INSTRUCTORS_VISIBLE;
	const canCollapseSections = visibleSectionCount > INITIAL_SECTIONS_VISIBLE;
	const hasExpandableInstructors = course.instructors.length > INITIAL_INSTRUCTORS_VISIBLE;
	const hasExpandableSections = course.sections.length > INITIAL_SECTIONS_VISIBLE;

	return (
		<div className="course-page">
			<ThemeToggle />
			<div className="course-shell">
				<div className="course-breadcrumb">
					<Link to="/courses">Courses</Link>
					<span>/</span>
					<span>{summary.code}</span>
				</div>

				<header className="course-hero">
					<div>
						<p className="course-code">{summary.code}</p>
						<h1>{summary.name}</h1>
						<p className="course-dept">{summary.department}</p>
					</div>
					<div className="course-rating-box">
						{summary.avgRating != null ? (
							<>
								<StarRating rating={summary.avgRating} size="md" />
								<span className="course-rating-value">{summary.avgRating.toFixed(2)}</span>
							</>
						) : (
							<span className="course-rating-value na">N/A</span>
						)}
						<span className="course-rating-label">TRACE aggregate</span>
					</div>
				</header>

				<section className="course-stats-grid">
					<StatCard label="Sections" value={summary.totalSections.toLocaleString()} />
					<StatCard label="Instructors" value={summary.totalInstructors.toLocaleString()} />
					<StatCard label="Enrollment" value={summary.totalEnrollment.toLocaleString()} />
					<StatCard label="Responses" value={summary.totalResponses.toLocaleString()} />
					<StatCard label="Latest Term" value={summary.latestTermTitle || 'Unknown'} />
				</section>

				{topInstructors.length > 0 && (
					<section className="course-panel">
						<div className="course-panel-header">
							<h2>Top 10 Professors Who Teach This Class</h2>
						</div>
						<div className="course-top-prof-grid">
							{topInstructors.map((prof, index) => (
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
									<div className="course-top-prof-rank">#{index + 1}</div>
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
													<StarRating rating={prof.avgRating} size="sm" />
													<span>{prof.avgRating.toFixed(2)}</span>
												</>
											) : (
												<span>N/A</span>
											)}
										</div>
										<div className="course-top-prof-meta">
											<span>
												Difficulty: {prof.difficulty != null ? `${prof.difficulty.toFixed(2)}/5` : 'N/A'}
											</span>
											<span>
												Would Take Again: {prof.wouldTakeAgainPct != null ? `${prof.wouldTakeAgainPct.toFixed(1)}%` : 'N/A'}
											</span>
											<span>Total Reviews: {prof.totalReviews.toLocaleString()}</span>
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
						<h2>Section History</h2>
					</div>
					<div className="course-table-wrap">
						<table className="course-table section-table">
							<thead>
								<tr>
									<th>Term</th>
									<th>Section</th>
									<th>Instructor</th>
									<th>Overall</th>
									<th>Enrollment</th>
									<th>Responses</th>
								</tr>
							</thead>
							<tbody>
								{visibleSections.map((row) => (
									<tr key={`${row.courseId}-${row.instructorId}-${row.termId}`}>
										<td>{row.termTitle}</td>
										<td>{row.section || '-'}</td>
										<td>{row.instructor}</td>
										<td>{row.overallRating != null ? row.overallRating.toFixed(2) : 'N/A'}</td>
										<td>{row.enrollment}</td>
										<td>{row.totalResponses}</td>
									</tr>
								))}
							</tbody>
						</table>
					</div>
					{hasExpandableSections && (
						<div className="course-expand-controls" aria-label="Section history controls">
							<button
								type="button"
								className="course-expand-btn"
								aria-label="Collapse sections"
								title="Collapse sections"
								disabled={!canCollapseSections}
								onClick={() => setVisibleSectionCount(INITIAL_SECTIONS_VISIBLE)}
							>
								<span className="visually-hidden">Collapse sections</span>
								<span className="course-expand-chevron up" aria-hidden="true" />
							</button>
							<button
								type="button"
								className="course-expand-btn"
								aria-label="Show more sections"
								title="Show more sections"
								disabled={!hasMoreSections}
								onClick={() =>
									setVisibleSectionCount((prev) =>
										Math.min(prev + SECTIONS_VISIBLE_STEP, course.sections.length)
									)
								}
							>
								<span className="visually-hidden">Show more sections</span>
								<span className="course-expand-chevron down" aria-hidden="true" />
							</button>
						</div>
					)}
				</section>

			</div>
			<Footer />
		</div>
	);
};

function StatCard({ label, value }: { label: string; value: string }) {
	return (
		<article className="course-stat-card">
			<span>{label}</span>
			<strong>{value}</strong>
		</article>
	);
}

function getInitials(name: string): string {
	return name
		.split(' ')
		.filter(Boolean)
		.slice(0, 2)
		.map((part) => part[0]?.toUpperCase() ?? '')
		.join('');
}

export default Course;
