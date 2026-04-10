import { useState, useEffect, useRef, useCallback } from 'react';
import logo from '../assets/logo.jpg';
import Dropdown from './Dropdown';
import { submitFeedback } from '../api/api';
import './FeedbackTab.css';

declare global {
  interface Window {
    turnstile?: {
      render: (container: string | HTMLElement, options: Record<string, unknown>) => string;
      remove: (widgetId: string) => void;
      reset: (widgetId: string) => void;
    };
  }
}

const TURNSTILE_SITE_KEY = import.meta.env.VITE_TURNSTILE_SITE_KEY || '1x00000000000000000000AA'; // test key fallback

const feedbackOptions = [
  { value: 'bug', label: 'Bug Report' },
  { value: 'feature', label: 'Feature Request' },
  { value: 'missing', label: 'Missing Data' },
  { value: 'incorrectdata', label: 'Incorrect Data' },
  { value: 'general', label: 'General Feedback' },
];

const FeedbackTab = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [feedbackType, setFeedbackType] = useState('');
  const [description, setDescription] = useState('');
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [turnstileToken, setTurnstileToken] = useState('');
  const turnstileRef = useRef<HTMLDivElement>(null);
  const widgetIdRef = useRef<string | null>(null);

  useEffect(() => {
    const handler = () => setIsOpen(true);
    window.addEventListener('open-feedback', handler);
    return () => window.removeEventListener('open-feedback', handler);
  }, []);

  const renderTurnstile = useCallback(() => {
    if (!turnstileRef.current || !window.turnstile) return;
    if (widgetIdRef.current !== null) {
      window.turnstile.remove(widgetIdRef.current);
      widgetIdRef.current = null;
    }
    widgetIdRef.current = window.turnstile.render(turnstileRef.current, {
      sitekey: TURNSTILE_SITE_KEY,
      callback: (token: string) => setTurnstileToken(token),
      'expired-callback': () => setTurnstileToken(''),
      theme: document.documentElement.classList.contains('dark') ? 'dark' : 'light',
      size: 'normal',
    });
  }, []);

  useEffect(() => {
    if (!isOpen || submitted) return;
    // Wait for Turnstile script to load
    const interval = setInterval(() => {
      if (window.turnstile) {
        clearInterval(interval);
        renderTurnstile();
      }
    }, 100);
    return () => {
      clearInterval(interval);
      if (widgetIdRef.current !== null && window.turnstile) {
        window.turnstile.remove(widgetIdRef.current);
        widgetIdRef.current = null;
      }
      setTurnstileToken('');
    };
  }, [isOpen, submitted, renderTurnstile]);

  const handleSubmit = async () => {
    if (!feedbackType || !description.trim()) {
      setError('Please select a feedback type and enter a description.');
      return;
    }
    if (!turnstileToken) {
      setError('Please complete the CAPTCHA verification.');
      return;
    }
    setError('');
    setLoading(true);
    try {
      await submitFeedback({ feedbackType, description, email: email || undefined, turnstileToken });
      setSubmitted(true);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '';
      if (msg.includes('429') || msg.includes('limit')) {
        setError('Daily feedback limit reached. Please try again tomorrow.');
      } else if (msg.includes('Invalid email')) {
        setError('Please enter a valid email address.');
      } else if (msg.includes('CAPTCHA') || msg.includes('captcha')) {
        setError('CAPTCHA verification failed. Please try again.');
        if (widgetIdRef.current !== null && window.turnstile) {
          window.turnstile.reset(widgetIdRef.current);
        }
        setTurnstileToken('');
      } else {
        setError('Failed to send feedback. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setIsOpen(false);
    setTimeout(() => {
      setSubmitted(false);
      setFeedbackType('');
      setDescription('');
      setEmail('');
      setError('');
      setLoading(false);
      setTurnstileToken('');
    }, 300);
  };

  const getPlaceholder = () => {
    switch (feedbackType) {
      case 'bug':
        return "Describe the bug. What happened, and what did you expect to happen?";
      case 'feature':
        return "What feature would you like to see? Describe what it would do and why it would be useful.";
      case 'missing':
        return "What data is missing? Please include the professor name and any relevant links.";
      case 'incorrectdata':
        return "What data is incorrect? Please include the professor name and what the correct information should be.";
      case 'general':
        return "Share your thoughts, suggestions, or anything else on your mind.";
      default:
        return "Describe your feedback here.";
    }
  };

  return (
    <>
      <button className="feedback-tab" onClick={() => setIsOpen(true)}>
        Feedback
      </button>
      <button className="feedback-fab" onClick={() => setIsOpen(true)} aria-label="Feedback">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
      </button>

      {isOpen && (
        <div className="feedback-overlay" onClick={handleClose}>
          <div
            className={`feedback-modal ${submitted ? 'feedback-modal-shrink' : ''}`}
            onClick={(e) => e.stopPropagation()}
          >
            <button className="feedback-close" onClick={handleClose}>
              ×
            </button>

            {submitted ? (
              <div className="feedback-success">
                <div className="feedback-success-icon">✓</div>
                <h2 className="feedback-title">Thank You!</h2>
                <p className="feedback-success-msg">
                  We've received your feedback and appreciate you taking the time to help us improve RateMyHusky.
                </p>
                <button className="feedback-done-btn" onClick={handleClose}>
                  Done
                </button>
              </div>
            ) : (
              <>
                <div className="feedback-mascot">
                  <img src={logo} alt="RateMyHusky Mascot" className="feedback-mascot-img" />
                </div>

                <h2 className="feedback-title">Feedback Form</h2>
                <p className="feedback-subtitle">
                  Spotted something off? Got ideas? We'd love to hear from you.
                </p>

                {error && <p className="feedback-error">{error}</p>}

                <label className="feedback-label">
                  Type of Feedback <span className="feedback-required">*</span>
                </label>
                <Dropdown
                  className="feedback-dropdown"
                  options={feedbackOptions}
                  value={feedbackType}
                  onChange={setFeedbackType}
                  placeholder="Select Feedback Type"
                />

                <label className="feedback-label">
                  Description <span className="feedback-required">*</span>
                </label>
                <textarea
                  className="feedback-textarea"
                  placeholder={getPlaceholder()}
                  rows={4}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />

                <label className="feedback-label">
                  Email (Optional)
                </label>
                <input
                  className="feedback-input"
                  type="email"
                  placeholder="How should we contact you?"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />

                <div ref={turnstileRef} className="feedback-turnstile" />

                <button className="feedback-submit" onClick={handleSubmit} disabled={loading || !turnstileToken}>
                  {loading ? 'Sending...' : 'Submit'}
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
};

export default FeedbackTab;