import React, { useState, useRef, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useApp } from '../AppContext';
import { useAuth } from '../AuthContext';

const NAV_ITEMS = [
  { key: 'dashboard', label: '仪表盘', icon: '📊' },
  { key: 'agents', label: '运行中心', icon: '🖥' },
  { key: 'tasks', label: '任务与用量', icon: '📋' },
  { key: 'sessions', label: '会话中心', icon: '💬' },
  { key: 'skills', label: 'Skill 库', icon: '⭐' },
  { key: 'memory', label: '记忆管理', icon: '🧠' },
];

export default function Topbar({ viewLabels, onMobileOpen }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const { addToast } = useApp();
  const currentView = location.pathname.replace('/', '') || 'dashboard';
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef(null);

  useEffect(() => {
    const handler = e => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleLogout = async () => {
    await logout();
    navigate('/');
  };

  const navTo = (key) => {
    navigate('/' + key);
    setDropdownOpen(false);
  };

  // Get user display info from localStorage or AuthContext
  const profile = JSON.parse(localStorage.getItem('agentos_profile') || '{}');
  const displayName = profile.nickname || user?.username || '用户';
  const avatarUrl = profile.avatarUrl || null;
  const initials = displayName.slice(0, 2).toUpperCase();

  return (
    <header className="topbar-v2">
      {/* Left: Logo + Nav */}
      <div className="topbar-v2-left">
        <button className="mobile-menu-btn" onClick={onMobileOpen} aria-label="菜单">
          <svg viewBox="0 0 20 20" fill="none" width="20" height="20"><path d="M3 5h14M3 10h14M3 15h14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
        </button>

        <div className="topbar-v2-logo" onClick={() => navigate('/')}>
          <svg viewBox="0 0 32 32" fill="none" width="28" height="28">
            <polygon points="16,2 30,10 30,22 16,30 2,22 2,10" fill="none" stroke="#00d4ff" strokeWidth="1.5"/>
            <circle cx="16" cy="16" r="3" fill="#00d4ff"/>
          </svg>
          <span className="topbar-v2-brand">AgentOS</span>
        </div>

        <nav className="topbar-v2-nav">
          {NAV_ITEMS.map(item => (
            <button
              key={item.key}
              className={`topbar-v2-nav-item${currentView === item.key ? ' active' : ''}`}
              onClick={() => navTo(item.key)}
            >
              <span className="topbar-v2-nav-icon">{item.icon}</span>
              <span className="topbar-v2-nav-label">{item.label}</span>
            </button>
          ))}
        </nav>
      </div>

      {/* Right: User area */}
      <div className="topbar-v2-right" ref={dropdownRef}>
        <button
          className="topbar-v2-user"
          onClick={() => setDropdownOpen(prev => !prev)}
        >
          {avatarUrl ? (
            <img src={avatarUrl} alt={displayName} className="topbar-v2-avatar" />
          ) : (
            <div className="topbar-v2-avatar-placeholder">{initials}</div>
          )}
          <span className="topbar-v2-username">{displayName}</span>
          <svg viewBox="0 0 12 12" fill="none" width="10" height="10"><path d="M3 4l3 3 3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
        </button>

        {dropdownOpen && (
          <div className="topbar-v2-dropdown">
            <button className="topbar-v2-dropdown-item" onClick={() => navTo('profile')}>
              👤 个人资料
            </button>
            <button className="topbar-v2-dropdown-item" onClick={() => navTo('settings')}>
              ⚙️ 系统设置
            </button>
            <div className="topbar-v2-dropdown-divider" />
            <button className="topbar-v2-dropdown-item topbar-v2-dropdown-danger" onClick={handleLogout}>
              🚪 退出登录
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
