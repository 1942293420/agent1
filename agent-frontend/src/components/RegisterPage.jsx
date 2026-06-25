import React, { useState } from 'react';

const CSS = `
.register-page {
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: #0f1724;
  position: relative;
  overflow: hidden;
}
.register-bg-grid {
  position: fixed; inset: 0; pointer-events: none;
  background-image: linear-gradient(rgba(0,212,255,0.03) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(0,212,255,0.03) 1px, transparent 1px);
  background-size: 40px 40px;
}
.register-card {
  position: relative; z-index: 1;
  width: 380px; max-width: 92vw;
  background: rgba(20,30,46,0.85);
  backdrop-filter: blur(24px);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 16px;
  padding: 40px 36px;
  box-shadow: 0 0 0 1px rgba(0,0,0,0.3), 0 8px 32px rgba(0,0,0,0.5);
  animation: regIn 0.5s ease;
}
@keyframes regIn {
  from { opacity: 0; transform: translateY(12px) scale(0.98); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}
.register-header {
  text-align: center; margin-bottom: 28px;
}
.register-header h2 {
  font-family: 'Inter', system-ui, sans-serif;
  font-size: 20px; font-weight: 600; color: #e8f0fe;
  margin-bottom: 6px;
}
.register-header p {
  font-size: 13px; color: #8ba0b8;
}
.register-field {
  margin-bottom: 16px;
}
.register-field label {
  display: block; font-size: 12px; font-weight: 500; color: #8ba0b8;
  margin-bottom: 6px; letter-spacing: 0.02em;
}
.register-field input {
  width: 100%; padding: 10px 14px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 8px;
  color: #e8f0fe; font-size: 15px;
  font-family: 'Inter', system-ui, sans-serif;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.register-field input:focus {
  border-color: rgba(0,212,255,0.5);
  box-shadow: 0 0 0 3px rgba(0,212,255,0.08);
}
.register-field input::placeholder { color: #4d6178; }

.register-error {
  background: rgba(226,75,74,0.1);
  border: 1px solid rgba(226,75,74,0.25);
  border-radius: 8px;
  padding: 10px 14px; color: #ff6b6b; font-size: 13px;
  margin-bottom: 16px;
  animation: regShake 0.4s ease;
}
@keyframes regShake {
  0%,100% { transform: translateX(0); }
  25% { transform: translateX(-4px); }
  75% { transform: translateX(4px); }
}
.register-success {
  background: rgba(29,158,117,0.1);
  border: 1px solid rgba(29,158,117,0.25);
  border-radius: 8px;
  padding: 16px; color: #4ade80; font-size: 14px;
  margin-bottom: 16px; text-align: center; line-height: 1.6;
}

.register-btn {
  width: 100%; padding: 11px 0;
  background: #00d4ff; border: none; border-radius: 8px;
  color: #0f1724; font-size: 15px; font-weight: 600;
  font-family: 'Inter', system-ui, sans-serif;
  cursor: pointer;
  transition: background 0.2s, transform 0.1s, box-shadow 0.2s;
  margin-top: 4px;
}
.register-btn:hover {
  background: #33ddff;
  box-shadow: 0 0 20px rgba(0,212,255,0.25);
}
.register-btn:active { transform: scale(0.98); }
.register-btn:disabled { opacity: 0.5; cursor: not-allowed; box-shadow: none; }

.register-back {
  display: block; text-align: center; margin-top: 20px;
  font-size: 13px; color: #8ba0b8; cursor: pointer;
  background: none; border: none;
  font-family: 'Inter', system-ui, sans-serif;
  transition: color 0.2s;
  width: 100%;
}
.register-back:hover { color: #e8f0fe; }
`;

export default function RegisterPage({ onBack }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [password2, setPassword2] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username.trim()) { setError('请输入用户名'); return; }
    if (username.trim().length < 3) { setError('用户名至少 3 个字符'); return; }
    if (!password) { setError('请输入密码'); return; }
    if (password.length < 6) { setError('密码至少 6 个字符'); return; }
    if (password !== password2) { setError('两次密码不一致'); return; }

    setError('');
    setLoading(true);
    try {
      const res = await fetch('/api/auth/register/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username.trim(), password, password2 }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || '注册失败');
        return;
      }
      setSuccess(true);
    } catch (err) {
      setError('网络错误，请检查服务是否运行');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <style>{CSS}</style>
      <div className="register-page">
        <div className="register-bg-grid" />
        <div className="register-card">
          <div className="register-header">
            <h2>注册新账号</h2>
            <p>注册后需等待管理员审批</p>
          </div>

          {success ? (
            <div className="register-success">
              注册成功！<br/>
              请等待管理员审批通过后即可登录。
              <button className="register-back" onClick={onBack} style={{marginTop:12}}>
                返回登录
              </button>
            </div>
          ) : (
            <>
              {error && <div className="register-error">{error}</div>}
              <div className="register-field">
                <label>用户名</label>
                <input type="text" value={username} onChange={e => setUsername(e.target.value)}
                  placeholder="至少 3 个字符" autoFocus autoComplete="username" />
              </div>
              <div className="register-field">
                <label>密码</label>
                <input type="password" value={password} onChange={e => setPassword(e.target.value)}
                  placeholder="至少 6 个字符" autoComplete="new-password" />
              </div>
              <div className="register-field">
                <label>确认密码</label>
                <input type="password" value={password2} onChange={e => setPassword2(e.target.value)}
                  placeholder="再次输入密码" autoComplete="new-password" />
              </div>
              <button className="register-btn" onClick={handleSubmit} disabled={loading}>
                {loading ? '提交中...' : '注 册'}
              </button>
              <button className="register-back" onClick={onBack}>已有账号？返回登录</button>
            </>
          )}
        </div>
      </div>
    </>
  );
}
