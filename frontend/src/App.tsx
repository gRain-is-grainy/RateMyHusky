import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import Homepage from './pages/Homepage';
import Professor from './pages/Professor';
import ProfessorCatalog from './pages/ProfessorCatalog';
import Compare from './pages/Compare';
import NotFound from './pages/NotFound';
import Navbar from './components/Navbar';
import FeedbackTab from './components/FeedbackTab';
import './App.css';

function App() {
  return (
    <AuthProvider>
      <Router>
        <Navbar />
        <Routes>
          <Route path="/" element={<Homepage />} />
          <Route path="/professors" element={<ProfessorCatalog />} />
          <Route path="/professors/:slug" element={<Professor />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
        <FeedbackTab />
      </Router>
    </AuthProvider>
  );
}

export default App;