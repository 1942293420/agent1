import React from 'react';

export default function DetailPanel({ type, data, onClose, agents, tasks, addToast, openDetail, setTasks, setAgents }) {
  if (!type || !data) return null;

  return (
    <div className="detail-overlay open" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="detail-panel">
        <div className="detail-header">
          <button className="detail-back" onClick={onClose} aria-label="返回">
            <svg viewBox="0 0 16 16" fill="none" width="16" height="16"><path d="M10 3L5 8l5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
          </button>
          <h2 className="detail-title">
            {type === 'task' && (data.title || data.name)}
            {type === 'agent' && data.name}
            {type === 'skill' && data.name}
            {type === 'memory' && `记忆详情 · ${data.entry_type || data.type || ''}`}
          </h2>
          <button className="detail-close" onClick={onClose} aria-label="关闭">
            <svg viewBox="0 0 16 16" fill="none" width="16" height="16"><path d="M3 3l10 10M13 3L3 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
          </button>
        </div>
        <div className="detail-body">
          {type === 'task' && <TaskDetail data={data} agents={agents} openDetail={openDetail} onClose={onClose} />}
          {type === 'agent' && <AgentDetail data={data} tasks={tasks} openDetail={openDetail} onClose={onClose} />}
          {type === 'skill' && <SkillDetail data={data} addToast={addToast} onClose={onClose} />}
          {type === 'memory' && <MemoryDetail data={data} addToast={addToast} onClose={onClose} />}
        </div>
      </div>
    </div>
  );
}

function TaskDetail({ data: t, agents, openDetail, onClose }) {
  return (
    <>
      <div className="detail-section">
        <div className="detail-section-title">基本信息</div>
        <div className="detail-kv">
          <span className="detail-key">任务ID</span><span className="detail-val">#{t.id}</span>
          <span className="detail-key">状态</span><span className="detail-val"><span className={`status-badge ${t.status}`}>{t.status === 'completed' ? '完成' : t.status === 'in_progress' ? '执行中' : t.status === 'pending' ? '等待' : t.status === 'failed' ? '失败' : t.status}</span></span>
          <span className="detail-key">优先级</span><span className="detail-val"><span className={`priority-badge ${t.priority || 'medium'}`}>{t.priority === 'high' ? '高' : t.priority === 'medium' ? '中' : '低'}</span></span>
          <span className="detail-key">Agent</span><span className="detail-val" style={{color:'var(--cyan)',cursor:'pointer'}} onClick={() => { onClose(); setTimeout(() => { const a = agents.find(x => x.name === t.agent_name); if (a) openDetail('agent', a); }, 200); }}>{t.agent_name || '未分配'}</span>
          <span className="detail-key">创建时间</span><span className="detail-val">{t.created_at ? new Date(t.created_at).toLocaleString() : '—'}</span>
          <span className="detail-key">来源</span><span className="detail-val">{t.source_label || t.source || '—'}</span>
        </div>
      </div>
      <div className="detail-section">
        <div className="detail-section-title">描述</div>
        <p className="detail-desc">{t.description || '暂无描述'}</p>
      </div>
      {t.assigned_skills?.length > 0 && (
        <div className="detail-section">
          <div className="detail-section-title">挂载 Skill</div>
          <div style={{display:'flex',gap:6,flexWrap:'wrap'}}>{t.assigned_skills.map((s, i) => <span key={i} className="skill-tag">{s.name || s}</span>)}</div>
        </div>
      )}
    </>
  );
}

function AgentDetail({ data: a, tasks: allTasks, openDetail, onClose }) {
  const agentTasks = allTasks.filter(t => t.agent_name === a.name || t.agent === a.id);
  return (
    <>
      <div className="detail-section">
        <div style={{display:'flex',alignItems:'center',gap:14,marginBottom:16}}>
          <div style={{width:56,height:56,borderRadius:14,background:'rgba(0,212,255,0.12)',border:'1px solid rgba(0,212,255,0.3)',display:'flex',alignItems:'center',justifyContent:'center',fontSize:22,fontWeight:600,color:'#00d4ff'}}>{a.name?.slice(0,2)}</div>
          <div><div style={{fontSize:18,fontWeight:600}}>{a.name}</div><div style={{fontSize:12,color:'var(--text-muted)'}}><span className={`status-badge ${a.status}`}>{a.status === 'online' ? '在线' : a.status === 'busy' ? '忙碌' : '离线'}</span></div></div>
        </div>
      </div>
      <div className="detail-section">
        <div className="detail-section-title">运行指标</div>
        <div className="detail-kv">
          <span className="detail-key">任务数</span><span className="detail-val">{a.task_count || 0}</span>
          <span className="detail-key">技能数</span><span className="detail-val">{a.skill_count || 0}</span>
          <span className="detail-key">状态</span><span className="detail-val">{a.status || '未知'}</span>
          <span className="detail-key">ID</span><span className="detail-val">#{a.id}</span>
        </div>
      </div>
      {a.portrait && (
        <div className="detail-section">
          <div className="detail-section-title">System Portrait</div>
          <p className="detail-desc" style={{maxHeight:200,overflowY:'auto'}}>{a.portrait}</p>
        </div>
      )}
    </>
  );
}

function SkillDetail({ data: s, addToast, onClose }) {
  if (!s.name && !s.id) return null;
  return (
    <>
      <div className="detail-section">
        <div style={{display:'flex',alignItems:'center',gap:14,marginBottom:16}}>
          <div style={{width:56,height:56,borderRadius:14,background:'var(--bg-hover)',display:'flex',alignItems:'center',justifyContent:'center',fontSize:20,fontWeight:600,color:'var(--cyan)'}}>SK</div>
          <div><div style={{fontSize:18,fontWeight:600}}>{s.name}</div><div style={{fontSize:12,color:'var(--text-muted)'}}>{s.category || 'tools'} · v{s.version}</div></div>
        </div>
      </div>
      <div className="detail-section">
        <div className="detail-section-title">技能信息</div>
        <div className="detail-kv">
          <span className="detail-key">Skill ID</span><span className="detail-val">#{s.id}</span>
          <span className="detail-key">版本</span><span className="detail-val">v{s.version}</span>
          <span className="detail-key">来源</span><span className="detail-val">{s.source || '—'}</span>
          <span className="detail-key">状态</span><span className="detail-val">{s.status || 'active'}</span>
        </div>
      </div>
      <div className="detail-section">
        <div className="detail-section-title">描述</div>
        <p className="detail-desc">{s.description || '暂无描述'}</p>
      </div>
      {s.tags?.length > 0 && (
        <div className="detail-section">
          <div className="detail-section-title">标签</div>
          <div style={{display:'flex',gap:6,flexWrap:'wrap'}}>
            {s.tags.map(t => <span key={t} className="skill-tag">{t}</span>)}
          </div>
        </div>
      )}
    </>
  );
}

function MemoryDetail({ data: m, addToast, onClose }) {
  return (
    <>
      <div className="detail-section">
        <div className="detail-section-title">基本信息</div>
        <div className="detail-kv">
          <span className="detail-key">ID</span><span className="detail-val">#{m.id}</span>
          <span className="detail-key">类型</span><span className="detail-val"><span className={`memory-type-badge ${m.entry_type || 'fact'}`}>{m.entry_type || '未知'}</span></span>
          <span className="detail-key">来源</span><span className="detail-val" style={{color:'var(--cyan)'}}>{m.source_agent || '—'}</span>
          <span className="detail-key">创建时间</span><span className="detail-val">{m.created_at ? new Date(m.created_at).toLocaleString() : '—'}</span>
        </div>
      </div>
      <div className="detail-section">
        <div className="detail-section-title">标题</div>
        <p className="detail-desc">{m.title || '—'}</p>
      </div>
      <div className="detail-section">
        <div className="detail-section-title">内容</div>
        <p className="detail-desc" style={{maxHeight:300,overflowY:'auto'}}>{m.content}</p>
      </div>
      {m.tags?.length > 0 && (
        <div className="detail-section">
          <div className="detail-section-title">标签</div>
          <div style={{display:'flex',gap:6,flexWrap:'wrap'}}>
            {m.tags.map(t => <span key={t} style={{background:'var(--bg-hover)',border:'1px solid var(--border-subtle)',borderRadius:4,padding:'2px 8px',fontSize:11,color:'var(--text-secondary)'}}>{t}</span>)}
          </div>
        </div>
      )}
    </>
  );
}
