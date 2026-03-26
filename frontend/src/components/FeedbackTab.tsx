import { useState, useEffect } from 'react';
import logo from '../assets/logo.jpg';
import Dropdown from './Dropdown';
import './FeedbackTab.css';

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
  const [error, setError] = useState('');

  useEffect(() => {
    const handler = () => setIsOpen(true);
    window.addEventListener('open-feedback', handler);
    return () => window.removeEventListener('open-feedback', handler);
  }, []);

  const handleSubmit = () => {
    if (!feedbackType || !description.trim()) {
      setError('Please select a feedback type and enter a description.');
      return;
    }
    setError('');
    setSubmitted(true);
  };

  const handleClose = () => {
    setIsOpen(false);
    // Reset after close animation
    setTimeout(() => {
      setSubmitted(false);
      setFeedbackType('');
      setDescription('');
      setEmail('');
      setError('');
    }, 300);
  };

  const getPlaceholder = () => {
    if (feedbackType === 'missing') {
      return "What data is missing? Please include the professor name and any relevant links.";
    }
    if (feedbackType === 'wrongname') {
      return "What's the correct name? Please provide links to their RMP pages so we can fix it.";
    }
    return "Say more about bugs, suggestions, etc.";
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
                  Found a bug? RateMyHusky's #1 fan? Let our devs know through this form.
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

                <button className="feedback-submit" onClick={handleSubmit}>Submit</button>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
};

export default FeedbackTab;