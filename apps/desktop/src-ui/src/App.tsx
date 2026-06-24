import { BrowserRouter as Router, Routes, Route, useNavigate } from 'react-router-dom';
import ChatPage from './pages/ChatPage';
import SkillsPage from './pages/SkillsPage';
import EvolutionPage from './pages/EvolutionPage';
import AdminPage from './pages/AdminPage';
import './App.css';

const NavButton = ({ to, label, isActive }: { to: string; label: string; isActive: boolean }) => {
  const navigate = useNavigate();
  const handleClick = () => {
    navigate(to);
  };
  return (
    <button
      className={`nav-btn ${isActive ? 'active' : ''}`}
      onClick={handleClick}
    >
      {label}
    </button>
  );
};

function App() {
  return (
    <Router>
      <div className="App">
        <nav className="navbar">
          <div className="navbar-brand">
            <h1>SupremeAI 2.0</h1>
          </div>
          <div className="navbar-menu">
            <NavButton to="/" label="Chat" isActive={true} />
            <NavButton to="/skills" label="Skills" isActive={false} />
            <NavButton to="/evolution" label="Evolution" isActive={false} />
            <NavButton to="/admin" label="Admin" isActive={false} />
          </div>
        </nav>
        <div className="app-content">
          <aside className="sidebar">
            <div className="sidebar-section">
              <h3>History</h3>
              <ul>
                <li>New Chat</li>
                <li>Previous Session</li>
              </ul>
            </div>
            <div className="sidebar-section">
              <h3>Skills</h3>
              <ul>
                <li>Web Scraper</li>
                <li>Code Generator</li>
                <li>Data Analyzer</li>
              </ul
            </div>
          </aside>
          <main className="main-content">
            <Routes>
              <Route path="/" element={<ChatPage />} />
              <Route path="/skills" element={<SkillsPage />} />
              <Route path="/evolution" element={<EvolutionPage />} />
              <Route path="/admin" element={<AdminPage />} />
            </Routes>
          </main>
        </div>
      </div>
    </Router>
  );
}

export default App;