import { Link, useLocation } from 'react-router-dom';
import './Breadcrumbs.css';

interface BreadcrumbItem {
  label: string;
  to?: string;
}

interface BreadcrumbsProps {
  items: BreadcrumbItem[];
}

const Breadcrumbs = ({ items }: BreadcrumbsProps) => {
  const location = useLocation();

  // If we came from a specific page (e.g. Compare), prepend that as the first breadcrumb
  const fromPage = location.state?.fromPage as { label: string; url: string } | undefined;
  const goatedCollege = location.state?.goatedCollege as string | undefined;
  // Preserve catalog filters when the first link points to /professors
  const catalogLink = location.state?.fromCatalog || '/professors';

  const resolvedItems = fromPage
    ? [{ label: fromPage.label, to: fromPage.url }, ...items.filter(item => item.to !== '/professors')]
    : items;

  return (
    <nav className="breadcrumbs" aria-label="Breadcrumb">
      <ol className="breadcrumbs-list">
        {resolvedItems.map((item, i) => {
          const isLast = i === resolvedItems.length - 1;
          const href = item.to === '/professors' ? catalogLink : item.to;

          return (
            <li key={i} className="breadcrumbs-item">
              {!isLast && href ? (
                <>
                  <Link to={href} state={goatedCollege ? { goatedCollege } : undefined} className="breadcrumbs-link">{item.label}</Link>
                  <span className="breadcrumbs-separator" aria-hidden="true">
                    <svg width="7" height="11" viewBox="0 0 7 11" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M1 1l4.5 4.5L1 10" />
                    </svg>
                  </span>
                </>
              ) : (
                <span className="breadcrumbs-current" aria-current="page">{item.label}</span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
};

export default Breadcrumbs;
