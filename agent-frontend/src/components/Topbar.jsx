import React from 'react';

export default function Topbar({ view, viewLabels, onViewChange, addToast, onMobileOpen }) {
  const [searchVal, setSearchVal] = React.useState('');

  const handleSearch = e => {
    if (e.key === 'Enter' && searchVal.trim()) {
      addToast(`全局搜索："${searchVal}" — 找到 3 个相关结果`);
      setSearchVal('');
    }
  };

  return (
    <header className="topbar">
      <div className="topbar-left">
        <button className="mobile-menu-btn" onClick={onMobileOpen} aria-label="打开菜单">
          <svg viewBox="0 0 20 20" fill="none"><path d="M3 5h14M3 10h14M3 15h14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
        </button>
        <div className="breadcrumb">
          <span className="breadcrumb-home" onClick={() => onViewChange('dashboard')}>AgentOS</span>
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
        <button className="topbar-btn" title="通知" onClick={() => addToast('您有 4 条未读通知：\n• DocAgent 完成任务 T004\n• CodeAgent 发现 3 个中危漏洞\n• MLAgent CPU 使用率 85%\n• 系统备份完成')}>
          <svg viewBox="0 0 20 20" fill="none" width="18" height="18"><path d="M10 2a6 6 0 00-6 6v3l-2 2v1h16v-1l-2-2V8a6 6 0 00-6-6z" stroke="currentColor" strokeWidth="1.5"/><path d="M10 18a2 2 0 002-2H8a2 2 0 002 2z" stroke="currentColor" strokeWidth="1.5"/></svg>
          <span className="topbar-badge">4</span>
        </button>
        <button className="topbar-btn" title="文档" onClick={() => addToast('文档中心：AgentOS v2.4.1 使用手册')}>
          <svg viewBox="0 0 20 20" fill="none" width="18" height="18"><path d="M6 2h8a2 2 0 012 2v12a2 2 0 01-2 2H6a2 2 0 01-2-2V4a2 2 0 012-2z" stroke="currentColor" strokeWidth="1.5"/><path d="M7 7h6M7 10h6M7 13h4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>
        </button>
      </div>
    </header>
  );
}
