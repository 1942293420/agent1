import React from 'react';

export default function ProgressTimeline({ events = [], className = '' }) {
  if (!events.length) return null;
  return (
    <div className={`card ${className}`}>
      <div className="card-header"><h2 className="card-title">事件时间轴</h2><span className="card-link">{events.length} 条</span></div>
      <div style={{ maxHeight: 300, overflowY: 'auto', padding: '8px 16px' }}>
        {events.slice(-50).map((ev, i) => {
          const t = ev.timestamp ? new Date(ev.timestamp).toLocaleTimeString() : '';
          const type = ev.eventType || ev.event_type || 'heartbeat';
          const typeCN = { heartbeat: '心跳', stage_mark: '阶段', partial_out: '输出', tool_call: '工具', error: '错误', done_signal: '完成', node_status: '状态', progress_event: '进度' }[type] || type;
          const colors = { heartbeat: '#666', stage_mark: '#378ADD', partial_out: '#1D9E75', tool_call: '#7C3AED', error: '#E24B4A', done_signal: '#1D9E75', node_status: '#378ADD', progress_event: '#F59E0B' };
          const c = colors[type] || '#666';
          const agent = ev.agentName || ev.agent_name || '';
          const payload = ev.payload || '';
          return (
            <div key={i} style={{ display: 'flex', gap: 10, padding: '4px 0', borderLeft: '2px solid ' + c, marginLeft: 6, paddingLeft: 14, position: 'relative' }}>
              <div style={{ position: 'absolute', left: -5, top: 8, width: 8, height: 8, borderRadius: '50%', background: c }} />
              <span style={{ fontSize: 10, color: 'var(--text-muted)', minWidth: 60, fontFamily: 'var(--font-mono)' }}>{t}</span>
              <span style={{ fontSize: 10, fontWeight: 500, padding: '1px 5px', borderRadius: 3, background: c + '20', color: c, whiteSpace: 'nowrap' }}>{typeCN}</span>
              {agent && <span style={{ fontSize: 10, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>[{agent}]</span>}
              <span style={{ fontSize: 11, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{typeof payload === 'string' ? payload.slice(0, 100) : JSON.stringify(payload).slice(0, 100)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
