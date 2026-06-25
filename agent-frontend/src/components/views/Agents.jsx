import { useApp } from '../../AppContext';
import React, { useState } from 'react';

const COLOR_CYCLE = ['blue','green','purple','amber','coral'];
const COLOR_MAP = {
  blue: { bg:'rgba(55,138,221,0.12)', border:'rgba(55,138,221,0.3)', text:'#378ADD' },
  green: { bg:'rgba(29,158,117,0.12)', border:'rgba(29,158,117,0.3)', text:'#1D9E75' },
  purple: { bg:'rgba(127,119,221,0.12)', border:'rgba(127,119,221,0.3)', text:'#7F77DD' },
  amber: { bg:'rgba(186,117,23,0.12)', border:'rgba(186,117,23,0.3)', text:'#BA7517' },
  coral: { bg:'rgba(216,90,48,0.12)', border:'rgba(216,90,48,0.3)', text:'#D85A30' },
};

export default function Agents() {
  const { agents, addToast, openDetail } = useApp();
  const [filter, setFilter] = useState('all');

  const filtered = agents.filter(a => filter === 'all' || a.status === filter);

  return (
    <>
      <div className="view-header">
        <h1 className="view-title">Agent 管理</h1>
        <div className="view-actions">
          <div className="filter-tabs">
            {['all','online','busy','idle','offline'].map(k => (
              <button key={k} className={`filter-tab${filter===k?' active':''}`} onClick={()=>setFilter(k)}>
                {{all:'全部',online:'在线',busy:'忙碌',idle:'空闲',offline:'离线'}[k]}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="agent-grid">
        {filtered.length ? filtered.map((a, i) => {
          const colorName = COLOR_CYCLE[i % COLOR_CYCLE.length];
          const c = COLOR_MAP[colorName] || COLOR_MAP.blue;
          return (
            <div key={a.id} className={`agent-card ${a.status}`} onClick={() => openDetail('agent', a)}>
              <div className="agent-card-header">
                <div className="agent-avatar" style={{background:c.bg,border:`1px solid ${c.border}`,color:c.text}}>
                  {a.name.slice(0,2)}
                </div>
                <div className="agent-info">
                  <div className="agent-name">{a.name}</div>
                  <div className="agent-type">{a.version || 'Agent'}</div>
                </div>
                <span className={`status-badge ${a.status}`}>
                  {a.status === 'online' ? '在线' : a.status === 'busy' ? '忙碌' : a.status === 'idle' ? '空闲' : '离线'}
                </span>
              </div>
              <div className="agent-stats">
                <div className="agent-stat"><span className="agent-stat-label">任务数</span><span className="agent-stat-val" style={{color:c.text}}>{a.task_count || 0}</span></div>
                <div className="agent-stat"><span className="agent-stat-label">技能数</span><span className="agent-stat-val">{a.skill_count || 0}</span></div>
                <div className="agent-stat"><span className="agent-stat-label">协作</span><span className="agent-stat-val">{a.capabilities?.length || 0}</span></div>
                <div className="agent-stat"><span className="agent-stat-label">状态</span><span className="agent-stat-val" style={{fontSize:11, color: a.status==='online'?'var(--green)':'var(--text-muted)'}}>{a.status || '未知'}</span></div>
              </div>
              {a.capabilities && a.capabilities.length > 0 && (
                <div className="agent-skills-row">
                  {a.capabilities.map((s, si) => <span key={si} className="skill-tag">{s.name || s}</span>)}
                </div>
              )}
              {a.portrait && (
                <div style={{fontSize:10,color:'var(--text-muted)',marginTop:8,lineHeight:1.5,overflow:'hidden',maxHeight:'2.25em'}}>
                  {a.portrait.slice(0, 80)}...
                </div>
              )}
            </div>
          );
        }) : <div style={{padding:40,textAlign:'center',color:'var(--text-muted)',gridColumn:'1/-1'}}>暂无 Agent</div>}
      </div>
    </>
  );
}
