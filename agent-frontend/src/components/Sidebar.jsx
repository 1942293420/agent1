import React from 'react';

const NAV_ITEMS = [
  { key:'dashboard', label:'仪表盘', shortLabel:'DASH', icon: <svg viewBox="0 0 20 20" fill="none"><rect x="2" y="2" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.5"/><rect x="11" y="2" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.5"/><rect x="2" y="11" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.5"/><rect x="11" y="11" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.5"/></svg> },
  { key:'agents', label:'Agent 管理', shortLabel:'AGENT', icon: <svg viewBox="0 0 20 20" fill="none"><circle cx="10" cy="7" r="3" stroke="currentColor" strokeWidth="1.5"/><path d="M4 17c0-3.3 2.7-6 6-6s6 2.7 6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg> },
  { key:'tasks', label:'任务管理', shortLabel:'TASK', icon: <svg viewBox="0 0 20 20" fill="none"><path d="M3 5h14M3 10h14M3 15h8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/><circle cx="15" cy="15" r="3" stroke="currentColor" strokeWidth="1.5"/></svg> },
  { key:'skills', label:'Skill 库', shortLabel:'SKILL', icon: <svg viewBox="0 0 20 20" fill="none"><path d="M10 2l2.4 4.8 5.3.8-3.8 3.7.9 5.2L10 14l-4.8 2.5.9-5.2L2.3 7.6l5.3-.8z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/></svg> },
  { key:'memory', label:'记忆管理', shortLabel:'MEM', icon: <svg viewBox="0 0 20 20" fill="none"><ellipse cx="10" cy="7" rx="7" ry="3" stroke="currentColor" strokeWidth="1.5"/><path d="M3 7v3c0 1.7 3.1 3 7 3s7-1.3 7-3V7" stroke="currentColor" strokeWidth="1.5"/></svg> },
  { key:'sessions', label:'会话中心', shortLabel:'CHAT', icon: <svg viewBox="0 0 20 20" fill="none"><path d="M2 5a2 2 0 012-2h12a2 2 0 012 2v8a2 2 0 01-2 2H7l-3 3v-3H4a2 2 0 01-2-2V5z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/></svg> },
  { key:'tokens', label:'Tokens', shortLabel:'TKNS', icon: <svg viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="7" stroke="currentColor" strokeWidth="1.5"/><path d="M10 6v4l3 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg> },
];
const SYS_ITEMS = [
  { key:'workers', label:'Worker', shortLabel:'WORK', icon: <svg viewBox="0 0 20 20" fill="none"><rect x="3" y="3" width="14" height="14" rx="2" stroke="currentColor" strokeWidth="1.5"/><circle cx="10" cy="10" r="3" stroke="currentColor" strokeWidth="1.5"/></svg> },
  { key:'cron', label:'定时任务', shortLabel:'CRON', icon: <svg viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="7" stroke="currentColor" strokeWidth="1.5"/><path d="M10 5v5l3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg> },
  { key:'logs', label:'运行日志', shortLabel:'LOGS', icon: <svg viewBox="0 0 20 20" fill="none"><rect x="3" y="3" width="14" height="14" rx="2" stroke="currentColor" strokeWidth="1.5"/><path d="M7 7h6M7 10h4M7 13h5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg> },
  { key:'settings', label:'系统设置', shortLabel:'CONF', icon: <svg viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="2.5" stroke="currentColor" strokeWidth="1.5"/><path d="M10 2v2M10 16v2M2 10h2M16 10h2M4.2 4.2l1.4 1.4M14.4 14.4l1.4 1.4M4.2 15.8l1.4-1.4M14.4 5.6l1.4-1.4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg> },
];

export default function Sidebar({ view, onViewChange, collapsed, onToggle, mobileOpen, onMobileOpen, workers }) {
  const [time, setTime] = React.useState('');
  React.useEffect(() => {
    setTime(new Date().toTimeString().slice(0,8));
    const id = setInterval(() => setTime(new Date().toTimeString().slice(0,8)), 1000);
    return () => clearInterval(id);
  }, []);

  const activeWorkers = workers.filter(w => w.status === 'active').length;

  const renderItems = (items) => items.map(item => (
    <a key={item.key} className={`nav-item${view === item.key ? ' active' : ''}`}
      data-label={item.shortLabel || item.label.slice(0,4)}
      onClick={e => { e.preventDefault(); onViewChange(item.key); }}
      aria-current={view === item.key ? 'page' : undefined}>
      <span className="nav-icon">{item.icon}</span>
      <span className="nav-label">{item.label}</span>
    </a>
  ));

  return (
    <aside className={`sidebar${collapsed ? ' collapsed' : ''}${mobileOpen ? ' mobile-open' : ''}`} role="navigation" aria-label="主导航">
      <div className="sidebar-header">
        <div className="logo-mark" aria-hidden="true">
          <svg viewBox="0 0 32 32" fill="none">
            <polygon points="16,2 30,10 30,22 16,30 2,22 2,10" fill="none" stroke="#00d4ff" strokeWidth="1.5"/>
            <polygon points="16,8 24,13 24,19 16,24 8,19 8,13" fill="none" stroke="#00d4ff" strokeWidth="1" opacity="0.5"/>
            <circle cx="16" cy="16" r="3" fill="#00d4ff"/>
          </svg>
        </div>
        <div className="logo-text">
          <span className="logo-name">AgentOS</span>
          <span className="logo-version">v2.4.1</span>
        </div>
        <button className="sidebar-toggle" onClick={onToggle} aria-label="折叠侧边栏">
          <svg viewBox="0 0 16 16" fill="none"><path d="M10 3L5 8L10 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
        </button>
      </div>
      <div className="system-status">
        <div className="status-dot active" />
        <span className="status-text">系统运行中</span>
        <span className="status-time">{time}</span>
      </div>
      <nav className="nav-menu">
        <div className="nav-section-label">主功能</div>
        {renderItems(NAV_ITEMS)}
        <div className="nav-section-label" style={{marginTop:8}}>系统</div>
        {renderItems(SYS_ITEMS)}
      </nav>
      <div className="sidebar-footer">
        <div className="resource-label">Worker 在线</div>
        <div className="resource-bar"><div className="resource-fill cpu" style={{width:`${Math.min(activeWorkers * 25, 100)}%`}} /></div>
        <div style={{fontSize:10,color:'var(--text-muted)',marginBottom:8}}>{activeWorkers}/{workers.length} 活跃</div>
        <div className="user-area">
          <div className="user-avatar">A</div>
          <div className="user-info">
            <span className="user-name">Admin</span>
            <span className="user-role">超级管理员</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
