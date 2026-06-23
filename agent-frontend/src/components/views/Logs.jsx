import React, { useState, useEffect } from 'react';
import { api } from '../../api';

export default function Logs({ addToast }) {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const data = await api.get('/cron-executions/', { page_size: 50 });
        const items = data.results || data || [];
        setLogs(items.map(e => ({
          ts: e.completed_at || e.created_at,
          level: e.status === 'ok' ? 'INFO' : e.status === 'error' ? 'ERROR' : 'INFO',
          src: e.job_id || 'system',
          msg: e.name || `执行记录 #${e.id}`,
        })));
      } catch {
        // Fallback: show recent tasks as log entries
        try {
          const data = await api.get('/tasks/', { page_size: 30, ordering: '-created_at' });
          const items = data.results || data || [];
          setLogs(items.map(t => ({
            ts: t.created_at,
            level: t.status === 'failed' ? 'ERROR' : t.status === 'completed' ? 'INFO' : 'INFO',
            src: t.agent_name || 'system',
            msg: `[任务#${t.id}] ${t.title}`,
          })));
        } catch {}
      }
      finally { setLoading(false); }
    })();
  }, []);

  return (
    <>
      <div className="view-header">
        <h1 className="view-title">运行日志</h1>
        <div className="view-actions">
          <span className="live-indicator">{logs.length} 条记录</span>
          <button className="btn btn-ghost" style={{fontSize:11}} onClick={() => window.location.reload()}>刷新</button>
        </div>
      </div>
      <div className="log-terminal">
        {loading ? (
          <div style={{color:'var(--text-muted)',textAlign:'center',padding:20}}>加载中...</div>
        ) : logs.length === 0 ? (
          <div style={{color:'var(--text-muted)',textAlign:'center',padding:20}}>暂无日志</div>
        ) : logs.map((l, i) => (
          <div key={i} className="log-line">
            <span className="log-ts">{l.ts ? new Date(l.ts).toLocaleString() : '—'}</span>
            <span className={`log-lvl ${l.level}`}>{l.level}</span>
            <span className="log-src">[{l.src}]</span>
            <span className="log-msg">{l.msg}</span>
          </div>
        ))}
      </div>
    </>
  );
}
