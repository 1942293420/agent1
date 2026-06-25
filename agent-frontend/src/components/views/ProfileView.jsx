import React, { useState, useRef } from 'react';
import { useAuth } from '../../AuthContext';

const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const MAX_SIZE = 2 * 1024 * 1024;

export default function ProfileView() {
  const { user, login } = useAuth();
  const fileRef = useRef(null);

  const localProfile = (() => { try { return JSON.parse(localStorage.getItem('agentos_profile') || '{}'); } catch { return {}; } })();

  const [nickname, setNickname] = useState(user?.display_name || localProfile.nickname || '');
  const [bio, setBio] = useState(localProfile.bio || '');
  const [role, setRole] = useState(localProfile.role || '');
  const [avatarPreview, setAvatarPreview] = useState(localProfile.avatarUrl || null);
  const [saving, setSaving] = useState(false);

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!ALLOWED_TYPES.includes(file.type)) { alert('仅支持 JPG/PNG/WebP'); return; }
    if (file.size > MAX_SIZE) { alert('不超过 2MB'); return; }
    const reader = new FileReader();
    reader.onload = (ev) => setAvatarPreview(ev.target.result);
    reader.readAsDataURL(file);
  };

  const handleSave = async () => {
    const displayName = nickname.trim();
    setSaving(true);

    // Save to backend
    try {
      await fetch('/api/auth/profile/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ display_name: displayName }),
        credentials: 'include',
      });
    } catch (e) { /* ignore */ }

    // Save avatar/bio to localStorage
    const local = {
      nickname: displayName,
      bio: bio.trim(),
      role: role.trim(),
      avatarUrl: avatarPreview,
      updatedAt: new Date().toISOString(),
    };
    localStorage.setItem('agentos_profile', JSON.stringify(local));

    // Update AuthContext user object
    if (user) {
      login({ ...user, display_name: displayName });
    }

    setSaving(false);
    alert('保存成功');
  };

  const initials = (nickname || user?.username || '用').slice(0, 2).toUpperCase();

  return (
    <>
      <div className="view-header">
        <h1 className="view-title">个人资料</h1>
      </div>

      <div style={{ maxWidth: 560, margin: '0 auto' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '32px 0 24px', gap: 12 }}>
          <div style={{ position: 'relative', width: 96, height: 96 }}>
            {avatarPreview ? (
              <img src={avatarPreview} alt="" style={{ width: 96, height: 96, borderRadius: '50%', objectFit: 'cover', border: '2px solid var(--border-subtle)' }} />
            ) : (
              <div style={{ width: 96, height: 96, borderRadius: '50%', background: 'linear-gradient(135deg, var(--blue), var(--purple))', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 28, fontWeight: 600, color: '#fff' }}>{initials}</div>
            )}
            <button onClick={() => fileRef.current?.click()} style={{ position: 'absolute', bottom: 2, right: 2, width: 30, height: 30, borderRadius: '50%', background: 'var(--bg-card)', border: '1px solid var(--border-default)', cursor: 'pointer' }}>📷</button>
          </div>
          <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" onChange={handleFileChange} style={{ display: 'none' }} />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, paddingBottom: 24 }}>
          <div>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 500, color: '#8ba0b8', marginBottom: 6 }}>昵称</label>
            <input style={{ width: '100%', padding: '10px 14px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, color: '#e8f0fe', fontSize: 15, fontFamily: 'Inter, sans-serif', outline: 'none' }}
              value={nickname} onChange={e => setNickname(e.target.value)} placeholder="你的显示名称" maxLength={32} />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 500, color: '#8ba0b8', marginBottom: 6 }}>角色</label>
            <input style={{ width: '100%', padding: '10px 14px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, color: '#e8f0fe', fontSize: 15, fontFamily: 'Inter, sans-serif', outline: 'none' }}
              value={role} onChange={e => setRole(e.target.value)} placeholder="如：管理员、开发者..." maxLength={32} />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 500, color: '#8ba0b8', marginBottom: 6 }}>简介</label>
            <textarea style={{ width: '100%', padding: '10px 14px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, color: '#e8f0fe', fontSize: 15, fontFamily: 'Inter, sans-serif', outline: 'none', minHeight: 100, resize: 'vertical' }}
              value={bio} onChange={e => setBio(e.target.value)} placeholder="介绍一下自己..." rows={4} maxLength={500} />
          </div>
        </div>

        <button className="btn btn-primary" onClick={handleSave} disabled={saving} style={{ width: '100%', padding: '12px 0', fontSize: 15 }}>
          {saving ? '保存中...' : '💾 保存'}
        </button>
      </div>
    </>
  );
}
