import React, { useState } from 'react';
import { api } from '../../api';

export default function Tasks({ tasks, setTasks, addToast, openDetail, openModal, setView }) {
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [batchMode, setBatchMode] = useState(false);
  const [selected, setSelected] = useState(new Set());
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 10;

  const statusCN = { completed:'完成', in_progress:'执行中', running:'运行中', pending:'待执行', failed:'失败' };
  const statusColors = {
    completed: { bg:'rgba(29,158,117,0.12)', text:'#1D9E75', border:'rgba(29,158,117,0.3)' },
    in_progress: { bg:'rgba(55,138,221,0.12)', text:'#378ADD', border:'rgba(55,138,221,0.3)' },
    running: { bg:'rgba(55,138,221,0.12)', text:'#378ADD', border:'rgba(55,138,221,0.3)' },
    pending: { bg:'rgba(186,117,23,0.12)', text:'#BA7517', border:'rgba(186,117,23,0.3)' },
    failed: { bg:'rgba(226,75,74,0.12)', text:'#E24B4A', border:'rgba(226,75,74,0.3)' },
  };

  let filtered = tasks.filter(t => {
    if (filter !== 'all' && t.status !== filter) return false;
    if (search && !(t.title || '').toLowerCase().includes(search.toLowerCase())
      && !(t.agent_name || '').toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  const paged = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const toggleSelect = (id) => {
    const next = new Set(selected);
    next.has(id) ? next.delete(id) : next.add(id);
    setSelected(next);
  };

  const selectAll = () => {
    if (selected.size === paged.length) { setSelected(new Set()); }
    else { setSelected(new Set(paged.map(t => t.id))); }
  };

  const batchAction = async (action) => {
    const ids = Array.from(selected);
    if (!ids.length) return addToast('请先选择任务', 'error');
    if (action === 'delete' && !confirm(`确定删除 ${ids.length} 个任务？`)) return;
    try {
      for (const id of ids) {
        if (action === 'delete') await api.delete('/tasks/' + id + '/');
        else if (action === 'complete') await api.patch('/tasks/' + id + '/', { status: 'completed' });
      }
      // Refresh list
      const data = await api.get('/tasks/', { page_size: 100, ordering: '-created_at' });
      setTasks(data.results || data || []);
      setSelected(new Set());
      addToast(`${action === 'delete' ? '删除' : '完成'} ${ids.length} 个任务`, 'success');
    } catch (e) { addToast('操作失败', 'error'); }
  };

  return (
    <>
      <div className="view-header">
        <h1 className="view-title">任务管理</h1>
        <div className="view-actions">
          {!batchMode ? (
            <button className="btn btn-ghost" style={{fontSize:11}} onClick={() => setBatchMode(true)}>☑ 批量管理</button>
          ) : (
            <>
              <button className="btn btn-primary" style={{fontSize:11}} onClick={() => batchAction('complete')} disabled={selected.size===0}>✅ 批量完成</button>
              <button className="btn btn-danger" style={{fontSize:11}} onClick={() => batchAction('delete')} disabled={selected.size===0}>🗑 批量删除</button>
              <button className="btn btn-ghost" style={{fontSize:11}} onClick={() => { setBatchMode(false); setSelected(new Set()); }}>✕ 退出</button>
            </>
          )}
        </div>
      </div>

      <div className="card">
        <div className="table-toolbar">
          <div className="filter-tabs">
            {['all','pending','in_progress','completed','failed'].map(k => (
              <button key={k} className={`filter-tab${filter===k?' active':''}`} onClick={()=>{setFilter(k);setPage(1);}}>
                {{all:'全部',pending:'待执行',in_progress:'执行中',completed:'已完成',failed:'失败'}[k]}
              </button>
            ))}
          </div>
          <div className="search-inline">
            <svg viewBox="0 0 16 16" fill="none" width="13" height="13"><circle cx="7" cy="7" r="4.5" stroke="currentColor" strokeWidth="1.3"/><path d="M10.5 10.5l2.5 2.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></svg>
            <input type="text" placeholder="搜索任务..." value={search} onChange={e => {setSearch(e.target.value);setPage(1);}} />
          </div>
        </div>

        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                {batchMode && <th style={{width:40}}><input type="checkbox" checked={selected.size === paged.length && paged.length > 0} onChange={selectAll} /></th>}
                <th>任务</th><th>Agent</th><th>状态</th><th>优先级</th><th>时间</th>
              </tr>
            </thead>
            <tbody>
              {paged.map(t => {
                const sc = statusColors[t.status] || statusColors.pending;
                return (
                  <tr key={t.id} onClick={() => { if (!batchMode) openModal('taskDetail', t); }}>
                    {batchMode && <td onClick={e=>e.stopPropagation()}><input type="checkbox" checked={selected.has(t.id)} onChange={()=>toggleSelect(t.id)} /></td>}
                    <td><div style={{fontWeight:500,fontSize:13}}>{t.title}</div><div style={{fontSize:10,color:'var(--text-muted)',fontFamily:'var(--font-mono)'}}>#{t.id}</div></td>
                    <td><span style={{color:'var(--cyan)',fontSize:12}}>{t.agent_name || '—'}</span></td>
                    <td><span style={{fontSize:10,padding:'2px 8px',borderRadius:10,background:sc.bg,color:sc.text,border:`1px solid ${sc.border}`,fontWeight:500}}>{statusCN[t.status]||t.status}</span></td>
                    <td><span className={`priority-badge ${t.priority||'medium'}`}>{t.priority==='high'?'高':t.priority==='low'?'低':'中'}</span></td>
                    <td style={{fontSize:11,color:'var(--text-muted)'}}>{t.created_at?new Date(t.created_at).toLocaleString():'—'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div className="table-footer">
            <span className="table-info">共 {filtered.length} 条 · 第 {page}/{totalPages} 页</span>
            <div className="pagination">
              <button className="page-btn" disabled={page<=1} onClick={()=>setPage(p=>p-1)}>‹</button>
              {Array.from({length:totalPages},(_,i)=>i+1).slice(Math.max(0,page-3),page+2).map(p=>(
                <button key={p} className={`page-btn${p===page?' active':''}`} onClick={()=>setPage(p)}>{p}</button>
              ))}
              <button className="page-btn" disabled={page>=totalPages} onClick={()=>setPage(p=>p+1)}>›</button>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
