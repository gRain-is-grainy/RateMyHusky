import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Homepage from './pages/Homepage';
import Professor from './pages/Professor';
import ProfessorCatalog from './pages/ProfessorCatalog';
import NotFound from './pages/NotFound';
import Navbar from './components/Navbar';
import './App.css';

function App() {
  return (
    <Router>
      <Navbar />
      <Routes>
        <Route path="/" element={<Homepage />} />
        <Route path="/professors" element={<ProfessorCatalog />} />
        <Route path="/professors/:slug" element={<Professor />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Router>
  );
}

export default App;