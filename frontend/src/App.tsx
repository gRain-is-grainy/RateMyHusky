import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Homepage from './pages/Homepage';
import Professor from './pages/Professor';
import './App.css';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Homepage />} />
        <Route path="/professors/:slug" element={<Professor />} />
      </Routes>
    </Router>
  );
}

export default App;