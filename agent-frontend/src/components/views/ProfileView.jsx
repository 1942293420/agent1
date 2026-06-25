import React, { useState, useRef, useEffect } from 'react';
import { useApp } from '../../AppContext';

const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const MAX_SIZE = 2 * 1024 * 1024; // 2MB

export default function ProfileView() {
  const { addToast } = useApp();
  const fileRef = useRef(null);

  const [profile, setProfile] = useState(() => {
    try { return JSON.parse(localStorage.getItem('agentos_profile') || '{}'); }
    catch { return {}; }
  });

  const [nickname, setNickname] = useState(profile.nickname || '');
  const [bio, setBio] = useState(profile.bio || '');
  const [role, setRole] = useState(profile.role || '');
  const [avatarPreview, setAvatarPreview] = useState(profile.avatarUrl || null);
  const [avatarFile, setAvatarFile] = useState(null);

  useEffect(() => {
    setNickname(profile.nickname || '');
    setBio(profile.bio || '');
    setRole(profile.role || '');
    setAvatarPreview(profile.avatarUrl || null);
  }, []);

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // MIME check
    if (!ALLOWED_TYPES.includes(file.type)) {
      addToast('仅支持 JPG、PNG、WebP 格式', 'error');
      e.target.value = '';
      return;
    }

    // Size check
    if (file.size > MAX_SIZE) {
      addToast('文件大小不能超过 2MB', 'error');
      e.target.value = '';
      return;
    }

    // Preview
    const reader = new FileReader();
    reader.onload = (ev) => {
      setAvatarPreview(ev.target.result);
      setAvatarFile(file);
    };
    reader.readAsDataURL(file);
  };

  const handleSave = () => {
    const updated = {
      ...profile,
      nickname: nickname.trim(),
      bio: bio.trim(),
      role: role.trim(),
      avatarUrl: avatarPreview || profile.avatarUrl,
      updatedAt: new Date().toISOString(),
    };
    localStorage.setItem('agentos_profile', JSON.stringify(updated));
    setProfile(updated);
    addToast('个人资料已保存', 'success');
    setAvatarFile(null);
  };

  const initials = (nickname || profile.nickname || '用户').slice(0, 2).toUpperCase();

  return (
    <>
      <div className="view-header">
        <h1 className="view-title">个人资料</h1>
        <div className="view-actions">
          <button className="btn btn-primary" onClick={handleSave}>
            💾 保存
          </button>
        </div>
      </div>

      <div style={{ maxWidth: 560, margin: '0 auto' }}>
        {/* Avatar section */}
        <div className="profile-avatar-section">
          <div className="profile-avatar-wrap">
            {avatarPreview ? (
              <img src={avatarPreview} alt="头像" className="profile-avatar-img" />
            ) : (
              <div className="profile-avatar-placeholder">{initials}</div>
            )}
            <button
              className="profile-avatar-edit"
              onClick={() => fileRef.current?.click()}
              title="更换头像"
            >
              📷
            </button>
          </div>
          <input
            ref={fileRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={handleFileChange}
            style={{ display: 'none' }}
          />
          <div className="profile-avatar-hint">
            点击更换头像 · 支持 JPG/PNG/WebP · 不超过 2MB
          </div>
        </div>

        {/* Form */}
        <div className="profile-form">
          <div className="form-group">
            <label className="form-label">昵称</label>
            <input
              className="form-input"
              value={nickname}
              onChange={e => setNickname(e.target.value)}
              placeholder="你的显示名称"
              maxLength={32}
            />
          </div>
          <div className="form-group">
            <label className="form-label">角色 / 职位</label>
            <input
              className="form-input"
              value={role}
              onChange={e => setRole(e.target.value)}
              placeholder="如：管理员、开发者..."
              maxLength={32}
            />
          </div>
          <div className="form-group">
            <label className="form-label">个人简介</label>
            <textarea
              className="form-input"
              value={bio}
              onChange={e => setBio(e.target.value)}
              placeholder="介绍一下自己..."
              rows={4}
              style={{ minHeight: 100, resize: 'vertical' }}
              maxLength={500}
            />
            <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4, textAlign: 'right' }}>
              {bio.length}/500
            </div>
          </div>
        </div>

        {/* Preview card */}
        <div className="profile-preview-card">
          <div className="profile-preview-title">顶部导航栏预览</div>
          <div className="profile-preview-bar">
            <div className="profile-preview-user">
              {avatarPreview ? (
                <img src={avatarPreview} alt="" className="profile-preview-avatar" />
              ) : (
                <div className="profile-preview-init">{initials}</div>
              )}
              <span>{nickname || '用户'}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Inline CSS */}
      <style>{`
        .profile-avatar-section {
          display: flex; flex-direction: column; align-items: center;
          padding: 32px 0 24px; gap: 12px;
        }
        .profile-avatar-wrap {
          position: relative; width: 96px; height: 96px;
        }
        .profile-avatar-img {
          width: 96px; height: 96px; border-radius: 50%;
          object-fit: cover; border: 2px solid var(--border-subtle);
        }
        .profile-avatar-placeholder {
          width: 96px; height: 96px; border-radius: 50%;
          background: linear-gradient(135deg, var(--blue), var(--purple));
          display: flex; align-items: center; justify-content: center;
          font-size: 28px; font-weight: 600; color: #fff;
          border: 2px solid var(--border-subtle);
        }
        .profile-avatar-edit {
          position: absolute; bottom: 2px; right: 2px;
          width: 30px; height: 30px; border-radius: 50%;
          background: var(--bg-card); border: 1px solid var(--border-default);
          cursor: pointer; font-size: 14px; display: flex;
          align-items: center; justify-content: center;
          transition: all var(--transition);
        }
        .profile-avatar-edit:hover { border-color: var(--cyan); }
        .profile-avatar-hint {
          font-size: 11px; color: var(--text-muted); text-align: center;
        }
        .profile-form {
          display: flex; flex-direction: column; gap: 16px;
          padding: 0 0 24px;
        }
        .profile-preview-card {
          background: var(--bg-card); border: 1px solid var(--border-subtle);
          border-radius: var(--radius); padding: 16px; margin-bottom: 32px;
        }
        .profile-preview-title {
          font-size: 11px; color: var(--text-muted); margin-bottom: 10px;
        }
        .profile-preview-bar {
          display: flex; align-items: center; justify-content: flex-end;
          padding: 8px 12px; background: rgba(13,19,32,.95);
          border: 1px solid var(--border-subtle); border-radius: 8px;
        }
        .profile-preview-user {
          display: flex; align-items: center; gap: 8px;
          padding: 4px 10px 4px 4px; border-radius: 8px;
          border: 1px solid var(--border-subtle);
          font-size: 12px; color: var(--text-secondary);
        }
        .profile-preview-avatar {
          width: 24px; height: 24px; border-radius: 50%; object-fit: cover;
        }
        .profile-preview-init {
          width: 24px; height: 24px; border-radius: 50%;
          background: linear-gradient(135deg, var(--blue), var(--purple));
          display: flex; align-items: center; justify-content: center;
          font-size: 10px; font-weight: 600; color: #fff;
        }
      `}</style>
    </>
  );
}
