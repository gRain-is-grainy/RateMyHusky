import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import {
	LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import type { CourseSection } from '../api/api';
import './SectionHistoryChart.css';

type Mode = 'aggregate' | 'individual';

interface Props {
	sections: CourseSection[];
}

interface TermPoint {
	term: string;
	termId: number;
	year: number;
	avg: number | null;
	trace: number | null;
	rmp: number | null;
}

function buildChartData(sections: CourseSection[]): TermPoint[] {
	const termMap = new Map<number, { title: string; year: number; traceSum: number; traceCount: number; rmpSum: number; rmpCount: number }>();

	for (const s of sections) {
		let entry = termMap.get(s.termId);
		if (!entry) {
			const cleaned = s.termTitle.replace(/^\d{6}:\s*/, '').replace(/\s*\d{6}/g, '').trim();
			const yearMatch = cleaned.match(/\b(20\d{2})\b/);
			const year = yearMatch ? Number(yearMatch[1]) : 0;
			entry = { title: cleaned, year, traceSum: 0, traceCount: 0, rmpSum: 0, rmpCount: 0 };
			termMap.set(s.termId, entry);
		}
		if (s.overallRating != null) {
			entry.traceSum += s.overallRating;
			entry.traceCount += 1;
		}
		if (s.rmpRating != null) {
			entry.rmpSum += s.rmpRating;
			entry.rmpCount += 1;
		}
	}

	return Array.from(termMap.entries())
		.sort(([a], [b]) => a - b)
		.map(([termId, d]) => {
			const trace = d.traceCount > 0 ? +(d.traceSum / d.traceCount).toFixed(2) : null;
			const rmp = d.rmpCount > 0 ? +(d.rmpSum / d.rmpCount).toFixed(2) : null;
			let avg: number | null = null;
			if (trace != null && rmp != null) avg = +((trace + rmp) / 2).toFixed(2);
			else if (trace != null) avg = trace;
			else if (rmp != null) avg = rmp;
			return { term: d.title, termId, year: d.year, avg, trace, rmp };
		});
}

const RANGE_OPTIONS = [
	{ label: 'All Years', value: 0 },
	{ label: '1 Year', value: 1 },
	{ label: '5 Years', value: 5 },
	{ label: '10 Years', value: 10 },
] as const;

export default function SectionHistoryChart({ sections }: Props) {
	const [mode, setMode] = useState<Mode>('aggregate');
	const [range, setRange] = useState(0);
	const tabsRef = useRef<HTMLDivElement>(null);
	const [pillStyle, setPillStyle] = useState({ left: 0, width: 0, opacity: 0 });
	const [pillReady, setPillReady] = useState(false);

	const updatePill = useCallback(() => {
		if (!tabsRef.current) return;
		const activeTab = tabsRef.current.querySelector('.sh-toggle-btn.active') as HTMLElement;
		if (activeTab) {
			setPillStyle({ left: activeTab.offsetLeft, width: activeTab.offsetWidth, opacity: 1 });
		}
	}, []);

	useLayoutEffect(() => {
		updatePill();
	}, [mode, updatePill]);

	useEffect(() => {
		updatePill();
		const timer = setTimeout(() => setPillReady(true), 150);
		return () => clearTimeout(timer);
	}, [updatePill]);

	const allData = useMemo<TermPoint[]>(() => buildChartData(sections), [sections]);

	const data = useMemo(() => {
		if (range === 0) return allData;
		const maxYear = Math.max(...allData.map(p => p.year).filter(y => y > 0));
		return allData.filter(p => p.year >= maxYear - range + 1);
	}, [allData, range]);

	if (data.length === 0) return null;

	return (
		<div className="sh-chart-wrap">
			<div className="sh-chart-controls">
				<div className="sh-toggle" ref={tabsRef}>
					<div
						className={`sh-pill-bg ${pillReady ? 'animate' : ''}`}
						style={{
							transform: `translateX(${pillStyle.left}px)`,
							width: `${pillStyle.width}px`,
							opacity: pillStyle.opacity,
							visibility: pillStyle.opacity === 0 ? 'hidden' : 'visible',
						}}
					/>
					<button
						type="button"
						className={`sh-toggle-btn ${mode === 'aggregate' ? 'active' : ''}`}
						onClick={() => setMode('aggregate')}
					>
						Aggregate
					</button>
					<button
						type="button"
						className={`sh-toggle-btn ${mode === 'individual' ? 'active' : ''}`}
						onClick={() => setMode('individual')}
					>
						Individual
					</button>
				</div>
				<select
					className="sh-range-select"
					value={range}
					onChange={(e) => setRange(Number(e.target.value))}
				>
					{RANGE_OPTIONS.map((opt) => (
						<option key={opt.value} value={opt.value}>{opt.label}</option>
					))}
				</select>
			</div>

			<div className="sh-chart-container">
				<ResponsiveContainer width="100%" height={300}>
					<LineChart data={data} margin={{ top: 12, right: 20, left: 30, bottom: 4 }}>
						<CartesianGrid strokeDasharray="3 3" stroke="var(--sh-grid)" />
						<XAxis
							dataKey="term"
							tick={{ fontSize: 11, fill: 'var(--sh-axis)' }}
							angle={-30}
							textAnchor="end"
							height={60}
							interval="preserveStartEnd"
						/>
						<YAxis
							domain={[1, 5]}
							ticks={[1, 2, 3, 4, 5]}
							tick={{ fontSize: 11, fill: 'var(--sh-axis)' }}
							width={32}
						/>
						<Tooltip
							contentStyle={{
								background: 'var(--sh-tooltip-bg)',
								border: '1px solid var(--sh-tooltip-border)',
								borderRadius: 8,
								fontSize: 13,
								color: 'var(--sh-tooltip-text)',
							}}
							formatter={(value) => typeof value === 'number' ? value.toFixed(2) : String(value ?? '')}
						/>
						<Legend />
						{mode === 'aggregate' ? (
							<Line
								type="monotone"
								dataKey="avg"
								name="Avg Rating"
								stroke="#5ec4a8"
								strokeWidth={2.5}
								dot={{ r: 3, fill: '#5ec4a8' }}
								activeDot={{ r: 5 }}
								connectNulls
							/>
						) : (
							<>
								<Line
									type="monotone"
									dataKey="trace"
									name="TRACE"
									stroke="#5ec4a8"
									strokeWidth={2.5}
									dot={{ r: 3, fill: '#5ec4a8' }}
									activeDot={{ r: 5 }}
									connectNulls
								/>
								<Line
									type="monotone"
									dataKey="rmp"
									name="RMP"
									stroke="#e8736c"
									strokeWidth={2.5}
									dot={{ r: 3, fill: '#e8736c' }}
									activeDot={{ r: 5 }}
									connectNulls
								/>
							</>
						)}
					</LineChart>
				</ResponsiveContainer>
			</div>
		</div>
	);
}
