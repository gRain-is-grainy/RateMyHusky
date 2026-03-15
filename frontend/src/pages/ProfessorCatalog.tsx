import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  fetchProfessorsCatalog,
  fetchColleges,
  fetchDepartments,
  type CatalogProfessor,
} from '../api/api';
import StarRating from '../components/StarRating';
import RatingBadge from '../components/RatingBadge';
import Dropdown from '../components/Dropdown';
import ThemeToggle from '../components/ThemeToggle';
import './ProfessorCatalog.css';

const SORT_OPTIONS = [
  { value: 'alpha',   label: 'A – Z' },
  { value: 'rating',  label: 'Highest Rating' },
  { value: 'reviews', label: 'Most Reviews' },
];

interface Filters {
  college:    string;
  dept:       string;
  minRating:  number;
  minReviews: number;
  sort:       string;
  page:       number;
}

const DEFAULT_FILTERS: Filters = {
  college:    '',
  dept:       '',
  minRating:  0,
  minReviews: 1,
  sort:       'alpha',
  page:       1,
};

function initials(name: string) {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map(n => n[0].toUpperCase())
    .join('');
}

export default function ProfessorCatalog() {
  const navigate = useNavigate();
  const [filters, setFilters]       = useState<Filters>(DEFAULT_FILTERS);
  const [colleges, setColleges]     = useState<string[]>([]);
  const [departments, setDepts]     = useState<string[]>([]);
  const [professors, setProfessors] = useState<CatalogProfessor[]>([]);
  const [total, setTotal]           = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading]       = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Fetch colleges once
  useEffect(() => {
    fetchColleges().then(setColleges).catch(console.error);
  }, []);

  // Re-fetch departments when college changes
  useEffect(() => {
    fetchDepartments(filters.college || undefined)
      .then(setDepts)
      .catch(console.error);
  }, [filters.college]);

  // Fetch professors when any filter changes
  useEffect(() => {
    setLoading(true);
    fetchProfessorsCatalog({
      college:    filters.college    || undefined,
      dept:       filters.dept       || undefined,
      minRating:  filters.minRating  > 0 ? filters.minRating  : undefined,
      minReviews: filters.minReviews > 1 ? filters.minReviews : undefined,
      sort:       filters.sort as 'alpha' | 'rating' | 'reviews',
      page:       filters.page,
      limit:      20,
    })
      .then(data => {
        setProfessors(data.professors);
        setTotal(data.total);
        setTotalPages(data.totalPages);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [filters]);

  const updateFilter = useCallback(
    <K extends keyof Filters>(key: K, value: Filters[K]) => {
      setFilters(f => ({
        ...f,
        [key]: value,
        page: key !== 'page' ? 1 : (value as number),
      }));
    },
    []
  );

  const setCollege = useCallback((college: string) => {
    setFilters(f => ({ ...f, college, dept: '', page: 1 }));
  }, []);

  const clearFilters = () => setFilters(DEFAULT_FILTERS);

  const hasActiveFilters =
    !!filters.college || !!filters.dept || filters.minRating > 0 || filters.minReviews > 1;

  return (
    <div className="catalog-page">
      <ThemeToggle />
      {/* Mobile sidebar toggle */}
      <button
        className="catalog-filter-toggle"
        onClick={() => setSidebarOpen(o => !o)}
        aria-label="Toggle filters"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <line x1="4" y1="6" x2="20" y2="6" />
          <line x1="4" y1="12" x2="20" y2="12" />
          <line x1="4" y1="18" x2="20" y2="18" />
        </svg>
        Filters
        {hasActiveFilters && <span className="filter-active-dot" />}
      </button>

      {sidebarOpen && (
        <div className="catalog-overlay" onClick={() => setSidebarOpen(false)} />
      )}

      <div className="catalog-layout">
        {/* ── Sidebar ── */}
        <aside className={`catalog-sidebar ${sidebarOpen ? 'open' : ''}`}>
          <div className="sidebar-inner">
            <div className="sidebar-header">
              <span className="sidebar-title">Filters</span>
              {hasActiveFilters && (
                <button className="clear-btn" onClick={clearFilters}>
                  Clear all
                </button>
              )}
            </div>

            {/* Sort */}
            <div className="filter-section">
              <p className="filter-label">Sort by</p>
              <Dropdown
                options={SORT_OPTIONS}
                value={filters.sort}
                onChange={v => updateFilter('sort', v)}
              />
            </div>

            {/* College */}
            <div className="filter-section">
              <p className="filter-label">College</p>
              <div className="college-pills">
                <button
                  className={`college-pill ${!filters.college ? 'active' : ''}`}
                  onClick={() => setCollege('')}
                >
                  All
                </button>
                {colleges.map(c => (
                  <button
                    key={c}
                    className={`college-pill ${filters.college === c ? 'active' : ''}`}
                    onClick={() => setCollege(c)}
                  >
                    {c}
                  </button>
                ))}
              </div>
            </div>

            {/* Department */}
            <div className="filter-section">
              <p className="filter-label">Department</p>
              <DepartmentFilter
                departments={departments}
                selected={filters.dept}
                onSelect={d => updateFilter('dept', d)}
              />
            </div>

            {/* Min Rating */}
            <div className="filter-section">
              <p className="filter-label">
                Min. Rating
                <span className="slider-value">
                  {filters.minRating > 0
                    ? `${filters.minRating.toFixed(1)}+`
                    : 'Any'}
                </span>
              </p>
              <input
                type="range"
                className="rating-slider"
                min="0"
                max="5"
                step="0.5"
                value={filters.minRating}
                onChange={e => updateFilter('minRating', parseFloat(e.target.value))}
              />
              <div className="slider-ticks">
                <span>Any</span>
                <span>5.0</span>
              </div>
            </div>

            {/* Min Reviews */}
            <div className="filter-section">
              <p className="filter-label">Min. Reviews</p>
              <div className="reviews-input-row">
                <input
                  type="range"
                  className="rating-slider"
                  min="1"
                  max="100"
                  step="1"
                  value={filters.minReviews}
                  onChange={e => updateFilter('minReviews', parseInt(e.target.value, 10))}
                />
                <input
                  type="number"
                  className="reviews-number-input"
                  min="1"
                  max="999"
                  value={filters.minReviews === 1 ? '' : filters.minReviews}
                  placeholder="Any"
                  onChange={e => {
                    const v = parseInt(e.target.value, 10);
                    updateFilter('minReviews', isNaN(v) || v < 1 ? 1 : Math.min(v, 999));
                  }}
                />
              </div>
              <div className="slider-ticks">
                <span>Any</span>
                <span>100</span>
              </div>
            </div>
          </div>
        </aside>

        {/* ── Main ── */}
        <main className="catalog-main">
          <div className="catalog-header">
            <h1 className="catalog-title">Professors</h1>
            <span className="catalog-count">
              {loading ? '…' : `${total.toLocaleString()} result${total !== 1 ? 's' : ''}`}
            </span>
          </div>
          <p className="catalog-disclaimer">
            Professors without any rating data are not shown.{' '}
            <span>They may still have a profile if found via search.</span>
          </p>

          {loading ? (
            <div className="catalog-grid">
              {Array.from({ length: 20 }).map((_, i) => (
                <div key={i} className="prof-card skeleton" />
              ))}
            </div>
          ) : professors.length === 0 ? (
            <div className="catalog-empty">
              <p>No professors match your filters.</p>
              <button className="clear-btn prominent" onClick={clearFilters}>
                Clear filters
              </button>
            </div>
          ) : (
            <div className="catalog-grid">
              {professors.map(prof => (
                <div
                  key={prof.slug}
                  className="prof-card"
                  role="button"
                  tabIndex={0}
                  onClick={() => navigate(`/professors/${prof.slug}`)}
                  onKeyDown={e =>
                    e.key === 'Enter' && navigate(`/professors/${prof.slug}`)
                  }
                >
                  <div className="prof-avatar">{initials(prof.name)}</div>
                  <div className="prof-body">
                    <h3 className="prof-name">{prof.name}</h3>
                    <p className="prof-dept">{prof.department}</p>
                    <span className="prof-college">{prof.college}</span>

                    <div className="prof-rating-row">
                      {prof.avgRating != null ? (
                        <>
                          <StarRating rating={prof.avgRating} size="sm" />
                          <span className="prof-avg">{prof.avgRating.toFixed(2)}</span>
                        </>
                      ) : (
                        <span className="prof-avg na">N/A</span>
                      )}
                    </div>

                    <div className="prof-badges">
                      <RatingBadge label="RMP"   value={prof.rmpRating}   size="sm" />
                      <RatingBadge label="TRACE" value={prof.traceRating} size="sm" />
                    </div>

                    <div className="prof-meta">
                      <span>{prof.totalReviews.toLocaleString()} review{prof.totalReviews !== 1 ? 's' : ''}</span>
                      {prof.wouldTakeAgainPct != null && (
                        <>
                          <span className="meta-dot">·</span>
                          <span>{prof.wouldTakeAgainPct}% again</span>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {!loading && totalPages > 1 && (
            <Pagination
              page={filters.page}
              totalPages={totalPages}
              onPageChange={p => updateFilter('page', p)}
            />
          )}
        </main>
      </div>
    </div>
  );
}

// ── Department filter sub-component ──────────────────────────────────────────

function DepartmentFilter({
  departments,
  selected,
  onSelect,
}: {
  departments: string[];
  selected: string;
  onSelect: (dept: string) => void;
}) {
  const [search, setSearch] = useState('');
  const filtered = departments.filter(d =>
    d.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="dept-filter">
      <input
        className="dept-search"
        type="text"
        placeholder="Search departments…"
        value={search}
        onChange={e => setSearch(e.target.value)}
      />
      <div className="dept-list">
        <label className="dept-option">
          <input
            type="radio"
            name="dept"
            checked={!selected}
            onChange={() => onSelect('')}
          />
          <span>All departments</span>
        </label>
        {filtered.map(d => (
          <label key={d} className="dept-option">
            <input
              type="radio"
              name="dept"
              checked={selected === d}
              onChange={() => onSelect(d)}
            />
            <span>{d}</span>
          </label>
        ))}
        {filtered.length === 0 && (
          <p className="dept-empty">No departments found</p>
        )}
      </div>
    </div>
  );
}

// ── Pagination sub-component ──────────────────────────────────────────────────

function Pagination({
  page,
  totalPages,
  onPageChange,
}: {
  page: number;
  totalPages: number;
  onPageChange: (p: number) => void;
}) {
  const pages: (number | '...')[] = [];

  if (totalPages <= 7) {
    for (let i = 1; i <= totalPages; i++) pages.push(i);
  } else {
    pages.push(1);
    if (page > 3) pages.push('...');
    for (
      let i = Math.max(2, page - 1);
      i <= Math.min(totalPages - 1, page + 1);
      i++
    ) {
      pages.push(i);
    }
    if (page < totalPages - 2) pages.push('...');
    pages.push(totalPages);
  }

  return (
    <div className="pagination">
      <button
        className="page-btn"
        disabled={page === 1}
        onClick={() => onPageChange(page - 1)}
      >
        ‹
      </button>
      {pages.map((p, i) =>
        p === '...' ? (
          <span key={`ell-${i}`} className="page-ellipsis">…</span>
        ) : (
          <button
            key={p}
            className={`page-btn ${p === page ? 'active' : ''}`}
            onClick={() => onPageChange(p as number)}
          >
            {p}
          </button>
        )
      )}
      <button
        className="page-btn"
        disabled={page === totalPages}
        onClick={() => onPageChange(page + 1)}
      >
        ›
      </button>
    </div>
  );
}
