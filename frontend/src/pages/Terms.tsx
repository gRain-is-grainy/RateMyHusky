import Footer from '../components/Footer';
import './Terms.css';

const Terms = () => {
  return (
    <div className="terms-page">
      <main className="terms-main">
        <div className="terms-shell">
          <header className="terms-header">
            <span className="terms-kicker">Legal</span>
            <h1>Terms &amp; Conditions</h1>
            <p className="terms-meta">Effective March 26, 2025 &middot; RateMyHusky</p>
          </header>

          <div className="terms-body">
            <section className="terms-section">
              <h2>1. About the Service</h2>
              <p>
                RateMyHusky is a read-only aggregator of professor and course information for
                Northeastern University students. Data displayed on this platform is sourced from
                RateMyProfessors and Northeastern University's TRACE course evaluation system; it
                is not submitted by users of this site.
              </p>
              <p>
                RateMyHusky is an independent student project and is not affiliated with,
                endorsed by, or officially connected to Northeastern University or RateMyProfessors.
              </p>
            </section>

            <section className="terms-section">
              <h2>2. Eligibility &amp; Access</h2>
              <p>
                Most content on RateMyHusky is publicly accessible without an account. However,
                access to TRACE course evaluation comments requires signing in with a valid
                Northeastern University Google account (<code>@husky.neu.edu</code>).
              </p>
              <p>
                By signing in, you confirm that you are authorized to use the Google account
                you provide. Access may be revoked at any time if the service is misused.
              </p>
            </section>

            <section className="terms-section">
              <h2>3. Authentication &amp; Account Data</h2>
              <p>
                Sign-in is handled through Google OAuth 2.0, restricted to <code>@husky.neu.edu</code> accounts.
                When you authenticate, Google provides your name, email address, and profile photo to RateMyHusky.
              </p>
              <p>
                This information is encoded in a JWT (JSON Web Token) that is stored in your
                browser's <code>localStorage</code>. The token expires after 7 days.
                RateMyHusky does not maintain a persistent server-side user database; no account
                record is stored beyond the duration of your session token. Signing out deletes
                the token from your browser.
              </p>
            </section>

            <section className="terms-section">
              <h2>4. Data We Collect</h2>
              <p>When you use RateMyHusky, the following data may be collected or stored:</p>
              <ul>
                <li>
                  <strong>From Google sign-in:</strong> your name, email address
                  (<code>@husky.neu.edu</code>), and profile photo, stored only in your
                  browser-side JWT token.
                </li>
                <li>
                  <strong>Browser preferences:</strong> your theme (dark/light) and catalog
                  view mode are saved to <code>localStorage</code> on your device only and
                  are never synced to our servers.
                </li>
                <li>
                  <strong>Anonymous usage data:</strong> Vercel Analytics and Vercel Speed
                  Insights collect anonymous page view and performance metrics. No personally
                  identifiable information is included.
                </li>
              </ul>
              <p>
                We do <strong>not</strong> log or store your search queries, which professor or
                course pages you viewed, or any other browsing activity on our servers.
              </p>
            </section>

            <section className="terms-section">
              <h2>5. Feedback Form</h2>
              <p>
                RateMyHusky includes a feedback form that accepts a message type, description,
                and an optional email address. At this time, submissions from this form are
                not transmitted to or stored on our servers. If this changes, these Terms will
                be updated accordingly.
              </p>
            </section>

            <section className="terms-section">
              <h2>6. Third-Party Services</h2>
              <p>RateMyHusky integrates with the following third-party services:</p>
              <ul>
                <li>
                  <strong>Google OAuth 2.0</strong>: handles authentication. Your use of
                  Google sign-in is subject to Google's Terms of Service and Privacy Policy.
                </li>
                <li>
                  <strong>Vercel Analytics &amp; Speed Insights</strong>: collects anonymous
                  performance and usage data to help improve the service.
                </li>
                <li>
                  <strong>RateMyProfessors</strong>: professor ratings and review data are
                  sourced from RateMyProfessors. This data remains subject to RateMyProfessors'
                  own terms and usage policies.
                </li>
                <li>
                  <strong>Northeastern TRACE</strong>: course evaluation scores and comments
                  are sourced from Northeastern University's TRACE system.
                </li>
              </ul>
            </section>

            <section className="terms-section">
              <h2>7. Intellectual Property &amp; Data Sources</h2>
              <p>
                Review content and ratings sourced from RateMyProfessors remain subject to
                RateMyProfessors' intellectual property rights and terms of use. TRACE evaluation
                data is the property of Northeastern University.
              </p>
              <p>
                You may not scrape, bulk-download, reproduce, or redistribute the aggregated
                data presented on RateMyHusky for any commercial or systematic purpose.
              </p>
            </section>

            <section className="terms-section">
              <h2>8. Acceptable Use</h2>
              <p>By using RateMyHusky, you agree not to:</p>
              <ul>
                <li>Use automated scripts, bots, or crawlers to access the service (rate limiting is enforced)</li>
                <li>Attempt to access, steal, or forge other users' session tokens or credentials</li>
                <li>Use data from this platform to harass, target, or harm any individual professor or instructor</li>
                <li>Attempt to reverse-engineer, overload, or otherwise disrupt the service</li>
              </ul>
            </section>

            <section className="terms-section">
              <h2>9. No Warranties &amp; Data Accuracy</h2>
              <p>
                Professor ratings, review comments, and TRACE scores are sourced from external
                systems and may be incomplete, outdated, or inaccurate. RateMyHusky makes no
                guarantees about the accuracy, completeness, or timeliness of any data displayed
                on the platform.
              </p>
              <p>
                We encourage you to use RateMyHusky as one of several resources when making
                course registration decisions, not as the sole basis for those decisions.
              </p>
            </section>

            <section className="terms-section">
              <h2>10. Limitation of Liability</h2>
              <p>
                RateMyHusky is provided "as-is" without warranties of any kind, express or
                implied. To the fullest extent permitted by law, RateMyHusky and its developers
                are not liable for any damages arising from your use of or inability to use
                the service, including decisions made based on data presented on this platform.
              </p>
            </section>

            <section className="terms-section">
              <h2>11. Changes to These Terms</h2>
              <p>
                We may update these Terms from time to time. The effective date at the top of
                this page will be updated when changes are made. Continued use of RateMyHusky
                after changes are posted constitutes your acceptance of the revised Terms.
              </p>
            </section>

            <section className="terms-section terms-section--last">
              <h2>12. Contact</h2>
              <p>
                If you have questions about these Terms or want to report an issue, please use
                the feedback form available at the bottom-right of any page on RateMyHusky.
              </p>
            </section>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
};

export default Terms;
