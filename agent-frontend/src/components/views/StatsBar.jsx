import React from 'react';

export default function StatsBar({ stats = {}, parentStatus, className = '' }) {
  const { total = 0, done = 0, running = 0, pending = 0, failed = 0, progressPct = 0, bottleneckCount = 0 } = stats;
  const circumference = 2 * Math.PI * 36;
  const dashoffset = circumference * (1 - progressPct / 100);
  const statusLabel = parentStatus === 'REPLY' ? '已完成' : parentStatus === 'FAILED' ? '失败' : running > 0 ? '执行中' : '等待中';

  return (
    <div className={`stats-bar ${className}`}>
      <div className="stats-ring-card">
        <svg width="90" height="90" viewBox="0 0 90 90">
          <circle cx="45" cy="45" r="36" fill="none" stroke="var(--border-subtle)" strokeWidth="5" />
          <circle cx="45" cy="45" r="36" fill="none" stroke="var(--cyan)" strokeWidth="5"
            strokeDasharray={circumference} strokeDashoffset={dashoffset}
            strokeLinecap="round" transform="rotate(-90 45 45)"
            style={{ transition: 'stroke-dashoffset 0.5s ease' }} />
        </svg>
        <div className="stats-ring-text">
          <span className="stats-ring-number">{done}</span>
          <span className="stats-ring-sub">/ {total}</span>
        </div>
      </div>

      <div className="stats-cards">
        {[{ label: '等待中', count: pending, cls: 'pending' }, { label: '执行中', count: running, cls: 'running' }, { label: '已完成', count: done, cls: 'done' }, { label: '失败', count: failed, cls: 'failed' }].map(s => (
          <div key={s.cls} className={`stat-card ${s.cls}`}>
            <span className="stat-number">{s.count}</span>
            <span className="stat-label">{s.label}</span>
          </div>
        ))}
      </div>

      <div className="stats-meta">
        <span className={`status-badge status-${parentStatus?.toLowerCase() || 'pending'}`}>{statusLabel}</span>
        {bottleneckCount > 0 && <span className="bottleneck-badge">⚠ {bottleneckCount} 卡点</span>}
      </div>
    </div>
  );
}
