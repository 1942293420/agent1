import React, { useState } from 'react';
import { useApp } from '../../AppContext';

const PAGES = {
  general: (
    <>
      <div className="settings-group"><div className="settings-group-title">基本信息</div>
        <div className="setting-row"><div><div className="setting-label">平台名称</div><div className="setting-desc">显示在导航栏的系统名称</div></div><div className="setting-control"><input type="text" defaultValue="AgentOS" className="form-input" style={{minWidth:200}} /></div></div>
        <div className="setting-row"><div><div className="setting-label">系统语言</div></div><div className="setting-control"><select className="form-input" style={{minWidth:160}} defaultValue="简体中文"><option>简体中文</option><option>English</option><option>日本語</option></select></div></div>
        <div className="setting-row"><div><div className="setting-label">时区</div></div><div className="setting-control"><select className="form-input" style={{minWidth:160}} defaultValue="Asia/Shanghai (UTC+8)"><option>Asia/Shanghai (UTC+8)</option><option>UTC</option><option>America/New_York</option></select></div></div>
      </div>
      <div className="settings-group"><div className="settings-group-title">界面偏好</div>
        <SettingToggle label="实时数据刷新" desc="每 4 秒自动更新仪表盘数据" defaultChecked />
        <SettingToggle label="侧边栏默认折叠" />
        <SettingToggle label="紧凑模式" desc="减小卡片间距和内边距" />
      </div>
    </>
  ),
  model: (
    <div className="settings-group"><div className="settings-group-title">默认模型配置</div>
      <div className="setting-row"><div><div className="setting-label">主力模型</div><div className="setting-desc">用于复杂推理任务</div></div><div className="setting-control"><select className="form-input" style={{minWidth:180}} defaultValue="Claude-3.5-Sonnet"><option>Claude-3.5-Sonnet</option><option>GPT-4o</option><option>Gemini-1.5-Pro</option><option>DeepSeek-V3</option></select></div></div>
      <div className="setting-row"><div><div className="setting-label">快速模型</div><div className="setting-desc">用于简单分类和轻量任务</div></div><div className="setting-control"><select className="form-input" style={{minWidth:180}} defaultValue="Claude-3-Haiku"><option>Claude-3-Haiku</option><option>GPT-4o-mini</option><option>Gemini-Flash</option></select></div></div>
      <div className="setting-row"><div><div className="setting-label">最大 Token 数</div></div><div className="setting-control"><input type="number" defaultValue="4096" className="form-input" style={{minWidth:120}} /></div></div>
      <div className="setting-row"><div><div className="setting-label">温度系数</div><div className="setting-desc">0.0 = 确定性输出，1.0 = 最大创造力</div></div><div className="setting-control"><input type="number" defaultValue="0.7" step="0.1" min="0" max="1" className="form-input" style={{minWidth:120}} /></div></div>
      <div className="setting-row"><div><div className="setting-label">上下文窗口</div></div><div className="setting-control"><select className="form-input" style={{minWidth:160}} defaultValue="128K"><option>自动</option><option>8K</option><option>32K</option><option>128K</option><option>200K</option></select></div></div>
    </div>
  ),
  security: (
    <div className="settings-group"><div className="settings-group-title">认证设置</div>
      <SettingToggle label="API 密钥轮换" desc="定期自动更新 API 访问密钥" defaultChecked />
      <SettingToggle label="双因素认证" />
      <div className="setting-row"><div><div className="setting-label">会话超时（分钟）</div></div><div className="setting-control"><input type="number" defaultValue="60" className="form-input" style={{minWidth:120}} /></div></div>
      <div className="setting-row"><div><div className="setting-label">IP 白名单</div></div><div className="setting-control"><input type="text" defaultValue="10.0.0.0/8, 172.16.0.0/12" className="form-input" style={{minWidth:200}} /></div></div>
    </div>
  ),
  notification: (
    <div className="settings-group"><div className="settings-group-title">通知渠道</div>
      <SettingToggle label="站内通知" defaultChecked />
      <SettingToggle label="邮件告警" defaultChecked />
      <SettingToggle label="Webhook 推送" />
      <div className="setting-row"><div><div className="setting-label">告警接收邮箱</div></div><div className="setting-control"><input type="text" defaultValue="admin@example.com" className="form-input" style={{minWidth:200}} /></div></div>
      <div className="setting-row"><div><div className="setting-label">Webhook URL</div></div><div className="setting-control"><input type="text" defaultValue="https://hooks.example.com/alert" className="form-input" style={{minWidth:240}} /></div></div>
    </div>
  ),
};

function SettingToggle({ label, desc, defaultChecked, onChange }) {
  const [checked, setChecked] = useState(defaultChecked || false);
  return (
    <div className="setting-row">
      <div><div className="setting-label">{label}</div>{desc && <div className="setting-desc">{desc}</div>}</div>
      <div className="setting-control"><label className="switch"><input type="checkbox" checked={checked} onChange={e => { setChecked(e.target.checked); onChange?.(e.target.checked); }} /><span className="switch-track" /></label></div>
    </div>
  );
}

export default function Settings() {
  const { addToast } = useApp();
  const [tab, setTab] = useState('general');
  const tabs = { general:'基本设置', model:'模型配置', security:'安全认证', notification:'通知设置' };

  return (
    <>
      <div className="view-header">
        <h1 className="view-title">系统设置</h1>
        <div className="view-actions">
          <button className="btn btn-primary" onClick={() => addToast('设置已保存', 'success')}>保存更改</button>
        </div>
      </div>
      <div className="settings-layout">
        <div className="settings-nav">
          {Object.entries(tabs).map(([k,v]) => (
            <button key={k} className={`settings-nav-item${tab===k?' active':''}`} onClick={() => setTab(k)}>{v}</button>
          ))}
        </div>
        <div className="settings-content">{PAGES[tab]}</div>
      </div>
    </>
  );
}
