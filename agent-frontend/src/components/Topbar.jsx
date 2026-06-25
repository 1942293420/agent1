import React, { useState, useRef, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useApp } from '../AppContext';
import { useAuth } from '../AuthContext';

const NAV_ITEMS = [
  { key: 'dashboard', label: '仪表盘', icon: '📊' },
  { key: 'agents', label: 'Agent管理', icon: '🤖' },
  { key: 'tasks', label: '任务与用量', icon: '📋' },
  { key: 'sessions', label: '新建任务', icon: '💬' },
  { key: 'skills', label: 'Skill 库', icon: '⭐' },
  { key: 'memory', label: '记忆管理', icon: '🧠' },
];

const SYS_ITEMS = [
  { key: 'workers', label: 'Worker', icon: '🔧' },
  { key: 'cron', label: '定时任务', icon: '⏰' },
  { key: 'monitor', label: '系统监控', icon: '📈' },
  { key: 'logs', label: '运行日志', icon: '📝' },
];

export default function Topbar({ onMobileOpen }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const currentView = location.pathname.replace('/', '') || 'dashboard';
  const [menuOpen, setMenuOpen] = useState(false);
  const [sysOpen, setSysOpen] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);
  const menuRef = useRef(null);
  const sysTimer = useRef(null);

  useEffect(() => {
    const h = e => { if (menuRef.current && !menuRef.current.contains(e.target)) setMenuOpen(false); };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, []);

  const navTo = (k) => { navigate('/' + k); setMenuOpen(false); };

  const profile = JSON.parse(localStorage.getItem('agentos_profile') || '{}');
  const name = profile.nickname || user?.username || '用户';
  const avatarUrl = profile.avatarUrl || null;
  const initials = name.slice(0, 2).toUpperCase();

  const sysEnter = () => { clearTimeout(sysTimer.current); setSysOpen(true); };
  const sysLeave = () => { sysTimer.current = setTimeout(() => setSysOpen(false), 200); };

  return (
    <header className="topbar-v2">
      <div className="topbar-v2-left">
        <button className="mobile-menu-btn" onClick={() => setMobileNav(p => !p)} aria-label="菜单">
          <svg viewBox="0 0 20 20" fill="none" width="20" height="20"><path d="M3 5h14M3 10h14M3 15h14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
        </button>
        <div className="topbar-v2-logo" onClick={() => navigate('/')}>
          <svg viewBox="0 0 32 32" fill="none" width="28" height="28"><polygon points="16,2 30,10 30,22 16,30 2,22 2,10" fill="none" stroke="#00d4ff" strokeWidth="1.5"/><circle cx="16" cy="16" r="3" fill="#00d4ff"/></svg>
          <span className="topbar-v2-brand">AgentOS</span>
        </div>
        <nav className={`topbar-v2-nav${mobileNav ? ' mobile-open' : ''}`}>
          {NAV_ITEMS.map(item => (
            <button key={item.key} className={`topbar-v2-nav-item${currentView === item.key ? ' active' : ''}`} onClick={() => navTo(item.key)}>
              <span className="topbar-v2-nav-icon">{item.icon}</span>
              <span className="topbar-v2-nav-label">{item.label}</span>
            </button>
          ))}
          {/* System hover dropdown */}
          <div className="topbar-v2-sys-wrap" onMouseEnter={sysEnter} onMouseLeave={sysLeave}>
            <button className={`topbar-v2-nav-item${sysOpen ? ' active' : ''}`}>
              <span className="topbar-v2-nav-icon">⚙️</span>
              <span className="topbar-v2-nav-label">系统</span>
              <svg viewBox="0 0 12 12" fill="none" width="8" height="8"><path d="M3 4l3 3 3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
            </button>
            {sysOpen && (
              <div className="topbar-v2-dropdown topbar-v2-dropdown-sys" onMouseEnter={sysEnter} onMouseLeave={sysLeave}>
                {user?.is_staff && <button className="topbar-v2-dropdown-item" onClick={() => navTo('admin')}>👥 用户管理</button>}
                {SYS_ITEMS.map(item => (
                  <button key={item.key} className="topbar-v2-dropdown-item" onClick={() => navTo(item.key)}>{item.icon} {item.label}</button>
                ))}
              </div>
            )}
          </div>
        </nav>
      </div>

      <div className="topbar-v2-right" ref={menuRef}>
        <button className="topbar-v2-user" onClick={() => setMenuOpen(prev => !prev)}>
          {avatarUrl ? <img src={avatarUrl} alt="" className="topbar-v2-avatar"/> : <div className="topbar-v2-avatar-placeholder">{initials}</div>}
          <span className="topbar-v2-username">{name}</span>
          <svg viewBox="0 0 12 12" fill="none" width="10" height="10"><path d="M3 4l3 3 3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
        </button>
        {menuOpen && (
          <div className="topbar-v2-dropdown">
            <button className="topbar-v2-dropdown-item" onClick={() => navTo('profile')}>👤 个人资料</button>
            {user?.is_staff && <button className="topbar-v2-dropdown-item" onClick={() => navTo('admin')}>👥 用户管理</button>}
            <button className="topbar-v2-dropdown-item" onClick={() => navTo('workers')}>🔧 Worker</button>
            <button className="topbar-v2-dropdown-item" onClick={() => navTo('cron')}>⏰ 定时任务</button>
            <button className="topbar-v2-dropdown-item" onClick={() => navTo('monitor')}>📈 系统监控</button>
            <button className="topbar-v2-dropdown-item" onClick={() => navTo('logs')}>📝 运行日志</button>
            <div className="topbar-v2-dropdown-divider"/>
            <button className="topbar-v2-dropdown-item" onClick={() => navTo('settings')}>⚙️ 系统设置</button>
            <div className="topbar-v2-dropdown-divider"/>
            <button className="topbar-v2-dropdown-item topbar-v2-dropdown-danger" onClick={logout}>🚪 退出登录</button>
          </div>
        )}
      </div>
    </header>
  );
}
