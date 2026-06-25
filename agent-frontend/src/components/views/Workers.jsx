import { useApp } from '../../AppContext';
import React from 'react';

export default function WorkersView() {
  const { workers, loading } = useApp();
  return (
    <>
      <div className="view-header">
        <h1 className="view-title">Worker 状态</h1>
        <span className="live-indicator"><span className="live-dot" />实时</span>
      </div>
      {loading ? <div style={{padding:40,textAlign:'center',color:'var(--text-muted)'}}>加载中...</div> : (
        <div className="agent-grid">
          {workers.map(w => {
            const active = w.status === 'active';
            const color = active ? 'var(--green)' : w.status === 'error' ? 'var(--red)' : 'var(--text-muted)';
            return (
              <div key={w.name} className={`agent-card ${active ? 'online' : 'offline'}`}>
                <div className="agent-card-header">
                  <div className="agent-avatar" style={{background:`${color}20`,border:`1px solid ${color}40`,color}}>
                    {w.icon}
                  </div>
                  <div className="agent-info">
                    <div className="agent-name">{w.label}</div>
                    <div className="agent-type">{w.name}</div>
                  </div>
                  <span className={`status-badge ${active ? 'online' : 'offline'}`}>
                    {w.status === 'active' ? '运行中' : w.status}
                  </span>
                </div>
                <div className="agent-stats">
                  <div className="agent-stat"><span className="agent-stat-label">PID</span><span className="agent-stat-val" style={{fontSize:11}}>{w.pid || '—'}</span></div>
                  <div className="agent-stat"><span className="agent-stat-label">运行时长</span><span className="agent-stat-val" style={{fontSize:11}}>{w.uptime_display || '—'}</span></div>
                  <div className="agent-stat"><span className="agent-stat-label">内存</span><span className="agent-stat-val">{w.memory_mb > 0 ? `${w.memory_mb}MB` : '—'}</span></div>
                  <div className="agent-stat"><span className="agent-stat-label">端口</span><span className="agent-stat-val" style={{color: w.port_ok ? 'var(--green)' : 'var(--red)'}}>
                    {w.port ? `${w.port} ${w.port_ok ? '✓' : '✗'}` : '—'}
                  </span></div>
                </div>
                {w.error && <div style={{fontSize:10,color:'var(--red)',marginTop:8}}>⚠️ {w.error}</div>}
                {w.desc && <div style={{fontSize:10,color:'var(--text-muted)',marginTop:8}}>{w.desc}</div>}
              </div>
            );
          })}
        </div>
      )}
    </>
  );
}
