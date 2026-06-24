import React from "react";
import ChatPage from "./pages/ChatPage";
import "./App.css";

function App() {
  return (
    <div className="App">
      <nav className="navbar">
        <div className="navbar-brand">
          <h1>SupremeAI 2.0</h1>
        </div>
        <div className="navbar-menu">
          <button className="nav-btn active">Chat</button>
          <button className="nav-btn">Skills</button>
          <button className="nav-btn">Evolution</button>
          <button className="nav-btn">Admin</button>
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
          <ChatPage />
        </main>
      </div>
    </div>
  );
}

export default App;

