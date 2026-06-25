import React, { useState } from 'react';

const CSS = `
.login-page {
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: #0f1724;
  position: relative;
  overflow: hidden;
}
.login-page::before {
  content: '';
  position: fixed;
  inset: 0;
  background: radial-gradient(circle at 50% 30%, rgba(0,212,255,0.06) 0%, transparent 60%);
  pointer-events: none;
}
.login-bg-grid {
  position: fixed; inset: 0; pointer-events: none;
  background-image: linear-gradient(rgba(0,212,255,0.03) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(0,212,255,0.03) 1px, transparent 1px);
  background-size: 40px 40px;
}
.login-card {
  position: relative;
  z-index: 1;
  width: 380px;
  max-width: 92vw;
  background: rgba(20,30,46,0.85);
  backdrop-filter: blur(24px);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 16px;
  padding: 40px 36px;
  box-shadow: 0 0 0 1px rgba(0,0,0,0.3), 0 8px 32px rgba(0,0,0,0.5);
  animation: loginIn 0.5s ease;
}
@keyframes loginIn {
  from { opacity: 0; transform: translateY(12px) scale(0.98); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}

.login-logo {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 32px;
  justify-content: center;
}
.login-logo svg { width: 36px; height: 36px; flex-shrink: 0; }
.login-logo h1 {
  font-family: 'Inter', system-ui, sans-serif;
  font-size: 22px;
  font-weight: 600;
  color: #e8f0fe;
  letter-spacing: -0.3px;
}

.login-subtitle {
  text-align: center;
  color: #8ba0b8;
  font-size: 13px;
  margin-bottom: 28px;
  line-height: 1.5;
}

.login-field {
  margin-bottom: 18px;
}
.login-field label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: #8ba0b8;
  margin-bottom: 6px;
  letter-spacing: 0.02em;
}
.login-field input {
  width: 100%;
  padding: 10px 14px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 8px;
  color: #e8f0fe;
  font-size: 15px;
  font-family: 'Inter', system-ui, sans-serif;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.login-field input:focus {
  border-color: rgba(0,212,255,0.5);
  box-shadow: 0 0 0 3px rgba(0,212,255,0.08);
}
.login-field input::placeholder { color: #4d6178; }

.login-error {
  background: rgba(226,75,74,0.1);
  border: 1px solid rgba(226,75,74,0.25);
  border-radius: 8px;
  padding: 10px 14px;
  color: #ff6b6b;
  font-size: 13px;
  margin-bottom: 18px;
  animation: loginShake 0.4s ease;
}
@keyframes loginShake {
  0%,100% { transform: translateX(0); }
  25% { transform: translateX(-4px); }
  75% { transform: translateX(4px); }
}

.login-btn {
  width: 100%;
  padding: 11px 0;
  background: #00d4ff;
  border: none;
  border-radius: 8px;
  color: #0f1724;
  font-size: 15px;
  font-weight: 600;
  font-family: 'Inter', system-ui, sans-serif;
  cursor: pointer;
  transition: background 0.2s, transform 0.1s, box-shadow 0.2s;
  margin-top: 4px;
}
.login-btn:hover {
  background: #33ddff;
  box-shadow: 0 0 20px rgba(0,212,255,0.25);
}
.login-btn:active { transform: scale(0.98); }
.login-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  box-shadow: none;
}

.login-footer {
  text-align: center;
  margin-top: 24px;
  color: #4d6178;
  font-size: 11px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: center;
}
.login-register-link {
  font-size: 13px;
  color: #00d4ff;
  cursor: pointer;
  background: none;
  border: none;
  font-family: 'Inter', system-ui, sans-serif;
  transition: color 0.2s;
}
.login-register-link:hover { color: #33ddff; }
`;

export default function LoginPage({ onLogin, onGoRegister }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      setError('请输入用户名和密码');
      return;
    }
    setError('');
    setLoading(true);
    try {
      const res = await fetch('/api/auth/login/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username.trim(), password }),
        credentials: 'include',
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || '登录失败');
        return;
      }
      onLogin(data.user);
    } catch (err) {
      setError('网络错误，请检查服务是否运行');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <style>{CSS}</style>
      <div className="login-page">
        <div className="login-bg-grid" />
        <div className="login-card">
          <div className="login-logo">
            <svg viewBox="0 0 36 36" fill="none">
              <rect width="36" height="36" rx="10" fill="rgba(0,212,255,0.12)"/>
              <path d="M10 26V12l8 7-8 7z" fill="#00d4ff"/>
              <circle cx="24" cy="12" r="3" fill="#00d4ff" opacity="0.6"/>
              <circle cx="26" cy="22" r="2.5" fill="#00d4ff" opacity="0.4"/>
              <circle cx="20" cy="26" r="1.8" fill="#00d4ff" opacity="0.25"/>
            </svg>
            <h1>AgentOS</h1>
          </div>
          <p className="login-subtitle">多 Agent 协作平台 · 请登录后使用</p>

          {error && <div className="login-error">{error}</div>}

          <div className="login-field">
            <label>用户名</label>
            <input type="text" value={username} onChange={e => setUsername(e.target.value)}
              placeholder="请输入用户名" autoFocus autoComplete="username" />
          </div>
          <div className="login-field">
            <label>密码</label>
            <input type="password" value={password} onChange={e => setPassword(e.target.value)}
              placeholder="请输入密码" autoComplete="current-password" />
          </div>
          <button className="login-btn" type="submit" onClick={handleSubmit} disabled={loading}>
            {loading ? '登录中...' : '登 录'}
          </button>
          <div className="login-footer">
            <button className="login-register-link" onClick={onGoRegister}>还没有账号？立即注册</button>
            <span>AgentOS v2.0 · Multi-Agent Platform</span>
          </div>
        </div>
      </div>
    </>
  );
}
