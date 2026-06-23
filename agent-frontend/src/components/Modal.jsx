import React, { useState } from 'react';
import { api } from '../api';

export default function Modal({ type, data, onClose, addToast, tasks, setTasks, agents, setAgents, skills, setSkills, memory, setMemory, sessions, setSessions }) {
  if (!type) return null;

  const MODALS = {
    createTask: <CreateTaskForm onClose={onClose} addToast={addToast} tasks={tasks} setTasks={setTasks} agents={agents} />,
    deployAgent: <DeployAgentForm onClose={onClose} addToast={addToast} agents={agents} setAgents={setAgents} />,
    registerSkill: <RegisterSkillForm onClose={onClose} addToast={addToast} skills={skills} setSkills={setSkills} />,
    addMemory: <AddMemoryForm onClose={onClose} addToast={addToast} memory={memory} setMemory={setMemory} />,
    newSession: <NewSessionForm onClose={onClose} addToast={addToast} sessions={sessions} setSessions={setSessions} agents={agents} />,
    taskDetail: <TaskDetailView data={data} onClose={onClose} />,
  };

  const titles = { createTask:'新建任务', deployAgent:'部署新 Agent', registerSkill:'注册新技能', addMemory:'添加记忆条目', newSession:'新建会话' };

  return (
    <div className="modal-overlay open" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal">
        <div className="modal-header">
          <h2 className="modal-title">{titles[type]}</h2>
          <button className="modal-close" onClick={onClose} aria-label="关闭">
            <svg viewBox="0 0 16 16" fill="none" width="16" height="16"><path d="M3 3l10 10M13 3L3 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
          </button>
        </div>
        <div className="modal-body">{MODALS[type]}</div>
      </div>
    </div>
  );
}

function CreateTaskForm({ onClose, addToast, tasks, setTasks, agents }) {
  const [name, setName] = useState('');
  const [agent, setAgent] = useState('自动分配');
  const [priority, setPriority] = useState('medium');
  const [desc, setDesc] = useState('');

  const submit = () => {
    if (!name.trim()) return addToast('请输入任务名称', 'error');
    const newTask = {
      id: 'T' + String(tasks.length + 1).padStart(3, '0'),
      name: name.trim(),
      agent,
      priority,
      status: 'pending',
      progress: 0,
      created: new Date().toLocaleString('zh-CN', { month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit', hour12:false }).replace(/\//g, '-'),
      desc,
      skills: [],
    };
    setTasks([newTask, ...tasks]);
    addToast('任务创建成功', 'success');
    onClose();
  };

  return (
    <>
      <div className="form-group"><label className="form-label">任务名称 *</label><input className="form-input" value={name} onChange={e => setName(e.target.value)} placeholder="描述这个任务要做什么" /></div>
      <div className="form-row">
        <div className="form-group"><label className="form-label">分配 Agent</label>
          <select className="form-input" value={agent} onChange={e => setAgent(e.target.value)}>
            <option>自动分配</option>
            {agents.filter(a => a.status !== 'offline').map(a => <option key={a.id}>{a.name}</option>)}
          </select></div>
        <div className="form-group"><label className="form-label">优先级</label>
          <select className="form-input" value={priority} onChange={e => setPriority(e.target.value)}>
            <option value="medium">中</option><option value="high">高</option><option value="low">低</option>
          </select></div>
      </div>
      <div className="form-group"><label className="form-label">任务描述</label><textarea className="form-input" value={desc} onChange={e => setDesc(e.target.value)} placeholder="详细描述任务目标..." /></div>
      <div className="modal-footer">
        <button className="btn btn-ghost" onClick={onClose}>取消</button>
        <button className="btn btn-primary" onClick={submit}>创建任务</button>
      </div>
    </>
  );
}

function DeployAgentForm({ onClose, addToast, agents, setAgents }) {
  const [name, setName] = useState('');
  const [type, setType] = useState('通用助手');
  const [model, setModel] = useState('Claude-3.5-Sonnet');
  const [prompt, setPrompt] = useState('');

  const submit = () => {
    if (!name.trim()) return addToast('请输入Agent名称', 'error');
    const colors = ['blue','green','purple','amber','coral'];
    const newAgent = {
      id: 'A' + String(agents.length + 1).padStart(3, '0'),
      name: name.trim(),
      type, status: 'online', model,
      tasks: 0, cpu: '2%', mem: '0.4GB',
      skills: [],
      color: colors[Math.floor(Math.random() * colors.length)],
      uptime: '刚刚启动',
      desc: prompt || '新部署的Agent',
    };
    setAgents([...agents, newAgent]);
    addToast(`${name} 部署成功`, 'success');
    onClose();
  };

  return (
    <>
      <div className="form-group"><label className="form-label">Agent 名称</label><input className="form-input" value={name} onChange={e => setName(e.target.value)} placeholder="e.g. LegalAgent" /></div>
      <div className="form-row">
        <div className="form-group"><label className="form-label">Agent 类型</label>
          <select className="form-input" value={type} onChange={e => setType(e.target.value)}>
            <option>通用助手</option><option>文档处理</option><option>代码分析</option><option>数据处理</option><option>视觉理解</option>
          </select></div>
        <div className="form-group"><label className="form-label">基础模型</label>
          <select className="form-input" value={model} onChange={e => setModel(e.target.value)}>
            <option>Claude-3.5-Sonnet</option><option>GPT-4o</option><option>Gemini-1.5</option>
          </select></div>
      </div>
      <div className="form-group"><label className="form-label">系统提示词</label><textarea className="form-input" value={prompt} onChange={e => setPrompt(e.target.value)} placeholder="定义 Agent 的角色和行为规范..." /></div>
      <div className="modal-footer">
        <button className="btn btn-ghost" onClick={onClose}>取消</button>
        <button className="btn btn-primary" onClick={submit}>部署</button>
      </div>
    </>
  );
}

function RegisterSkillForm({ onClose, addToast, skills, setSkills }) {
  const [name, setName] = useState('');
  const [cat, setCat] = useState('NLP');
  const [desc, setDesc] = useState('');
  const [sType, setSType] = useState('Python函数');

  const submit = () => {
    if (!name.trim()) return addToast('请输入技能名称', 'error');
    const colors = ['blue','green','purple','amber','coral'];
    const newSkill = {
      id: 'S' + String(skills.length + 1).padStart(3, '0'),
      name: name.trim(), category: cat, desc,
      version:'1.0.0', usage:0, icon:'⚡',
      color: colors[Math.floor(Math.random() * colors.length)],
      type: sType, author: '当前用户',
    };
    setSkills([...skills, newSkill]);
    addToast(`${name} 注册成功`, 'success');
    onClose();
  };

  return (
    <>
      <div className="form-row">
        <div className="form-group"><label className="form-label">技能名称</label><input className="form-input" value={name} onChange={e => setName(e.target.value)} placeholder="技能显示名称" /></div>
        <div className="form-group"><label className="form-label">分类</label>
          <select className="form-input" value={cat} onChange={e => setCat(e.target.value)}>
            <option>NLP</option><option>文档</option><option>开发</option><option>视觉</option><option>数据库</option><option>监控</option>
          </select></div>
      </div>
      <div className="form-group"><label className="form-label">技能描述</label><input className="form-input" value={desc} onChange={e => setDesc(e.target.value)} placeholder="简短描述" /></div>
      <div className="form-group"><label className="form-label">实现方式</label>
        <select className="form-input" value={sType} onChange={e => setSType(e.target.value)}><option>Python 函数</option><option>HTTP API</option><option>MCP 协议</option></select></div>
      <div className="modal-footer">
        <button className="btn btn-ghost" onClick={onClose}>取消</button>
        <button className="btn btn-primary" onClick={submit}>注册</button>
      </div>
    </>
  );
}

function AddMemoryForm({ onClose, addToast, memory, setMemory }) {
  const [type, setType] = useState('fact');
  const [content, setContent] = useState('');
  const [agent, setAgent] = useState('');
  const [tags, setTags] = useState('');

  const submit = () => {
    if (!content.trim()) return addToast('请输入记忆内容', 'error');
    const newMem = {
      id: 'M' + String(memory.length + 1).padStart(3, '0'),
      type, content: content.trim(),
      agent: agent || 'System',
      time: new Date().toLocaleString('zh-CN', { month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit', hour12:false }).replace(/\//g, '-'),
      tags: tags.split(',').map(s => s.trim()).filter(Boolean),
    };
    setMemory([newMem, ...memory]);
    addToast('记忆添加成功', 'success');
    onClose();
  };

  return (
    <>
      <div className="form-group"><label className="form-label">记忆类型</label>
        <select className="form-input" value={type} onChange={e => setType(e.target.value)}>
          <option value="fact">事实 (Fact)</option><option value="conversation">对话 (Conversation)</option>
          <option value="skill">技能 (Skill)</option><option value="context">上下文 (Context)</option>
        </select></div>
      <div className="form-group"><label className="form-label">内容 *</label><textarea className="form-input" style={{minHeight:120}} value={content} onChange={e => setContent(e.target.value)} placeholder="记录需要持久化的信息..." /></div>
      <div className="form-group"><label className="form-label">关联 Agent</label><input className="form-input" value={agent} onChange={e => setAgent(e.target.value)} placeholder="归属哪个Agent" /></div>
      <div className="form-group"><label className="form-label">标签（逗号分隔）</label><input className="form-input" value={tags} onChange={e => setTags(e.target.value)} placeholder="e.g. 用户偏好,配置" /></div>
      <div className="modal-footer">
        <button className="btn btn-ghost" onClick={onClose}>取消</button>
        <button className="btn btn-primary" onClick={submit}>添加</button>
      </div>
    </>
  );
}

function NewSessionForm({ onClose, addToast, sessions, setSessions, agents }) {
  const [title, setTitle] = useState('');
  const [agentId, setAgentId] = useState('');

  const submit = async () => {
    if (!agentId) return addToast('请选择一个 Agent', 'error');
    try {
      const data = await api.post('/conversations/', {
        title: title.trim() || '新会话',
        agent: parseInt(agentId),
      });
      setSessions(prev => [{ ...data, message_count: 0 }, ...prev]);
      addToast('会话已创建', 'success');
      onClose();
    } catch (e) { addToast('创建失败: ' + (e.message || '未知错误'), 'error'); }
  };

  return (
    <>
      <div className="form-group"><label className="form-label">对话标题</label><input className="form-input" value={title} onChange={e => setTitle(e.target.value)} placeholder="给对话起个名字..." /></div>
      <div className="form-group"><label className="form-label">选择 Agent</label>
        <select className="form-input" value={agentId} onChange={e => setAgentId(e.target.value)}>
          <option value="">选择 Agent...</option>
          {agents.map(a => <option key={a.id} value={a.id}>{a.name}{a.portrait ? ' — ' + a.portrait : ''}</option>)}
        </select></div>
      <div className="modal-footer">
        <button className="btn btn-ghost" onClick={onClose}>取消</button>
        <button className="btn btn-primary" onClick={submit} disabled={!agentId}>创建会话</button>
      </div>
    </>
  );
}

function TaskDetailView({ data: t, onClose }) {
  const statusCN = { completed:'已完成', in_progress:'执行中', running:'运行中', pending:'待执行', failed:'失败' };
  return (
    <>
      <div style={{display:'flex',alignItems:'center',gap:12,marginBottom:16}}>
        <div style={{width:48,height:48,borderRadius:14,background:'var(--bg-hover)',display:'flex',alignItems:'center',justifyContent:'center',fontSize:16,fontWeight:700,color:'var(--cyan)'}}>#{t.id}</div>
        <div><div style={{fontSize:16,fontWeight:600}}>{t.title}</div><div style={{fontSize:11,color:'var(--text-muted)'}}>{t.agent_name || '未分配'} · {statusCN[t.status]||t.status}</div></div>
      </div>
      <div className="detail-section"><div className="detail-section-title">基本信息</div>
        <div className="detail-kv">
          <span className="detail-key">状态</span><span className="detail-val"><span className={`status-badge ${t.status}`}>{statusCN[t.status]||t.status}</span></span>
          <span className="detail-key">优先级</span><span className="detail-val"><span className={`priority-badge ${t.priority||'medium'}`}>{t.priority==='high'?'高':t.priority==='low'?'低':'中'}</span></span>
          <span className="detail-key">来源</span><span className="detail-val">{t.source_label || t.source || '—'}</span>
          <span className="detail-key">创建</span><span className="detail-val">{t.created_at?new Date(t.created_at).toLocaleString():'—'}</span>
        </div>
      </div>
      {t.description && <div className="detail-section"><div className="detail-section-title">描述</div><p className="detail-desc">{t.description}</p></div>}
    </>
  );
}
