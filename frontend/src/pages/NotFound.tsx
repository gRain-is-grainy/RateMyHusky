import { Link } from 'react-router-dom';
import Footer from '../components/Footer';

import huskyIcon from '../assets/neu-husky-icon.png';
import './NotFound.css';

const NotFound = () => {
  return (
    <div className="not-found-page">
      <main className="not-found-main">
        <div className="not-found-shell">
          <section className="not-found-hero">
            <div className="not-found-copy">
              <span className="not-found-kicker">Error 404</span>
              <h1>That page is off the map.</h1>
              <p>
                The link you followed does not point to an active page. Head back to the
                homepage or browse the professor catalog to get back on track.
              </p>

              <div className="not-found-actions">
                <Link to="/" className="not-found-primary-btn">
                  Back to homepage
                </Link>
                <Link to="/professors" className="not-found-secondary-btn">
                  Browse professors
                </Link>
              </div>
            </div>

            <div className="not-found-visual" aria-hidden="true">
              <div className="not-found-visual-glow" />
              <div className="not-found-visual-card">
                <img src={huskyIcon} alt="" className="not-found-husky" />
              </div>
            </div>
          </section>
        </div>
      </main>
      <Footer />
    </div>
  );
};

export default NotFound;
