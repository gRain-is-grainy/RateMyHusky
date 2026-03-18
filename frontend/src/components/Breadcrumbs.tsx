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

  // Build the "Professors" link preserving any catalog filters the user came from
  const catalogLink = location.state?.fromCatalog || '/professors';

  return (
    <nav className="breadcrumbs" aria-label="Breadcrumb">
      <ol className="breadcrumbs-list">
        {items.map((item, i) => {
          const isLast = i === items.length - 1;
          const href = item.to === '/professors' ? catalogLink : item.to;

          return (
            <li key={i} className="breadcrumbs-item">
              {!isLast && href ? (
                <>
                  <Link to={href} className="breadcrumbs-link">{item.label}</Link>
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
