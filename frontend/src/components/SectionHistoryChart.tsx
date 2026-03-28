import { useMemo, useState } from 'react';
import {
	LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import type { CourseSection } from '../api/api';
import './SectionHistoryChart.css';

type Mode = 'aggregate' | 'individual';

interface Props {
	sections: CourseSection[];
}

interface YearPoint {
	year: string;
	avg: number | null;
	trace: number | null;
	rmp: number | null;
}

function buildChartData(sections: CourseSection[]): YearPoint[] {
	const yearMap = new Map<string, { traceSum: number; traceCount: number; rmpSum: number; rmpCount: number }>();

	for (const s of sections) {
		const match = s.termTitle.match(/\b(20\d{2})\b/);
		const year = match ? match[0] : 'Unknown';
		let entry = yearMap.get(year);
		if (!entry) {
			entry = { traceSum: 0, traceCount: 0, rmpSum: 0, rmpCount: 0 };
			yearMap.set(year, entry);
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

	return Array.from(yearMap.entries())
		.sort(([a], [b]) => Number(a) - Number(b))
		.map(([year, d]) => {
			const trace = d.traceCount > 0 ? +(d.traceSum / d.traceCount).toFixed(2) : null;
			const rmp = d.rmpCount > 0 ? +(d.rmpSum / d.rmpCount).toFixed(2) : null;
			let avg: number | null = null;
			if (trace != null && rmp != null) avg = +((trace + rmp) / 2).toFixed(2);
			else if (trace != null) avg = trace;
			else if (rmp != null) avg = rmp;
			return { year, avg, trace, rmp };
		});
}

const RANGE_OPTIONS = [
	{ label: 'All Years', value: 0 },
	{ label: 'Last 5', value: 5 },
	{ label: 'Last 10', value: 10 },
	{ label: 'Last 20', value: 20 },
] as const;

export default function SectionHistoryChart({ sections }: Props) {
	const [mode, setMode] = useState<Mode>('aggregate');
	const [range, setRange] = useState(0);

	const allData = useMemo<YearPoint[]>(() => buildChartData(sections), [sections]);
	const data = range > 0 ? allData.slice(-range) : allData;

	if (data.length === 0) return null;

	return (
		<div className="sh-chart-wrap">
			<div className="sh-chart-controls">
				<div className="sh-toggle">
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
					<LineChart data={data} margin={{ top: 12, right: 20, left: 0, bottom: 4 }}>
						<CartesianGrid strokeDasharray="3 3" stroke="var(--sh-grid)" />
						<XAxis
							dataKey="year"
							tick={{ fontSize: 11, fill: 'var(--sh-axis)' }}
							height={40}
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
