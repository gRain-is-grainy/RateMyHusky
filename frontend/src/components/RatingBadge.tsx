import './RatingBadge.css';

interface RatingBadgeProps {
  label: string;
  value: number | null;
  size?: 'sm' | 'md' | 'lg';
}

const RatingBadge = ({ label, value, size = 'md' }: RatingBadgeProps) => {
  const displayValue = value !== null ? value.toFixed(2) : '—';

  const getColor = (v: number | null) => {
    if (v === null) return 'neutral';
    if (v >= 4) return 'high';
    if (v >= 3) return 'mid';
    return 'low';
  };

  return (
    <div className={`rating-badge rating-badge-${size}`} data-color={getColor(value)}>
      <span className="rating-badge-value">{displayValue}</span>
      <span className="rating-badge-label">{label}</span>
    </div>
  );
};

export default RatingBadge;
