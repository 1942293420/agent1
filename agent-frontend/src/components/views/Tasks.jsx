import React, { useState } from 'react';
import TaskGraph from './TaskGraph';
import RealtimeDashboard from './RealtimeDashboard';

export default function Tasks({ tasks, setTasks, addToast, openDetail, openModal, setView }) {
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [batchMode, setBatchMode] = useState(false);
  const [selected, setSelected] = useState(new Set());
  const [page, setPage] = useState(1);
  const [viewMode, setViewMode] = useState('table');
  const [graphTaskId, setGraphTaskId] = useState(null);
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
      const data = await api.get('/tasks/', { page_size: 100, ordering: '-created_at' });
      setTasks(data.results || data || []);
      setSelected(new Set());
      addToast(`${action === 'delete' ? '删除' : '完成'} ${ids.length} 个任务`, 'success');
    } catch (e) { addToast('操作失败', 'error'); }
  };

  // ── Tree-building ──
  const buildTaskTree = (taskList) => {
    const map = {};
    taskList.forEach(t => { map[t.id] = { ...t, children: [] }; });
    const roots = [];
    taskList.forEach(t => {
      if (t.parent_task && map[t.parent_task]) {
        map[t.parent_task].children.push(map[t.id]);
      } else {
        roots.push(map[t.id]);
      }
    });
    return roots;
  };

  const treeRoots = buildTaskTree(filtered);

  // If viewing a task graph full-screen (DAG drilldown)
  if (viewMode === 'graph-full' && graphTaskId) {
    return (
      <>
        <div className="view-header">
          <h1 className="view-title">任务管理</h1>
          <div className="view-actions">
            <button className="btn btn-ghost" style={{fontSize:11}} onClick={() => { setViewMode('tree'); setGraphTaskId(null); }}>
              ← 返回树形视图
            </button>
          </div>
        </div>
        <TaskGraph parentTaskId={graphTaskId} onClose={() => { setViewMode('tree'); setGraphTaskId(null); }} />
      </>
    );
  }

  // If viewing SSE realtime dashboard
  if (viewMode === 'realtime' && graphTaskId) {
    return (
      <>
        <div className="view-header">
          <h1 className="view-title">实时任务看板</h1>
          <div className="view-actions">
            <button className="btn btn-ghost" style={{fontSize:11}} onClick={() => { setViewMode('tree'); setGraphTaskId(null); }}>
              ← 返回列表
            </button>
          </div>
        </div>
        <RealtimeDashboard parentTaskId={graphTaskId} />
      </>
    );
  }

  return (
    <>
      <div className="view-header">
        <h1 className="view-title">任务管理</h1>
        <div className="view-actions">
          <div className="view-toggle" style={{ marginRight: 8 }}>
            <button className={`btn btn-ghost btn-toggle${viewMode === 'table' ? ' active' : ''}`}
              style={{fontSize:11}} onClick={() => setViewMode('table')}>
              📋 列表
            </button>
            <button className={`btn btn-ghost btn-toggle${viewMode === 'tree' ? ' active' : ''}`}
              style={{fontSize:11}} onClick={() => setViewMode('tree')}>
              🌳 树形
            </button>
          </div>
          {viewMode === 'table' && (
            !batchMode ? (
              <button className="btn btn-ghost" style={{fontSize:11}} onClick={() => setBatchMode(true)}>☑ 批量管理</button>
            ) : (
              <>
                <button className="btn btn-primary" style={{fontSize:11}} onClick={() => batchAction('complete')} disabled={selected.size===0}>✅ 批量完成</button>
                <button className="btn btn-danger" style={{fontSize:11}} onClick={() => batchAction('delete')} disabled={selected.size===0}>🗑 批量删除</button>
                <button className="btn btn-ghost" style={{fontSize:11}} onClick={() => { setBatchMode(false); setSelected(new Set()); }}>✕ 退出</button>
              </>
            )
          )}
        </div>
      </div>

      {/* ── Filter bar (shared) ── */}
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

        {viewMode === 'table' ? (
          /* ── Table View ── */
          <>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    {batchMode && <th style={{width:40}}><input type="checkbox" checked={selected.size === paged.length && paged.length > 0} onChange={selectAll} /></th>}
                    <th>任务</th><th>Agent</th><th>状态</th><th>优先级</th><th>时间</th><th style={{width:80}}></th>
                  </tr>
                </thead>
                <tbody>
                  {paged.map(t => {
                    const sc = statusColors[t.status] || statusColors.pending;
                    return (
                      <tr key={t.id} onClick={() => { if (!batchMode) { if (t._type === 'parent') { setGraphTaskId(t.id); setViewMode('graph-full'); } else { openModal('taskDetail', t); } } }}>
                        {batchMode && <td onClick={e=>e.stopPropagation()}><input type="checkbox" checked={selected.has(t.id)} onChange={()=>toggleSelect(t.id)} /></td>}
                        <td><div style={{fontWeight:500,fontSize:13}}>{t.title}</div><div style={{fontSize:10,color:'var(--text-muted)',fontFamily:'var(--font-mono)'}}>#{t.id}</div></td>
                        <td><span style={{color:'var(--cyan)',fontSize:12}}>{t.agent_name || '—'}</span></td>
                        <td><span style={{fontSize:10,padding:'2px 8px',borderRadius:10,background:sc.bg,color:sc.text,border:`1px solid ${sc.border}`,fontWeight:500}}>{statusCN[t.status]||t.status}</span></td>
                        <td><span className={`priority-badge ${t.priority||'medium'}`}>{t.priority==='high'?'高':t.priority==='low'?'低':'中'}</span></td>
                        <td style={{fontSize:11,color:'var(--text-muted)'}}>{t.created_at?new Date(t.created_at).toLocaleString():'—'}</td>
                        <td onClick={e => e.stopPropagation()} style={{display:'flex',gap:4}}>
                          {t._type === 'parent' && <>
                            <button className="btn btn-ghost" style={{fontSize:10,padding:'2px 6px'}} title="静态节点图" onClick={() => { setGraphTaskId(t.id); setViewMode('graph-full'); }}>📊</button>
                            <button className="btn btn-ghost" style={{fontSize:10,padding:'2px 6px',color:'#10b981'}} title="SSE实时看板" onClick={() => { setGraphTaskId(t.id); setViewMode('realtime'); }}>📡</button>
                          </>}
                        </td>
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
          </>
        ) : (
          /* ── Tree View ── */
          <div className="tree-view-container">
            {treeRoots.length === 0 ? (
              <div className="tree-empty">
                <span>📭 {search ? '没有匹配的任务' : '暂无任务，点击右上角创建'}</span>
              </div>
            ) : (
              treeRoots.map(root => (
                <TaskTreeNode
                  key={root.id}
                  node={root}
                  depth={0}
                  statusCN={statusCN}
                  statusColors={statusColors}
                  onDetail={(t) => openModal('taskDetail', t)}
                  onGraph={(id) => { setGraphTaskId(id); setViewMode('graph-full'); }}
                />
              ))
            )}
          </div>
        )}
      </div>
    </>
  );
}

/* ── Tree Node Component ── */
function TaskTreeNode({ node, depth, statusCN, statusColors, onDetail, onGraph }) {
  const [expanded, setExpanded] = useState(false);
  const hasChildren = node.children && node.children.length > 0;
  const sc = statusColors[node.status] || statusColors.pending;
  const isRunning = node.status === 'running' || node.status === 'in_progress';

  return (
    <div className="tree-node-group">
      <div
        className="tree-node-row"
        style={{ paddingLeft: depth * 28 + 12 }}
      >
        {/* Expand / collapse toggle */}
        <span
          className={`tree-toggle ${hasChildren ? 'has-children' : ''}`}
          onClick={(e) => { e.stopPropagation(); if (hasChildren) setExpanded(!expanded); }}
        >
          {hasChildren ? (expanded ? '▼' : '▶') : '·'}
        </span>

        {/* Status dot */}
        <span className={`tree-status-dot ${isRunning ? 'pulse' : ''}`}
          style={{ backgroundColor: sc.text }}
          title={statusCN[node.status] || node.status}
        />

        {/* Title + ID */}
        <span className="tree-title" onClick={() => onDetail(node)} title="点击查看详情">
          <span className="tree-title-text">{node.title}</span>
          <span className="tree-id">#{node.id}</span>
        </span>

        {/* Agent */}
        <span className="tree-agent" style={{ color: 'var(--cyan)' }}>
          {node.agent_name || '—'}
        </span>

        {/* Status badge */}
        <span className="tree-status-badge"
          style={{
            background: sc.bg,
            color: sc.text,
            border: `1px solid ${sc.border}`,
          }}>
          {statusCN[node.status] || node.status}
        </span>

        {/* Priority */}
        <span className={`priority-badge ${node.priority || 'medium'} tree-priority`}>
          {node.priority === 'high' ? '高' : node.priority === 'low' ? '低' : '中'}
        </span>

        {/* Time */}
        <span className="tree-time">
          {node.created_at ? new Date(node.created_at).toLocaleString() : '—'}
        </span>

        {/* Children count badge */}
        {hasChildren && (
          <span className="tree-child-count" title={`${node.children.length} 个子任务`}>
            {node.children.length}
          </span>
        )}

        {/* Graph button */}
        <button
          className="btn btn-ghost tree-graph-btn"
          style={{ fontSize: 10, padding: '2px 6px' }}
          onClick={(e) => { e.stopPropagation(); onGraph(node.id); }}
          title="查看执行图"
        >
          🔀
        </button>
      </div>

      {/* Render children recursively */}
      {expanded && hasChildren && (
        <div className="tree-children">
          {node.children.map(child => (
            <TaskTreeNode
              key={child.id}
              node={child}
              depth={depth + 1}
              statusCN={statusCN}
              statusColors={statusColors}
              onDetail={onDetail}
              onGraph={onGraph}
            />
          ))}
        </div>
      )}
    </div>
  );
}
