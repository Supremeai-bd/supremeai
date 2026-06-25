import { BrowserRouter as Router, Routes, Route, NavLink } from 'react-router-dom';
import ChatPage from './pages/ChatPage';
import SkillsPage from './pages/SkillsPage';
import EvolutionPage from './pages/EvolutionPage';
import AdminPage from './pages/AdminPage';
import LoginPage from './pages/LoginPage';
import './App.css';
import { useAuthStore } from './stores/authStore';

const NavButton = ({ to, label }: { to: string; label: string }) => (
  <NavLink to={to} className={({ isActive }) => `nav-btn ${isActive ? 'active' : ''}`}>
    {label}
  </NavLink>
);

function App() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const logout = useAuthStore((state) => state.logout);

  return (
    <Router>
      <div className="App">
        <nav className="navbar">
          <div className="navbar-brand">
            <h1>SupremeAI 2.0</h1>
          </div>
          <div className="navbar-menu">
            {isAuthenticated ? (
              <>
                <NavButton to="/" label="Chat" />
                <NavButton to="/skills" label="Skills" />
                <NavButton to="/evolution" label="Evolution" />
                <NavButton to="/admin" label="Admin" />
                <button className="nav-btn" onClick={logout}>
                  Logout
                </button>
              </>
            ) : (
              <NavLink to="/login" className={({ isActive }) => `nav-btn ${isActive ? 'active' : ''}`}>
                Login
              </NavLink>
            )}
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
              </ul>
            </div>
          </aside>
          <main className="main-content">
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/" element={isAuthenticated ? <ChatPage /> : <LoginPage />} />
              <Route path="/skills" element={isAuthenticated ? <SkillsPage /> : <LoginPage />} />
              <Route path="/evolution" element={isAuthenticated ? <EvolutionPage /> : <LoginPage />} />
              <Route path="/admin" element={isAuthenticated ? <AdminPage /> : <LoginPage />} />
              <Route path="*" element={isAuthenticated ? <ChatPage /> : <LoginPage />} />
            </Routes>
          </main>
        </div>
      </div>
    </Router>
  );
}

export default App;