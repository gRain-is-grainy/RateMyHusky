import { useRef, useState, useEffect, useCallback } from 'react';
import './RatingBar.css';

interface RatingBarProps {
  star: number;
  count: number;
  max: number;
}

const RatingBar = ({ star, count, max }: RatingBarProps) => {
  const pct = max > 0 ? (count / max) * 100 : 0;
  const ref = useRef<HTMLDivElement>(null);
  const [animated, setAnimated] = useState(false);

  const trigger = useCallback(() => {
    if (!animated) setAnimated(true);
  }, [animated]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          trigger();
          obs.disconnect();
        }
      },
      { threshold: 0.3 },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [trigger]);

  return (
    <div className="rating-bar-row" ref={ref}>
      <span className="rating-bar-star">{star} ★</span>
      <div className="rating-bar-track">
        <div
          className="rating-bar-fill"
          style={{ width: animated ? `${pct}%` : '0%' }}
        />
      </div>
      <span className="rating-bar-count">{count}</span>
    </div>
  );
};

export default RatingBar;
