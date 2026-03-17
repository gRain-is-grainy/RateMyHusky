import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import ThemeToggle from '../components/ThemeToggle';
import StarRating from '../components/StarRating';
import NotFound from './NotFound';
import { fetchCourseData } from '../api/api';
import type { CourseDetail } from '../api/api';
import './Course.css';

const Course = () => {
	const { code = '' } = useParams<{ code: string }>();
	const [course, setCourse] = useState<CourseDetail | null>(null);
	const [loading, setLoading] = useState(true);
	const [notFound, setNotFound] = useState(false);

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

	const topQuestions = useMemo(() => {
		if (!course) return [];
		return course.questionScores
			.filter((q) => q.avgRating !== null)
			.slice(0, 6);
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

				<section className="course-panel">
					<div className="course-panel-header">
						<h2>Instructor Breakdown</h2>
					</div>
					<div className="course-table-wrap">
						<table className="course-table">
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
								{course.instructors.map((row) => (
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
				</section>

				<section className="course-panel">
					<div className="course-panel-header">
						<h2>Section History</h2>
					</div>
					<div className="course-table-wrap">
						<table className="course-table">
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
								{course.sections.map((row) => (
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
				</section>

				{topQuestions.length > 0 && (
					<section className="course-panel">
						<div className="course-panel-header">
							<h2>Top TRACE Questions</h2>
						</div>
						<div className="course-question-grid">
							{topQuestions.map((q) => (
								<article className="course-question-card" key={q.question}>
									<p>{q.question}</p>
									<strong>{q.avgRating != null ? q.avgRating.toFixed(2) : 'N/A'}</strong>
									<span>{q.totalResponses} responses</span>
								</article>
							))}
						</div>
					</section>
				)}
			</div>
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

export default Course;
