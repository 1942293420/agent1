import { useApp } from '../../AppContext';
import React, { useState } from 'react';
// imports removed

export default function MemoryView() {
  const { memory, setMemory, addToast, openDetail, openModal } = useApp();
  const [filter, setFilter] = useState('all');

  let filtered = memory.filter(m => filter === 'all' || m.entry_type === filter);

  return (
    <>
      <div className="view-header">
        <h1 className="view-title">记忆管理</h1>
        <div className="view-actions">
          <button className="btn btn-ghost" onClick={() => addToast('开始向量索引重建...')}>重建索引</button>
          <button className="btn btn-primary" onClick={() => openModal('addMemory')}>添加记忆</button>
        </div>
      </div>

      <div className="memory-stats">
        <div className="memory-stat-card"><span className="msc-value">{memory.length.toLocaleString()}</span><span className="msc-label">总条目</span></div>
        <div className="memory-stat-card"><span className="msc-value">4</span><span className="msc-label">记忆类型</span></div>
        <div className="memory-stat-card"><span className="msc-value">82%</span><span className="msc-label">索引率</span></div>
        <div className="memory-stat-card"><span className="msc-value">128MB</span><span className="msc-label">占用空间</span></div>
      </div>

      <div className="card">
        <div className="table-toolbar">
          <div className="filter-tabs">
            {['all','solution','fact','conversation','skill','context'].map(k => (
              <button key={k} className={`filter-tab${filter===k?' active':''}`} onClick={()=>setFilter(k)}>
                {{all:'全部',solution:'方案',fact:'事实',conversation:'对话',skill:'技能',context:'上下文'}[k]}
              </button>
            ))}
          </div>
        </div>
        <div className="memory-list">
          {filtered.length ? filtered.map(m => (
            <div key={m.id} className="memory-item" onClick={() => openDetail('memory', m)}>
              <span className={`memory-type-badge ${m.entry_type || 'fact'}`}>{m.entry_type || 'fact'}</span>
              <div className="memory-content">
                <p className="memory-text">{m.title || (m.content || '').slice(0, 100)}</p>
                <div className="memory-meta">
                  {m.source_agent || '-'} · {m.created_at ? new Date(m.created_at).toLocaleString() : '-'}
                  {m.tags?.map(t => <span key={t} style={{background:'var(--bg-hover)',border:'1px solid var(--border-subtle)',borderRadius:3,padding:'1px 5px',fontSize:9,marginLeft:4,color:'var(--text-muted)'}}>{t}</span>)}
                </div>
              </div>
              <div style={{display:'flex',gap:4,flexShrink:0}} onClick={e => e.stopPropagation()}>
                <button className="action-btn" title="编辑" onClick={() => openDetail('memory', m)}>
                  <svg viewBox="0 0 14 14" fill="none" width="11" height="11"><path d="M2 10L9 3l2 2-7 7H2v-2z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/></svg>
                </button>
                <button className="action-btn" title="删除" onClick={() => { if(confirm(`删除记忆 ${m.id}？`)) { setMemory(memory.filter(x=>x.id!==m.id)); addToast('记忆已删除','error'); } }}>
                  <svg viewBox="0 0 14 14" fill="none" width="11" height="11"><path d="M2 3.5h10M5 3.5V2.5h4v1M5.5 6v4M8.5 6v4M3 3.5l1 8h6l1-8" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/></svg>
                </button>
              </div>
            </div>
          )) : <div style={{padding:40,textAlign:'center',color:'var(--text-muted)'}}>暂无记忆数据</div>}
        </div>
      </div>
    </>
  );
}
