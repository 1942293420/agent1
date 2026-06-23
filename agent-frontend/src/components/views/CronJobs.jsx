import React, { useState } from 'react';
import { api } from '../../api';

export default function CronJobsView({ cronJobs, setCronJobs, loading, addToast }) {
  const [editing, setEditing] = useState(null);
  const [editName, setEditName] = useState('');
  const [editSchedule, setEditSchedule] = useState('');

  const deleteJob = async (id) => {
    if (!confirm('确定删除此定时任务？')) return;
    try {
      await api.delete('/cron-jobs/' + id + '/');
      setCronJobs(prev => prev.filter(c => c.id !== id));
      addToast('已删除', 'success');
    } catch { addToast('删除失败', 'error'); }
  };

  const togglePause = async (job) => {
    try {
      const newStatus = job.status === 'active' ? 'paused' : 'active';
      await api.patch('/cron-jobs/' + job.id + '/', { status: newStatus });
      setCronJobs(prev => prev.map(c => c.id === job.id ? { ...c, status: newStatus } : c));
      addToast(newStatus === 'active' ? '已恢复' : '已暂停', 'success');
    } catch { addToast('操作失败', 'error'); }
  };

  const startEdit = (job) => {
    setEditing(job.id);
    setEditName(job.name || '');
    setEditSchedule(job.schedule || '');
  };

  const saveEdit = async (id) => {
    try {
      await api.patch('/cron-jobs/' + id + '/', { name: editName, schedule: editSchedule });
      setCronJobs(prev => prev.map(c => c.id === id ? { ...c, name: editName, schedule: editSchedule } : c));
      setEditing(null);
      addToast('已更新', 'success');
    } catch { addToast('更新失败', 'error'); }
  };

  return (
    <>
      <div className="view-header">
        <h1 className="view-title">定时任务</h1>
        <span className="live-indicator">{cronJobs.length} 个任务</span>
      </div>
      {loading ? <div style={{padding:40,textAlign:'center',color:'var(--text-muted)'}}>加载中...</div> : (
        <div className="card">
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr><th>名称</th><th>调度</th><th>状态</th><th style={{width:140}}>操作</th></tr>
              </thead>
              <tbody>
                {cronJobs.length ? cronJobs.map(cj => (
                  <tr key={cj.id}>
                    <td>
                      {editing === cj.id ? (
                        <input className="form-input" style={{padding:'4px 8px',fontSize:12}} value={editName} onChange={e => setEditName(e.target.value)} />
                      ) : <span style={{fontWeight:500}}>{cj.name || cj.id}</span>}
                    </td>
                    <td style={{fontFamily:'var(--font-mono)',fontSize:11}}>
                      {editing === cj.id ? (
                        <input className="form-input" style={{padding:'4px 8px',fontSize:11}} value={editSchedule} onChange={e => setEditSchedule(e.target.value)} />
                      ) : (cj.schedule || '—')}
                    </td>
                    <td><span className={`status-badge ${cj.status}`}>{cj.status === 'active' ? '运行' : cj.status === 'paused' ? '暂停' : cj.status}</span></td>
                    <td>
                      {editing === cj.id ? (
                        <div style={{display:'flex',gap:4}}>
                          <button className="btn btn-primary" style={{fontSize:10,padding:'3px 8px'}} onClick={() => saveEdit(cj.id)}>保存</button>
                          <button className="btn btn-ghost" style={{fontSize:10,padding:'3px 8px'}} onClick={() => setEditing(null)}>取消</button>
                        </div>
                      ) : (
                        <div className="action-group">
                          <button className="action-btn" title="编辑" onClick={() => startEdit(cj)}>✏️</button>
                          <button className="action-btn" title={cj.status==='active'?'暂停':'恢复'} onClick={() => togglePause(cj)}>{cj.status==='active'?'⏸':'▶'}</button>
                          <button className="action-btn" title="删除" onClick={() => deleteJob(cj.id)} style={{color:'var(--red)'}}>🗑</button>
                        </div>
                      )}
                    </td>
                  </tr>
                )) : <tr><td colSpan="4" style={{textAlign:'center',color:'var(--text-muted)',padding:20}}>暂无定时任务</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}
