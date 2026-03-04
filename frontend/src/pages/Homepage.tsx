/**
 * Homepage.jsx
 * The main landing page of the application, featuring a search bar and navigation.
 * This component serves as the entry point for users to access the application's features.
 */

import Navbar from '../components/Navbar';
import SearchBar from '../components/SearchBar';
import Footer from '../components/Footer';
import FeedbackTab from '../components/FeedbackTab';
import './Homepage.css';

const Homepage = () => {
  return (
    <div className="homepage">
      <Navbar />

      <main className="homepage-hero">
        <SearchBar />
      </main>

      <Footer />
      <FeedbackTab />
    </div>
  );
};

export default Homepage;