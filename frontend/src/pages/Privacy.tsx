import Footer from '../components/Footer';
import './Terms.css';

const Privacy = () => {
  return (
    <div className="terms-page">
      <main className="terms-main">
        <div className="terms-shell">
          <header className="terms-header">
            <span className="terms-kicker">Legal</span>
            <h1>Privacy Policy</h1>
            <p className="terms-meta">Effective March 26, 2026 &middot; RateMyHusky</p>
          </header>

          <div className="terms-body">
            <section className="terms-section">
              <h2>1. Introduction</h2>
              <p>
                RateMyHusky is a read-only aggregator of professor and course information for
                Northeastern University students. This Privacy Policy describes what information
                we collect, how we use it, and the choices you have.
              </p>
              <p>
                RateMyHusky is an independent student project and is not affiliated with,
                endorsed by, or officially connected to Northeastern University or RateMyProfessors.
              </p>
            </section>

            <section className="terms-section">
              <h2>2. Information We Collect</h2>
              <p>We collect only the minimum information needed to operate the service:</p>
              <ul>
                <li>
                  <strong>Google Sign-In:</strong> when you authenticate with your{' '}
                  <code>@husky.neu.edu</code> Google account, we receive your name, email
                  address, and profile photo from Google. This information is encoded in a
                  JWT token stored in your browser; it is never written to a server-side
                  database.
                </li>
                <li>
                  <strong>Browser preferences:</strong> your selected theme (dark/light) and
                  catalog view mode are saved to <code>localStorage</code> on your device only
                  and are never transmitted to our servers.
                </li>
                <li>
                  <strong>Feedback form:</strong> the feedback form collects a message type,
                  description, and an optional email address. At this time, submissions are
                  not transmitted to or stored on our servers. If this changes, this Policy
                  will be updated.
                </li>
              </ul>
              <p>
                We do <strong>not</strong> log your search queries, which professor or course
                pages you viewed, or any other browsing activity on our servers.
              </p>
            </section>

            <section className="terms-section">
              <h2>3. How We Use Your Information</h2>
              <p>The information we collect is used solely to:</p>
              <ul>
                <li>Authenticate your identity and confirm your <code>@husky.neu.edu</code> affiliation</li>
                <li>Restrict access to TRACE course evaluation comments to signed-in users</li>
                <li>Display your name and profile photo in the navigation bar while signed in</li>
              </ul>
              <p>
                We do not use your information for advertising, profiling, or any purpose beyond
                operating the service. We do not sell, rent, or share your personal information
                with third parties for their own use.
              </p>
            </section>

            <section className="terms-section">
              <h2>4. How We Store Your Information</h2>
              <p>
                Your sign-in information is encoded in a JWT (JSON Web Token) stored in your
                browser's <code>localStorage</code>. The token expires automatically after
                7 days. RateMyHusky does not maintain a persistent server-side user database;
                no account record is stored beyond the duration of your session token.
              </p>
              <p>
                Signing out deletes the token from your browser immediately.
              </p>
            </section>

            <section className="terms-section">
              <h2>5. Third-Party Services</h2>
              <p>RateMyHusky integrates with the following third-party services that may
                collect data under their own privacy policies:</p>
              <ul>
                <li>
                  <strong>Google OAuth 2.0</strong>: handles authentication. Your use of
                  Google sign-in is governed by{' '}
                  <a
                    href="https://policies.google.com/privacy"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Google's Privacy Policy
                  </a>.
                </li>
                <li>
                  <strong>Vercel Analytics &amp; Speed Insights</strong>: collects anonymous
                  page view and performance metrics. No personally identifiable information is
                  included. Subject to{' '}
                  <a
                    href="https://vercel.com/legal/privacy-policy"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Vercel's Privacy Policy
                  </a>.
                </li>
                <li>
                  <strong>RateMyProfessors &amp; Northeastern TRACE</strong>: these are data
                  sources only. We do not send any user data to these services.
                </li>
              </ul>
            </section>

            <section className="terms-section">
              <h2>6. Cookies &amp; Local Storage</h2>
              <p>
                RateMyHusky does not use tracking cookies. During the Google OAuth sign-in
                flow, a short-lived, <code>httpOnly</code> cookie may be set to facilitate
                the authentication handshake; it is not used for tracking and is cleared after
                sign-in completes.
              </p>
              <p>
                <code>localStorage</code> is used to store your JWT session token and browser
                preferences (theme, view mode). This data stays on your device and is never
                synced to our servers.
              </p>
            </section>

            <section className="terms-section">
              <h2>7. Your Rights &amp; Choices</h2>
              <p>Because we do not maintain a persistent user database, your data controls are simple:</p>
              <ul>
                <li>
                  <strong>Sign out</strong> at any time to immediately delete your JWT token
                  from your browser.
                </li>
                <li>
                  <strong>Clear localStorage</strong> in your browser settings to remove your
                  session token and any stored preferences.
                </li>
                <li>
                  There is no account to delete. Once your token is cleared, no personal data
                  remains in our systems.
                </li>
              </ul>
            </section>

            <section className="terms-section">
              <h2>8. Children's Privacy</h2>
              <p>
                RateMyHusky is intended for Northeastern University students and is not directed
                at children under the age of 13. We do not knowingly collect personal information
                from children under 13. If you believe a child has provided us with personal
                information, please contact us using the feedback form.
              </p>
            </section>

            <section className="terms-section">
              <h2>9. Changes to This Policy</h2>
              <p>
                We may update this Privacy Policy from time to time. The effective date at the
                top of this page will be updated when changes are made. Continued use of
                RateMyHusky after changes are posted constitutes your acceptance of the
                revised Policy.
              </p>
            </section>

            <section className="terms-section terms-section--last">
              <h2>10. Contact</h2>
              <p>
                If you have questions about this Privacy Policy or want to report a concern,
                please use the feedback form available at the bottom-right of any page on
                RateMyHusky.
              </p>
            </section>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
};

export default Privacy;
