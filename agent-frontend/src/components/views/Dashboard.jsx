import React from 'react';

export default function Dashboard({ tasks, agents, skills, memory, workers, loading, addToast, openDetail, setView }) {
  const activeTasks = tasks.filter(t => t.status === 'running' || t.status === 'in_progress' || t.status === 'pending');
  const onlineAgents = agents.filter(a => a.status === 'online');
  const recentTasks = tasks.slice(0, 8);

  const metrics = [
    { key:'agents', color:'blue', label:'Agent', val:onlineAgents.length, sub:`共 ${agents.length}`, nav:'agents' },
    { key:'tasks', color:'green', label:'任务', val:tasks.length, sub:`${activeTasks.length} 活跃`, nav:'tasks' },
    { key:'skills', color:'amber', label:'Skill', val:skills.length, sub:'技能库', nav:'skills' },
    { key:'memory', color:'purple', label:'记忆', val:memory.length, sub:'条目', nav:'memory' },
    { key:'workers', color:'coral', label:'Worker', val:workers.filter(w=>w.status==='active').length, sub:`共 ${workers.length}`, nav:'workers' },
    { key:'cron', color:'gray', label:'定时', val:'查看', sub:'定时任务', nav:'cron' },
  ];

  return (
    <>
      <div className="view-header">
        <h1 className="view-title">系统概览</h1>
        <div className="view-actions">
          <span className="live-indicator"><span className="live-dot" />实时</span>
        </div>
      </div>

      {loading ? (
        <div style={{padding:40,textAlign:'center',color:'var(--text-muted)'}}>加载中...</div>
      ) : (
        <>
          <div className="metrics-grid">
            {metrics.map(m => (
              <div key={m.key} className={`metric-card ${m.color}`} onClick={() => setView(m.nav)} style={{cursor:'pointer'}}>
                <div className="metric-body">
                  <span className="metric-label">{m.label}</span>
                  <span className="metric-value">{m.val}</span>
                  <span className="metric-delta">{m.sub}</span>
                </div>
              </div>
            ))}
          </div>

          <div className="dashboard-bottom">
            <div className="card">
              <div className="card-header">
                <h2 className="card-title">Agent 状态</h2>
                <span className="card-link" onClick={() => setView('agents')}>查看全部 →</span>
              </div>
              {agents.map(a => {
                const online = a.status === 'online';
                return (
                  <div key={a.id} style={{display:'flex',alignItems:'center',gap:10,padding:'6px 0',cursor:'pointer'}}
                    onClick={() => openDetail('agent', a)}>
                    <span className={`status-badge ${online?'online':'offline'}`}>
                      {online ? '在线' : a.status === 'busy' ? '忙碌' : '离线'}
                    </span>
                    <span style={{fontSize:13,flex:1}}>{a.name}</span>
                    <span style={{fontSize:11,color:'var(--text-muted)'}}>{a.task_count || 0} 任务</span>
                  </div>
                );
              })}
            </div>
            <div className="card">
              <div className="card-header">
                <h2 className="card-title">最近任务</h2>
                <span className="card-link" onClick={() => setView('tasks')}>查看全部 →</span>
              </div>
              <div className="task-list">
                {recentTasks.map(t => (
                  <div key={t.id} className="task-item-small" onClick={() => openDetail('task', t)}>
                    <span className={`status-badge ${t.status}`}>
                      {t.status === 'completed' ? '完成' : t.status === 'in_progress' ? '执行中' : t.status === 'pending' ? '等待' : t.status}
                    </span>
                    <span className="task-name">{t.title}</span>
                    <span className="task-agent">{t.agent_name}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="card" style={{marginTop:16}}>
            <div className="card-header">
              <h2 className="card-title">Worker 心跳</h2>
              <span className="card-link" onClick={() => setView('workers')}>查看详情 →</span>
            </div>
            <div style={{display:'flex',gap:24,flexWrap:'wrap'}}>
              {workers.map(w => (
                <div key={w.name} style={{display:'flex',alignItems:'center',gap:10}}>
                  <span className="status-dot active" style={w.status !== 'active' ? {background:'var(--text-muted)',boxShadow:'none'} : {}} />
                  <span style={{fontSize:13}}>{w.icon} {w.label}</span>
                  <span style={{fontSize:11,color:'var(--text-muted)',fontFamily:'var(--font-mono)'}}>{w.uptime_display}</span>
                  <span style={{fontSize:11,color:'var(--text-muted)'}}>{w.memory_mb > 0 ? `${w.memory_mb}MB` : ''}</span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </>
  );
}
