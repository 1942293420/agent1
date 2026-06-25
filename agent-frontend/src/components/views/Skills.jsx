import { useApp } from '../../AppContext';
import React, { useState } from 'react';

const COLOR_MAP = {
  tools:'#378ADD', 开发:'#1D9E75', 搜索:'#00d4ff', 视觉:'#7F77DD',
  nlp:'#BA7517', 数据库:'#D85A30', 监控:'#E24B4A', 文档:'#378ADD',
  active:'#1D9E75', draft:'#BA7517', deprecated:'#888',
};

const CATEGORIES = ['全部','tools','开发','搜索','视觉','nlp','数据库','监控','文档','active'];

export default function Skills() {
  const { skills, addToast, openDetail } = useApp();
  const [cat, setCat] = useState('全部');
  const [search, setSearch] = useState('');

  const filtered = skills.filter(s => {
    if (cat !== '全部' && s.category !== cat) return false;
    if (search && !s.name?.toLowerCase().includes(search.toLowerCase()) &&
        !s.description?.toLowerCase().includes(search.toLowerCase()) &&
        !s.name_zh?.toLowerCase().includes(search.toLowerCase()) &&
        !s.description_zh?.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  return (
    <>
      <div className="view-header">
        <h1 className="view-title">Skill 技能库</h1>
        <div className="view-actions">
          <div className="search-box" style={{width:240}}>
            <svg viewBox="0 0 16 16" fill="none" width="13" height="13"><circle cx="7" cy="7" r="4.5" stroke="currentColor" strokeWidth="1.3"/><path d="M10.5 10.5l2.5 2.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></svg>
            <input type="text" placeholder="搜索技能..." value={search} onChange={e => setSearch(e.target.value)} />
          </div>
        </div>
      </div>

      <div className="skill-category-bar">
        {CATEGORIES.map(c => (
          <button key={c} className={`skill-cat-btn${cat===c?' active':''}`} onClick={() => setCat(c)}>
            {c === '全部' ? '全部' : c}
          </button>
        ))}
      </div>

      <div className="skill-grid">
        {filtered.length ? filtered.map(s => {
          const col = COLOR_MAP[s.category] || COLOR_MAP.tools;
          const icon = s.tags?.[0] ? s.tags[0].slice(0,2) : 'SK';
          return (
            <div key={s.id} className="skill-card" onClick={() => openDetail('skill', s)}>
              <div className="skill-card-header">
                <div className="skill-icon" style={{background:`${col}20`,border:`1px solid ${col}40`}}>
                  <span style={{fontSize:12,fontWeight:600,color:col}}>{icon}</span>
                </div>
                <div>
                  <div className="skill-name">{s.name_zh || s.name}</div>
                  <div style={{fontSize:10,color:'var(--text-muted)'}}>
                    {s.category || 'tools'} · v{s.version || '—'}
                    {s.source && <span> · {s.source}</span>}
                  </div>
                </div>
              </div>
              <p className="skill-desc">{(s.description_zh || s.description || '').slice(0, 100)}</p>
              {s.tags && s.tags.length > 0 && (
                <div style={{display:'flex',flexWrap:'wrap',gap:4}}>
                  {s.tags.slice(0,5).map((t,ti) => (
                    <span key={ti} className="skill-tag" style={{fontSize:9}}>{t}</span>
                  ))}
                </div>
              )}
              <div className="skill-footer">
                <div className="skill-meta">
                  {s.status === 'active' ? <span className="status-badge active" style={{fontSize:9}}>已激活</span>
                    : s.status === 'draft' ? <span className="status-badge pending" style={{fontSize:9}}>草稿</span>
                    : <span className="status-badge offline" style={{fontSize:9}}>{s.status}</span>}
                </div>
                <span style={{fontSize:10,color:'var(--text-muted)'}}>
                  {s.agent_count || 0} Agent 使用
                </span>
              </div>
            </div>
          );
        }) : <div style={{padding:40,textAlign:'center',color:'var(--text-muted)',gridColumn:'1/-1'}}>暂无匹配技能</div>}
      </div>
    </>
  );
}
