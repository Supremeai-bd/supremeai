import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { supremeApi } from '../services/api';
import { useAuthStore } from '../stores/authStore';

const LoginPage: React.FC = () => {
  const [token, setToken] = useState('');
  const [error, setError] = useState<string | null>(null);
  const login = useAuthStore((state) => state.login);
  const navigate = useNavigate();

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!token.trim()) {
      setError('Please enter a valid token.');
      return;
    }

    try {
      supremeApi.login(token.trim());
      login(token.trim());
      setError(null);
      navigate('/');
    } catch (err) {
      setError('Unable to save token. Please try again.');
      console.error(err);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <h1>Log In</h1>
        <p>Provide your API token to access SupremeAI features.</p>
        <form onSubmit={handleSubmit}>
          <div className="input-group">
            <input
              type="text"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="Enter API token"
            />
          </div>
          {error && <p className="error-text">{error}</p>}
          <button type="submit" className="nav-btn">
            Sign In
          </button>
        </form>
      </div>
    </div>
  );
};

export default LoginPage;
