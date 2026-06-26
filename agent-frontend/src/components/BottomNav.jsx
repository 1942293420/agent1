import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';

const NAV_ITEMS = [
  { key: 'dashboard', label: '首页', icon: '🏠', path: '/dashboard' },
  { key: 'tasks', label: '任务', icon: '📋', path: '/tasks' },
  { key: 'sessions', label: '会话', icon: '💬', path: '/sessions' },
  { key: 'skills', label: '技能', icon: '⭐', path: '/skills' },
  { key: 'profile', label: '我的', icon: '👤', path: '/profile' },
];

export default function BottomNav() {
  const loc = useLocation();

  return (
    <nav className="bottom-nav" role="navigation" aria-label="底部导航">
      {NAV_ITEMS.map(item => {
        const active = loc.pathname === item.path || (item.path !== '/' && loc.pathname.startsWith(item.path));
        return (
          <NavLink key={item.key} to={item.path}
            className={`bottom-nav-item${active ? ' active' : ''}`}
            aria-current={active ? 'page' : undefined}>
            <span className="bottom-nav-icon">{item.icon}</span>
            <span className="bottom-nav-label">{item.label}</span>
          </NavLink>
        );
      })}
    </nav>
  );
}
