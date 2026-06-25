import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../AuthContext';

export default function Topbar({ view, viewLabels, addToast, onMobileOpen }) {
  const [searchVal, setSearchVal] = React.useState('');
  const { user, logout } = useAuth();
  const [notifOpen, setNotifOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [notifLoading, setNotifLoading] = useState(false);
  const notifRef = useRef(null);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = e => {
      if (notifRef.current && !notifRef.current.contains(e.target)) {
        setNotifOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const fetchNotifications = async () => {
    setNotifLoading(true);
    try {
      const res = await fetch('/api/tasks/?ordering=-created_at&page_size=5');
      if (res.ok) {
        const data = await res.json();
        const items = (data.results || []).map(t => ({
          id: t.id,
          text: `任务 #${t.id}: ${(t.title || t.description || '').slice(0, 40)}`,
          status: t.status,
          time: t.created_at,
        }));
        setNotifications(items);
      }
    } catch (e) {
      // ignore
    } finally {
      setNotifLoading(false);
    }
  };

  const toggleNotif = () => {
    if (!notifOpen) {
      fetchNotifications();
    }
    setNotifOpen(prev => !prev);
  };

  const handleSearch = e => {
    if (e.key === 'Enter' && searchVal.trim()) {
      addToast(`全局搜索暂未实现，请使用侧边栏导航`);
      setSearchVal('');
    }
  };

  const handleLogout = async () => {
    await logout();
  };

  return (
    <header className="topbar">
      <div className="topbar-left">
        <button className="mobile-menu-btn" onClick={onMobileOpen} aria-label="打开菜单">
          <svg viewBox="0 0 20 20" fill="none"><path d="M3 5h14M3 10h14M3 15h14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
        </button>
        <div className="breadcrumb">
          <span className="breadcrumb-home" onClick={() => window.location.hash = ''}>AgentOS</span>
          <svg viewBox="0 0 12 12" fill="none" width="12" height="12"><path d="M4 2l4 4-4 4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>
          <span className="breadcrumb-current">{viewLabels[view]||view}</span>
        </div>
      </div>
      <div className="topbar-right">
        <div className="search-box">
          <svg viewBox="0 0 16 16" fill="none" width="14" height="14"><circle cx="7" cy="7" r="4.5" stroke="currentColor" strokeWidth="1.3"/><path d="M10.5 10.5l2.5 2.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></svg>
          <input type="text" placeholder="搜索 Agent、任务、技能..." value={searchVal} onChange={e => setSearchVal(e.target.value)} onKeyDown={handleSearch} aria-label="搜索" />
          <kbd>⌘K</kbd>
        </div>

        {/* Notification bell */}
        <div className="topbar-notif-wrap" ref={notifRef}>
          <button className="topbar-btn" title="通知" onClick={toggleNotif}>
            <svg viewBox="0 0 20 20" fill="none" width="18" height="18"><path d="M10 2a6 6 0 00-6 6v3l-2 2v1h16v-1l-2-2V8a6 6 0 00-6-6z" stroke="currentColor" strokeWidth="1.5"/><path d="M10 18a2 2 0 002-2H8a2 2 0 002 2z" stroke="currentColor" strokeWidth="1.5"/></svg>
            {notifications.length > 0 && <span className="topbar-badge">{notifications.length}</span>}
          </button>
          {notifOpen && (
            <div className="notif-dropdown">
              <div className="notif-header">最近任务动态</div>
              {notifLoading ? (
                <div className="notif-empty">加载中...</div>
              ) : notifications.length === 0 ? (
                <div className="notif-empty">暂无最近任务</div>
              ) : (
                notifications.map(n => (
                  <div key={n.id} className="notif-item">
                    <div className={`notif-dot ${n.status === 'completed' ? 'done' : n.status === 'failed' ? 'fail' : 'pending'}`} />
                    <div className="notif-text">{n.text}</div>
                    <div className="notif-time">{n.time ? new Date(n.time).toLocaleTimeString('zh-CN', {hour:'2-digit',minute:'2-digit'}) : ''}</div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        {/* User + logout */}
        {user && (
          <div className="topbar-user">
            <span className="topbar-username">{user.username}</span>
            <button className="topbar-logout-btn" onClick={handleLogout} title="退出登录">
              <svg viewBox="0 0 16 16" fill="none" width="15" height="15">
                <path d="M6 2H3a1 1 0 00-1 1v10a1 1 0 001 1h3M11 11l3-3-3-3M14 8H6" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
              </svg>
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
