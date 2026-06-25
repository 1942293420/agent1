import React, { useState, useEffect, useCallback } from 'react';

function getCSRF() {
  const m = document.cookie.match(/csrftoken=([^;]+)/);
  return m ? m[1] : "";
}

async function adminFetch(url, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  if ((opts.method || "GET") !== "GET") {
    const csrf = getCSRF();
    if (csrf) headers["X-CSRFToken"] = csrf;
  }
  if (opts.body && typeof opts.body === "string") {
    headers["Content-Type"] = "application/json";
  }
  return fetch(url, { ...opts, headers, credentials: "include" });
}

const MOBILE_CSS = `
.admin-mobile-cards { display: none; }
@media(max-width:768px){
  .admin-table-wrap { display: none; }
  .admin-mobile-cards { display: flex; flex-direction: column; gap: 12px; }
  .admin-mobile-card {
    background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06);
    border-radius: 10px; padding: 14px;
  }
  .admin-mobile-card-row {
    display: flex; justify-content: space-between; align-items: center;
    padding: 6px 0; font-size: 13px;
  }
  .admin-mobile-card-row .label { color: #4d6178; font-size: 11px; flex-shrink: 0; }
  .admin-mobile-card-row .value { color: #d0d6e0; text-align: right; }
  .admin-mobile-card-actions {
    display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; padding-top: 10px;
    border-top: 1px solid rgba(255,255,255,0.04);
  }
  .admin-mobile-card-actions button {
    flex: 1; min-width: 60px; padding: 8px 6px; font-size: 12px; font-weight: 500;
    border-radius: 6px; border: 1px solid rgba(255,255,255,0.1);
    background: rgba(255,255,255,0.04); color: #d0d6e0; cursor: pointer;
    font-family: 'Inter', system-ui, sans-serif;
  }
  .admin-mobile-card-actions .btn-approve { background: rgba(29,158,117,0.12); border-color: rgba(29,158,117,0.3); color: #4ade80; }
  .admin-mobile-card-actions .btn-danger { background: rgba(226,75,74,0.1); border-color: rgba(226,75,74,0.3); color: #ff6b6b; }
  .admin-stats-row { flex-direction: column; }
}
`;

export default function AdminView({ addToast }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [newUsername, setNewUsername] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [addError, setAddError] = useState('');
  const [resetModal, setResetModal] = useState(null);
  const [resetPwd, setResetPwd] = useState('');

  const fetchUsers = useCallback(async () => {
    try { const res = await adminFetch('/api/admin/users/'); if (res.ok) { setUsers(await res.json()); } } catch (e) {}
    setLoading(false);
  }, []);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  const handleApprove = async (id, username) => {
    try { const res = await adminFetch(`/api/admin/users/${id}/approve/`, { method: 'POST' }); if (res.ok) { addToast(`已通过 ${username}`); fetchUsers(); } } catch (e) {}
  };
  const handleReject = async (id, username) => {
    if (!confirm(`确定拒绝 ${username} 并删除？`)) return;
    try { const res = await adminFetch(`/api/admin/users/${id}/reject/`, { method: 'POST' }); if (res.ok) { addToast(`已拒绝 ${username}`); fetchUsers(); } } catch (e) {}
  };
  const handleDelete = async (id, username) => {
    if (!confirm(`永久删除 ${username}？`)) return;
    try { const res = await adminFetch(`/api/admin/users/${id}/delete/`, { method: 'POST' }); if (res.ok) { addToast(`已删除 ${username}`); fetchUsers(); } else { const d = await res.json(); addToast(d.error || '失败'); } } catch (e) {}
  };
  const handleReset = async () => {
    if (!resetPwd || resetPwd.length < 6) { addToast('密码至少6位'); return; }
    try { const res = await adminFetch(`/api/admin/users/${resetModal.id}/reset-password/`, { method: 'POST', body: JSON.stringify({ password: resetPwd }) }); if (res.ok) { addToast(`已重置 ${resetModal.username}，新密码: ${resetPwd}`); setResetModal(null); setResetPwd(''); } else { addToast((await res.json()).error || '失败'); } } catch (e) {}
  };
  const handleAdd = async () => {
    if (!newUsername.trim() || !newPassword) { setAddError('用户名和密码不能为空'); return; }
    if (newPassword.length < 6) { setAddError('密码至少6位'); return; }
    setAddError('');
    try { const res = await adminFetch('/api/admin/users/add/', { method: 'POST', body: JSON.stringify({ username: newUsername.trim(), password: newPassword }) }); if (res.ok) { addToast(`已添加 ${newUsername.trim()}，密码: ${newPassword}`); setNewUsername(''); setNewPassword(''); setShowAdd(false); fetchUsers(); } else { setAddError((await res.json()).error || '失败'); } } catch (e) { setAddError('网络错误'); }
  };

  const pendingCount = users.filter(u => !u.is_active).length;

  const styles = {
    container: { padding: 0 },
    header: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20, flexWrap: 'wrap', gap: 12 },
    title: { fontSize: 18, fontWeight: 600, color: '#e8f0fe' },
    subtitle: { fontSize: 12, color: '#8ba0b8', marginTop: 2 },
    statsRow: { display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' },
    statCard: { flex: 1, background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 10, padding: '14px 18px', minWidth: 100 },
    statNum: { fontSize: 28, fontWeight: 700, color: '#e8f0fe', fontFamily: 'JetBrains Mono, monospace' },
    statLabel: { fontSize: 11, color: '#4d6178', marginTop: 4, textTransform: 'uppercase', letterSpacing: '0.08em' },
    tableWrap: { background: 'rgba(255,255,255,0.015)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 10, overflow: 'hidden' },
    table: { width: '100%', borderCollapse: 'collapse' },
    th: { padding: '10px 14px', textAlign: 'left', fontSize: 11, fontWeight: 600, color: '#4d6178', textTransform: 'uppercase', letterSpacing: '0.06em', borderBottom: '1px solid rgba(255,255,255,0.06)', background: 'rgba(0,0,0,0.2)' },
    td: { padding: '10px 14px', fontSize: 13, color: '#d0d6e0', borderBottom: '1px solid rgba(255,255,255,0.04)' },
    badge: { display: 'inline-block', padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 500 },
    badgeActive: { background: 'rgba(29,158,117,0.12)', color: '#4ade80' },
    badgePending: { background: 'rgba(245,158,11,0.12)', color: '#fbbf24' },
    btn: { padding: '5px 10px', fontSize: 11, fontWeight: 500, borderRadius: 6, border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.04)', color: '#d0d6e0', cursor: 'pointer', marginRight: 6, fontFamily: 'Inter, system-ui, sans-serif' },
    btnApprove: { background: 'rgba(29,158,117,0.12)', borderColor: 'rgba(29,158,117,0.3)', color: '#4ade80' },
    btnDanger: { background: 'rgba(226,75,74,0.1)', borderColor: 'rgba(226,75,74,0.3)', color: '#ff6b6b' },
    btnAdd: { padding: '7px 16px', fontSize: 12, fontWeight: 500, borderRadius: 8, border: 'none', background: '#00d4ff', color: '#0f1724', cursor: 'pointer', fontFamily: 'Inter, system-ui, sans-serif' },
    addPanel: { background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 10, padding: 20, marginBottom: 20 },
    input: { padding: '8px 12px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 6, color: '#e8f0fe', fontSize: 13, fontFamily: 'Inter, system-ui, sans-serif', outline: 'none', width: 160 },
    modalOverlay: { position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 },
    modal: { background: '#141e2e', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 12, padding: 28, width: 340, maxWidth: '90vw' },
  };

  return (
    <div style={styles.container}>
      <style>{MOBILE_CSS}</style>

      <div style={styles.header}>
        <div>
          <div style={styles.title}>用户管理</div>
          <div style={styles.subtitle}>审批注册 · 管理账号 · 重置密码</div>
        </div>
        {!showAdd && <button style={styles.btnAdd} onClick={() => setShowAdd(true)}>+ 添加用户</button>}
      </div>

      {showAdd && (
        <div style={styles.addPanel}>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#e8f0fe', marginBottom: 12 }}>添加新用户</div>
          {addError && <div style={{ color: '#ff6b6b', fontSize: 12, marginBottom: 10 }}>{addError}</div>}
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <div><div style={{ fontSize: 11, color: '#8ba0b8', marginBottom: 4 }}>用户名</div><input style={styles.input} value={newUsername} onChange={e => setNewUsername(e.target.value)} placeholder="用户名" /></div>
            <div><div style={{ fontSize: 11, color: '#8ba0b8', marginBottom: 4 }}>密码</div><input style={{ ...styles.input, width: 140 }} type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)} placeholder="至少6位" /></div>
            <button style={styles.btnAdd} onClick={handleAdd}>确认添加</button>
            <button style={{ ...styles.btn, marginRight: 0 }} onClick={() => { setShowAdd(false); setAddError(''); }}>取消</button>
          </div>
        </div>
      )}

      <div className="admin-stats-row" style={styles.statsRow}>
        <div style={styles.statCard}><div style={{ ...styles.statNum, color: '#00d4ff' }}>{users.length}</div><div style={styles.statLabel}>总用户数</div></div>
        <div style={styles.statCard}><div style={styles.statNum}>{users.filter(u => u.is_active).length}</div><div style={styles.statLabel}>已激活</div></div>
        <div style={styles.statCard}><div style={{ ...styles.statNum, color: pendingCount > 0 ? '#f59e0b' : '#d0d6e0' }}>{pendingCount}</div><div style={styles.statLabel}>待审批</div></div>
      </div>

      {/* Desktop Table */}
      <div className="admin-table-wrap" style={styles.tableWrap}>
        {loading ? (
          <div style={{ padding: 32, textAlign: 'center', color: '#4d6178', fontSize: 13 }}>加载中...</div>
        ) : (
          <table style={styles.table}>
            <thead><tr>
              <th style={styles.th}>用户名</th><th style={styles.th}>状态</th><th style={styles.th}>角色</th>
              <th style={styles.th}>密码</th>
              <th style={styles.th}>注册时间</th><th style={styles.th}>最后登录</th><th style={styles.th}>操作</th>
            </tr></thead>
            <tbody>
              {users.map(u => (
                <tr key={u.id}>
                  <td style={{ ...styles.td, color: '#e8f0fe', fontWeight: 500 }}>{u.username}</td>
                  <td style={styles.td}>{u.is_active ? <span style={{ ...styles.badge, ...styles.badgeActive }}>已激活</span> : <span style={{ ...styles.badge, ...styles.badgePending }}>待审批</span>}</td>
                  <td style={{ ...styles.td, color: u.is_staff ? '#c084fc' : '#8ba0b8' }}>{u.is_staff ? '管理员' : '普通用户'}</td>
                  <td style={{ ...styles.td, color: '#4d6178', fontSize: 11 }}>
                    {u.password ? (
                      <span style={{ cursor: 'pointer', userSelect: 'none' }}
                        onClick={e => { e.currentTarget.textContent = e.currentTarget.textContent === '••••••' ? u.password : '••••••'; }}>
                        ••••••
                      </span>
                    ) : '-'}
                  </td>
                  <td style={{ ...styles.td, color: '#62666d', fontSize: 12 }}>{u.date_joined ? new Date(u.date_joined).toLocaleDateString('zh-CN') : '-'}</td>
                  <td style={{ ...styles.td, color: '#62666d', fontSize: 12 }}>{u.last_login ? new Date(u.last_login).toLocaleString('zh-CN') : '从未登录'}</td>
                  <td style={styles.td}>
                    {!u.is_active && (<>
                      <button style={{ ...styles.btn, ...styles.btnApprove }} onClick={() => handleApprove(u.id, u.username)}>通过</button>
                      <button style={{ ...styles.btn, ...styles.btnDanger }} onClick={() => handleReject(u.id, u.username)}>拒绝</button>
                    </>)}
                    <button style={styles.btn} onClick={() => { setResetModal(u); setResetPwd(''); }}>重置密码</button>
                    {u.id !== 1 && <button style={{ ...styles.btn, ...styles.btnDanger }} onClick={() => handleDelete(u.id, u.username)}>删除</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Mobile Cards */}
      <div className="admin-mobile-cards">
        {loading ? (
          <div style={{ padding: 32, textAlign: 'center', color: '#4d6178', fontSize: 13 }}>加载中...</div>
        ) : users.length === 0 ? (
          <div style={{ padding: 32, textAlign: 'center', color: '#4d6178' }}>暂无用户</div>
        ) : (
          users.map(u => (
            <div key={u.id} className="admin-mobile-card">
              <div className="admin-mobile-card-row">
                <span className="label">用户名</span>
                <span className="value" style={{ color: '#e8f0fe', fontWeight: 500 }}>{u.username}</span>
              </div>
              <div className="admin-mobile-card-row">
                <span className="label">状态</span>
                <span className="value">{u.is_active ? <span style={{ color: '#4ade80', background: 'rgba(29,158,117,0.12)', padding: '2px 10px', borderRadius: 10, fontSize: 12 }}>已激活</span> : <span style={{ color: '#fbbf24', background: 'rgba(245,158,11,0.12)', padding: '2px 10px', borderRadius: 10, fontSize: 12 }}>待审批</span>}</span>
              </div>
              <div className="admin-mobile-card-row">
                <span className="label">密码</span>
                <span className="value" style={{ fontSize: 11, cursor: 'pointer', userSelect: 'none' }}
                  onClick={e => { e.currentTarget.textContent = e.currentTarget.textContent === '••••••' ? (u.password || '-') : '••••••'; }}>
                  ••••••
                </span>
              </div>
              <div className="admin-mobile-card-row">
                <span className="label">角色</span>
                <span className="value" style={{ color: u.is_staff ? '#c084fc' : '#8ba0b8' }}>{u.is_staff ? '管理员' : '普通用户'}</span>
              </div>
              <div className="admin-mobile-card-actions">
                {!u.is_active && <>
                  <button className="btn-approve" onClick={() => handleApprove(u.id, u.username)}>✓ 通过</button>
                  <button className="btn-danger" onClick={() => handleReject(u.id, u.username)}>✕ 拒绝</button>
                </>}
                <button onClick={() => { setResetModal(u); setResetPwd(''); }}>🔑 重置</button>
                {u.id !== 1 && <button className="btn-danger" onClick={() => handleDelete(u.id, u.username)}>🗑 删除</button>}
              </div>
            </div>
          ))
        )}
      </div>

      {resetModal && (
        <div style={styles.modalOverlay} onClick={() => setResetModal(null)}>
          <div style={styles.modal} onClick={e => e.stopPropagation()}>
            <div style={{ fontSize: 16, fontWeight: 600, color: '#e8f0fe', marginBottom: 8 }}>重置密码</div>
            <div style={{ fontSize: 13, color: '#8ba0b8', marginBottom: 16 }}>用户：{resetModal.username}</div>
            <input type="password" style={{ ...styles.input, width: '100%', marginBottom: 12 }} value={resetPwd} onChange={e => setResetPwd(e.target.value)} placeholder="新密码（至少6位）" autoFocus />
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button style={styles.btn} onClick={() => setResetModal(null)}>取消</button>
              <button style={{ ...styles.btn, ...styles.btnApprove }} onClick={handleReset}>确认重置</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
