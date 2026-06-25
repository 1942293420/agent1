import React, { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../../api';
import { useApp } from '../../AppContext';
import MessageRenderer from '../chat/MessageRenderer';
import '../chat/messageStyles.css';

const MSG_GAP_MINUTES = 5;

function fmtTime(ts) {
  if (!ts) return '';
  const d = new Date(ts);
  const now = new Date();
  const time = d.toLocaleTimeString('zh-CN', { hour:'2-digit', minute:'2-digit' });
  if (d.toDateString() === now.toDateString()) return `今天 ${time}`;
  const yesterday = new Date(now); yesterday.setDate(now.getDate() - 1);
  if (d.toDateString() === yesterday.toDateString()) return `昨天 ${time}`;
  return `${d.toLocaleDateString('zh-CN', { month:'short', day:'numeric' })} ${time}`;
}

// Simple markdown → HTML
function renderMarkdown(md) {
  if (!md) return '';
  let html = md
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="md-code"><code>$2</code></pre>')
    .replace(/`([^`]+)`/g, '<code class="md-inline">$1</code>')
    .replace(/^#### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>[\s\S]*?<\/li>)/g, '<ul>$1</ul>')
    .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
    .replace(/^---$/gm, '<hr>')
    .replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>');
  html = '<p>' + html + '</p>';
  html = html.replace(/<pre class="md-code">([\s\S]*?)<\/pre>/g, (m, code) => {
    return '<pre class="md-code"><code>' + code.replace(/<\/?p>/g, '').replace(/<br>/g, '\n') + '</code></pre>';
  });
  return html;
}

// Resize hook
function useResize(defaultSize, min, max, direction) {
  const [size, setSize] = useState(defaultSize);
  const dragging = useRef(false);
  const startPos = useRef(0);
  const startSize = useRef(defaultSize);

  const onMouseDown = useCallback((e) => {
    e.preventDefault();
    dragging.current = true;
    startPos.current = direction === 'x' ? e.clientX : e.clientY;
    startSize.current = size;
    document.body.style.cursor = direction === 'x' ? 'col-resize' : 'row-resize';
    document.body.style.userSelect = 'none';
  }, [size, direction]);

  useEffect(() => {
    const onMouseMove = (e) => {
      if (!dragging.current) return;
      const delta = (direction === 'x' ? e.clientX : e.clientY) - startPos.current;
      const newSize = Math.max(min, Math.min(max, startSize.current + delta));
      setSize(newSize);
    };
    const onMouseUp = () => {
      if (dragging.current) {
        dragging.current = false;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
      }
    };
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };
  }, [direction, min, max]);

  return { size, onMouseDown };
}

export default function Sessions() {
  const { sessions, setSessions, agents, addToast, openModal, activeSessionId, setActiveSessionId } = useApp();
  const [active, setActive] = useState(activeSessionId);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [loadingMsgs, setLoadingMsgs] = useState(false);
  const [orchProgress, setOrchProgress] = useState(null);
  const [orchState, setOrchState] = useState('idle');
  const [showScrollBtn, setShowScrollBtn] = useState(false);
  const [copiedId, setCopiedId] = useState(null);
  const [animSwitch, setAnimSwitch] = useState(false);
  const [hoveredMsgId, setHoveredMsgId] = useState(null);
  const [showOutput, setShowOutput] = useState(false);
  const [outputContent, setOutputContent] = useState('');
  const [outputCopied, setOutputCopied] = useState(false);
  const [outputFullscreen, setOutputFullscreen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [attachedFiles, setAttachedFiles] = useState([]);  // files in input that will be sent
  const [msgFiles, setMsgFiles] = useState({});
  const messagesEnd = useRef(null);
  const chatContainer = useRef(null);
  const scrollPositions = useRef({});
  const userScrolledUp = useRef(false);
  const prevMsgCount = useRef(0);

  // Resizable: session list width (200–500)
  const listResize = useResize(280, 200, 500, 'x');

  const activeSession = sessions.find(s => s.id === active);

  // Agent role labels
  const agentRoles = {
    '豆角云枢': '决策中心 · 多Agent协同调度',
    '云枢': '决策中心 · 多Agent协同调度',
    'Banni': '小温 · 飞书助手',
    'Basir': '范先生 · 主力Agent',
  };
  const agentRole = activeSession ? (agentRoles[activeSession.agent_name] || '') : '';

  // Poll messages
  useEffect(() => {
    if (!active) { setMessages([]); return; }
    let cancelled = false;
    setLoadingMsgs(true);
    const poll = async () => {
      try {
        const data = await api.get('/conversations/' + active + '/');
        if (cancelled) return;
        setMessages(data.messages || []);
        setSessions(prev => prev.map(s => s.id === data.id
          ? { ...s, message_count: data.message_count, last_message: data.last_message } : s));
        setLoadingMsgs(false);
      } catch { if (cancelled) return; setLoadingMsgs(false); }
    };
    poll();
    const interval = setInterval(poll, 3000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [active]);

  // Poll orchestration state
  useEffect(() => {
    if (!active) { setOrchProgress(null); setOrchState('idle'); return; }
    let cancelled = false;
    const poll = async () => {
      try {
        const [progRes, stateRes] = await Promise.all([
          api.get('/conversations/' + active + '/orchestration-progress/'),
          api.get('/conversations/' + active + '/orch-state/'),
        ]);
        if (cancelled) return;
        setOrchProgress(progRes.active ? progRes : null);
        setOrchState(stateRes.state || 'idle');
      } catch { setOrchProgress(null); setOrchState('idle'); }
    };
    poll();
    const interval = setInterval(poll, 3000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [active]);

  // Restore scroll position
  useEffect(() => {
    if (!active || !chatContainer.current) return;
    const el = chatContainer.current;
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const saved = scrollPositions.current[active];
        if (saved !== undefined) {
          el.scrollTop = saved;
          userScrolledUp.current = true;
          setShowScrollBtn(true);
        } else {
          messagesEnd.current?.scrollIntoView({ behavior: 'instant' });
          userScrolledUp.current = false;
        }
      });
    });
  }, [active]);

  // Switch animation
  useEffect(() => {
    if (!active) return;
    setAnimSwitch(true);
    const timer = setTimeout(() => setAnimSwitch(false), 360);
    return () => clearTimeout(timer);
  }, [active]);

  // Poll output panel content
  useEffect(() => {
    if (!active) { setOutputContent(''); return; }
    let cancelled = false;
    const poll = async () => {
      try {
        const data = await api.get('/conversations/' + active + '/get-output/');
        if (cancelled) return;
        if (data.content !== undefined) setOutputContent(data.content);
      } catch {}
    };
    poll();
    const interval = setInterval(poll, 5000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [active]);

  const isNearBottom = () => {
    const el = chatContainer.current;
    if (!el) return true;
    return el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  };

  useEffect(() => {
    if (messages.length === 0) return;
    const isNewMsg = messages.length > prevMsgCount.current;
    prevMsgCount.current = messages.length;
    if (isNewMsg && !userScrolledUp.current) {
      requestAnimationFrame(() => {
        messagesEnd.current?.scrollIntoView({ behavior: 'smooth' });
      });
    }
  }, [messages]);

  const handleSessionClick = (sessionId) => {
    if (active && chatContainer.current) {
      scrollPositions.current[active] = chatContainer.current.scrollTop;
    }
    userScrolledUp.current = false;
    setActive(sessionId);
    setActiveSessionId(sessionId);
  };

  const handleScroll = () => {
    const nearBottom = isNearBottom();
    setShowScrollBtn(!nearBottom);
    if (!nearBottom) userScrolledUp.current = true;
    if (active && chatContainer.current) {
      scrollPositions.current[active] = chatContainer.current.scrollTop;
    }
  };

  const sendMessage = async () => {
    if (!input.trim() || !active || sending) return;
    setSending(true);
    let text = input;
    setInput('');

    const pendingFiles = [...attachedFiles];
    if (pendingFiles.length > 0) {
      const fileLinks = pendingFiles
        .filter(f => f.file)
        .map(f => `[📎 ${f.original_name}](${f.file.startsWith('http') ? f.file : window.location.origin + f.file})`).join('\n');
      if (fileLinks) text += '\n\n---\n📁 **已上传文件：**\n' + fileLinks;
      setAttachedFiles([]);
    }

    try {
      const msg = await api.post('/messages/', { conversation: active, role: 'user', content: text });
      if (pendingFiles.length > 0) {
        setMsgFiles(prev => ({ ...prev, [msg.id]: pendingFiles }));
      }
      const data = await api.get('/conversations/' + active + '/');
      setMessages(data.messages || []);
      setSessions(prev => prev.map(s => s.id === data.id
        ? { ...s, message_count: data.message_count, last_message: data.last_message } : s));
      addToast('消息已发送', 'success');
    } catch (e) { addToast('发送失败', 'error'); }
    finally { setSending(false); }
  };

  const handlePause = async () => {
    try { await api.post('/conversations/' + active + '/pause/'); addToast('已暂停'); } catch {}
  };
  const handleStop = async () => {
    if (!confirm('确定停止编排？')) return;
    try { await api.post('/conversations/' + active + '/stop/'); addToast('已停止'); } catch {}
  };

  const handleDeleteSession = async (sessionId, e) => {
    e.stopPropagation();
    const s = sessions.find(x => x.id === sessionId);
    if (!confirm(`确定关闭会话「${s?.agent_name || s?.title || '未命名'}」？\n所有消息将被删除。`)) return;
    try {
      await api.delete('/conversations/' + sessionId + '/');
      setSessions(prev => prev.filter(x => x.id !== sessionId));
      if (active === sessionId) { setActive(null); setActiveSessionId(null); }
      addToast('会话已关闭', 'success');
    } catch (e) { addToast('关闭失败: ' + e.message, 'error'); }
  };

  const copyText = (msg) => {
    const text = msg.content || '';
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(() => {
        setCopiedId(msg.id);
        setTimeout(() => setCopiedId(null), 1500);
      }).catch(() => {});
    } else {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand('copy'); } catch {}
      document.body.removeChild(ta);
      setCopiedId(msg.id);
      setTimeout(() => setCopiedId(null), 1500);
    }
  };

  const handleOutputDownload = () => {
    const filename = (activeSession?.agent_name || 'output') + '-output.md';
    const blob = new Blob([outputContent], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleFileDrop = async (e) => {
    e.preventDefault();
    setDragOver(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length === 0) return;
    await uploadFiles(files);
  };

  const handleFileSelect = async (e) => {
    const files = Array.from(e.target.files);
    if (files.length === 0) return;
    await uploadFiles(files);
    e.target.value = '';
  };

  const uploadFiles = async (files) => {
    if (!active) { addToast('请先选择会话', 'error'); return; }
    setUploading(true);
    const uploaded = [];
    for (const file of files) {
      try {
        const fd = new FormData();
        fd.append('file', file);
        fd.append('original_name', file.name);
        fd.append('conversation', String(active));
        fd.append('agent_name', activeSession?.agent_name || '');
        const result = await api.upload('/files/', fd);
        uploaded.push(result);
      } catch (e) { addToast(`上传失败: ${file.name}`, 'error'); }
    }
    if (uploaded.length > 0) {
      setUploadedFiles(prev => [...prev, ...uploaded]);
      setAttachedFiles(prev => [...prev, ...uploaded]);
      addToast(`已上传 ${uploaded.length} 个文件`, 'success');
    }
    setUploading(false);
  };

  // Fetch uploaded files when conversation changes (shared by agent)
  useEffect(() => {
    if (!active || !activeSession?.agent_name) { setUploadedFiles([]); return; }
    (async () => {
      try {
        const data = await api.get('/files/', { agent: activeSession.agent_name, page_size: 50 });
        setUploadedFiles(data.results || []);
      } catch {}
    })();
  }, [active, activeSession?.agent_name]);

  const renderContent = (content = '') => {
    if (!content) return null;
    const parts = content.split(/(!\[[^\]]*\]\([^)]+\))/g);
    return parts.map((part, i) => {
      const imgMatch = part.match(/^!\[([^\]]*)\]\(([^)]+)\)$/);
      if (imgMatch && imgMatch[2].startsWith('data:image/')) {
        return <img key={i} src={imgMatch[2]} alt={imgMatch[1]} style={{maxWidth:280,borderRadius:8,margin:'4px 0'}} />;
      }
      if (part) return <span key={i} style={{whiteSpace:'pre-wrap',wordBreak:'break-word'}}>{part}</span>;
      return null;
    });
  };

  const isOrchNode = (msg) => {
    if (msg.role !== 'system' || !msg.metadata) return false;
    try { return !!JSON.parse(msg.metadata).orch; } catch { return false; }
  };
  const getOrchMeta = (msg) => {
    try { return JSON.parse(msg.metadata || '{}'); } catch { return {}; }
  };
  const orchColors = {
    done: { bg:'rgba(29,158,117,0.12)', text:'#1D9E75', border:'rgba(29,158,117,0.3)' },
    error: { bg:'rgba(226,75,74,0.12)', text:'#E24B4A', border:'rgba(226,75,74,0.3)' },
    start: { bg:'rgba(255,255,255,0.05)', text:'#8f959e', border:'rgba(0,0,0,0.06)' },
    summarizing: { bg:'rgba(186,117,23,0.12)', text:'#BA7517', border:'rgba(186,117,23,0.3)' },
  };

  const buildMessageGroups = () => {
    const visible = messages.filter(m => !isOrchNode(m));
    if (visible.length === 0) return [];
    const groups = [];
    let currentGroup = { role: visible[0].role, msgs: [visible[0]], time: visible[0].created_at };
    for (let i = 1; i < visible.length; i++) {
      const prev = visible[i - 1];
      const curr = visible[i];
      const gap = new Date(curr.created_at) - new Date(prev.created_at);
      if (curr.role !== currentGroup.role || gap > MSG_GAP_MINUTES * 60 * 1000) {
        groups.push(currentGroup);
        currentGroup = { role: curr.role, msgs: [curr], time: curr.created_at };
      } else {
        currentGroup.msgs.push(curr);
      }
    }
    groups.push(currentGroup);
    const result = [];
    for (let i = 0; i < groups.length; i++) {
      if (i > 0) {
        const prevTime = groups[i - 1].msgs[groups[i - 1].msgs.length - 1].created_at;
        const currTime = groups[i].msgs[0].created_at;
        const gap = new Date(currTime) - new Date(prevTime);
        if (gap > MSG_GAP_MINUTES * 60 * 1000) {
          result.push({ type: 'time', time: currTime, key: `time-${groups[i].msgs[0].id}` });
        }
      } else {
        result.push({ type: 'time', time: groups[0].msgs[0].created_at, key: `time-${groups[0].msgs[0].id}` });
      }
      result.push({ type: 'group', ...groups[i], key: `group-${groups[i].msgs[0].id}` });
    }
    return result;
  };

  const msgGroups = buildMessageGroups();

  return (
    <div className="session-view-container">
      <div className="session-layout">
        {/* Session list — resizable */}
        <div className="session-list-panel light" style={{ width: listResize.size, minWidth: listResize.size, flexShrink: 0 }}>
          <div style={{padding:'10px 12px',borderBottom:'1px solid rgba(255,255,255,0.06)',flexShrink:0}}>
            <button className="btn btn-primary" style={{width:'100%'}} onClick={() => openModal('newSession')}>+ 新建会话</button>
          </div>
          {sessions.length === 0 ? (
            <div style={{padding:20,textAlign:'center',color:'var(--text-muted)'}}>暂无会话</div>
          ) : sessions.map(s => {
            const isProcessing = s.last_message && s.last_message.role !== 'agent';
            const isActive = active === s.id;
            return (
            <div key={s.id}
              className={`session-item${isActive?' active':''}`}
              onClick={() => handleSessionClick(s.id)}>
              <button
                className="session-close-btn"
                onClick={(e) => handleDeleteSession(s.id, e)}
                title="关闭会话"
              >✕</button>
              <div className="session-item-header">
                <div style={{display:'flex',alignItems:'center',gap:6}}>
                  {isProcessing && <span style={{
                    width:6,height:6,borderRadius:'50%',background:'#3370ff',
                    flexShrink:0,animation:'pulse 1.5s ease-in-out infinite'
                  }} />}
                  <span className="session-name">{s.agent_name || s.title}</span>
                </div>
              </div>
              <div style={{fontSize:10,color:'var(--text-muted)',marginBottom:4}}>
                {s.created_at ? new Date(s.created_at).toLocaleString() : ''}
                {s.feishu_chat_id ? ' · 💬飞书' : ''}
                {isProcessing ? ' · ⏳ 处理中' : ''}
              </div>
              <div className="session-preview">
                {s.last_message?.content?.slice(0, 60) || `${s.message_count || 0} 条消息`}
              </div>
            </div>
          )})}
        </div>

        {/* Resize handle: list ↔ detail */}
        <div className="resize-handle resize-handle-x" onMouseDown={listResize.onMouseDown}>
          <div className="resize-handle-bar" />
        </div>

        {/* Detail panel */}
        <div className="session-detail-panel light" style={{ flex: 1, minWidth: 0 }}>
          {activeSession ? (
            <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
              {/* Header */}
              <div className="session-detail-header">
                <div>
                  <span className="session-detail-agent">{activeSession.agent_name || '未指定'}</span>
                  {agentRole && <span className="session-detail-role">{agentRole}</span>}
                  <span className="session-detail-meta">
                    · {activeSession.message_count || 0} 条消息
                    {activeSession.feishu_chat_id ? ' · 💬飞书' : ''}
                  </span>
                </div>
                <div style={{display:'flex',gap:6,alignItems:'center'}}>
                  {/* Output toggle */}
                  <button
                    className={`btn btn-ghost${showOutput ? ' active' : ''}`}
                    style={{fontSize:11,padding:'4px 10px'}}
                    onClick={() => setShowOutput(prev => !prev)}
                    title="输出面板"
                  >
                    {showOutput ? '✕ 关闭输出' : '📄 输出'}
                  </button>
                  <button
                    className="btn btn-ghost"
                    style={{fontSize:11,padding:'4px 10px',color:'#E24B4A',borderColor:'rgba(226,75,74,0.4)'}}
                    onClick={(e) => handleDeleteSession(activeSession.id, e)}
                    title="关闭会话"
                  >✕ 关闭</button>
                  {orchState === 'running' ? (
                    <>
                      <button className="btn btn-ghost" style={{fontSize:11,padding:'4px 10px',color:'#BA7517',borderColor:'rgba(186,117,23,0.4)'}} onClick={handlePause}>⏸ 暂停</button>
                      <button className="btn btn-ghost" style={{fontSize:11,padding:'4px 10px',color:'#E24B4A',borderColor:'rgba(226,75,74,0.4)'}} onClick={handleStop}>⏹ 完成</button>
                    </>
                  ) : orchState === 'paused' ? (
                    <span style={{fontSize:11,color:'#BA7517'}}>已暂停</span>
                  ) : null}
                </div>
              </div>

              {/* Orch progress */}
              {orchProgress && (
                <div style={{padding:'8px 16px',borderBottom:'1px solid #dee2eb',background:'#f5f7fc'}}>
                  <div style={{display:'flex',justifyContent:'space-between',fontSize:11,marginBottom:4}}>
                    <span style={{color:'#646a73'}}>⚙ {orchProgress.done}/{orchProgress.total} {orchProgress.current_step || ''}</span>
                    <span style={{color:'#8f959e',fontSize:10}}>{orchProgress.done === orchProgress.total ? '✅ 完成' : '🔄 执行中'}</span>
                  </div>
                  <div style={{height:3,borderRadius:2,background:'#dee2eb',overflow:'hidden'}}>
                    <div style={{height:'100%',borderRadius:2,background:'#3370ff',transition:'width 0.7s',width:`${(orchProgress.done/orchProgress.total)*100}%`}} />
                  </div>
                </div>
              )}

              {/* Chat + Output split */}
              <div style={{ flex: 1, display: 'flex', minHeight: 0, position: 'relative' }}>
                {/* Messages panel */}
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
                  <div className={`session-messages${animSwitch ? ' switch-enter' : ''}`} ref={chatContainer}
                    onScroll={handleScroll}>
                    {loadingMsgs && messages.length === 0 ? (
                      <div className="session-loading">加载中...</div>
                    ) : (
                      <>
                        {messages.filter(m => isOrchNode(m)).map(msg => {
                          const meta = getOrchMeta(msg);
                          const c = orchColors[meta.orch] || orchColors.start;
                          return (
                            <div key={msg.id} style={{textAlign:'center',margin:'8px 0'}}>
                              <span style={{fontSize:10,padding:'3px 12px',borderRadius:10,background:c.bg,border:`1px solid ${c.border}`,color:c.text}}>
                                {msg.content}
                              </span>
                            </div>
                          );
                        })}
                        {msgGroups.map(item => {
                          if (item.type === 'time') {
                            return (
                              <div key={item.key} className="msg-time-sep">
                                <span>{fmtTime(item.time)}</span>
                              </div>
                            );
                          }
                          const group = item;
                          const firstMsg = group.msgs[0];
                          const isUser = group.role === 'user';
                          return (
                            <div key={group.key} className={`msg-group ${isUser ? 'msg-group-user' : 'msg-group-agent'}`}>
                              <div className="msg-sender">
                                {isUser ? '👤 用户' : '🤖 Agent'}
                              </div>
                              {group.msgs.map((msg, idx) => (
                                <div key={msg.id}
                                  className="msg-row"
                                  onMouseEnter={() => setHoveredMsgId(msg.id)}
                                  onMouseLeave={() => setHoveredMsgId(null)}
                                >
                                  <div className={`msg-bubble ${msg.role}${idx === 0 ? ' msg-bubble-first' : ''}`}>
                                    <button
                                      onClick={(e) => { e.stopPropagation(); copyText(msg); }}
                                      className={`msg-copy-btn${hoveredMsgId === msg.id || copiedId === msg.id ? ' visible' : ''}`}
                                      title="复制"
                                    >
                                      {copiedId === msg.id ? (
                                        <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M11.5 3.5L5.5 10L2.5 7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
                                      ) : (
                                        <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><rect x="4" y="4" width="9" height="9" rx="1" stroke="currentColor" strokeWidth="1.2"/><path d="M10 3V2.5a.5.5 0 0 0-.5-.5h-7a.5.5 0 0 0-.5.5v7a.5.5 0 0 0 .5.5H3" stroke="currentColor" strokeWidth="1.2"/></svg>
                                      )}
                                    </button>
                                    {msg.role === 'user' && msg.metadata ? (
                                      (() => { try { const m = JSON.parse(msg.metadata); if (m.html) return <div dangerouslySetInnerHTML={{ __html: m.html }} />; } catch {} return <MessageRenderer content={msg.content} />; })()
                                    ) : <MessageRenderer content={msg.content} />}

                                    {/* File attachments */}
                                    {msgFiles[msg.id] && msgFiles[msg.id].length > 0 && (
                                      <div style={{marginTop:8,display:'flex',flexDirection:'column',gap:4}}>
                                        {msgFiles[msg.id].map(f => (
                                          <div key={f.id} className="msg-file-badge"
                                            style={{fontSize:11,color:'#3370ff',display:'flex',alignItems:'center',gap:4,
                                              background:'rgba(51,112,255,0.06)',padding:'4px 8px',borderRadius:6,position:'relative'}}>
                                            <a href={f.file} target="_blank" rel="noopener noreferrer"
                                              style={{color:'inherit',textDecoration:'none',display:'flex',alignItems:'center',gap:4,flex:1}}>
                                              📎 {f.original_name} <span style={{color:'#8f959e'}}>{(f.size/1024).toFixed(0)}KB</span>
                                            </a>
                                            <button
                                              className="msg-file-delete"
                                              onClick={async (e) => {
                                                e.preventDefault();
                                                try { await api.delete('/files/' + f.id + '/'); } catch {}
                                                setMsgFiles(prev => {
                                                  const updated = { ...prev };
                                                  updated[msg.id] = updated[msg.id].filter(x => x.id !== f.id);
                                                  if (updated[msg.id].length === 0) delete updated[msg.id];
                                                  return updated;
                                                });
                                              }}
                                              title="取消上传"
                                            >×</button>
                                          </div>
                                        ))}
                                      </div>
                                    )}
                                  </div>
                                </div>
                              ))}
                            </div>
                          );
                        })}
                      </>
                    )}
                    <div ref={messagesEnd} />
                    {showScrollBtn && (
                      <button onClick={() => {
                        userScrolledUp.current = false;
                        setShowScrollBtn(false);
                        messagesEnd.current?.scrollIntoView({ behavior: 'smooth' });
                      }} className="scroll-bottom-btn">
                        <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
                      </button>
                    )}
                  </div>

                  {/* Drag zone */}
                  <div
                    className={`drag-zone${dragOver ? ' active' : ''}`}
                    onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                    onDragLeave={() => setDragOver(false)}
                    onDrop={handleFileDrop}
                    style={{display: dragOver ? 'block' : 'none'}}
                  >
                    <div>📁 拖放文件到此处上传</div>
                  </div>

                  {/* Uploaded files history — click to re-attach */}
                  {uploadedFiles.length > 0 && (
                    <div className="pending-files">
                      {uploadedFiles.map(f => (
                        <span key={f.id} className="pending-file-chip"
                          onClick={() => {
                            setAttachedFiles(prev => prev.some(x => x.id === f.id) ? prev : [...prev, f]);
                          }}
                          title="点击附加到本次消息"
                        >
                          📎 {f.original_name?.slice(0,28)}{(f.size > 1024 ? ` ${(f.size/1024).toFixed(0)}KB` : '')}
                          <button
                            className="pending-file-remove"
                            onClick={async (e) => {
                              e.stopPropagation();
                              try { await api.delete('/files/' + f.id + '/'); } catch {}
                              setUploadedFiles(prev => prev.filter(x => x.id !== f.id));
                              setAttachedFiles(prev => prev.filter(x => x.id !== f.id));
                            }}
                            title="删除文件"
                          >×</button>
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Input */}
                  <div className="session-input-area">
                    <input type="file" id="file-upload-input" multiple style={{display:'none'}} onChange={handleFileSelect} />
                    <label htmlFor="file-upload-input" className={`attach-btn${uploading ? ' uploading' : ''}`} title="上传文件">
                      {uploading ? '⏳' : '📎'}
                    </label>
                    {/* Attached files inside input */}
                    {attachedFiles.length > 0 && (
                      <div className="input-files">
                        {attachedFiles.map(f => (
                          <span key={f.id} className="input-file-tag">
                            📎 {f.original_name?.slice(0,22)}
                            <button className="input-file-untag"
                              onClick={() => {
                                setUploadedFiles(prev => [...prev, f]);
                                setAttachedFiles(prev => prev.filter(x => x.id !== f.id));
                              }}
                              title="移除附件">×</button>
                          </span>
                        ))}
                      </div>
                    )}
                    <textarea
                      placeholder="输入消息..."
                      value={input}
                      onChange={e => setInput(e.target.value)}
                      onKeyDown={e => { if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMessage();} }}
                      rows={1}
                    />
                    <button
                      className={`send-btn${input.trim() ? ' active' : ''}`}
                      onClick={sendMessage}
                      disabled={sending || !input.trim()}
                      title="发送 (Enter)"
                    >
                      {sending ? (
                        <span className="sending-dot" />
                      ) : (
                        <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                          <path d="M2.01 16L17 9 2.01 2 2 7.44l10.72 1.56L2 10.56 2.01 16z" fill="currentColor"/>
                        </svg>
                      )}
                    </button>
                  </div>
                </div>

                {/* Output panel — toggleable, fixed width */}
                {showOutput && (
                  <div className={`output-panel-inline${outputFullscreen ? ' output-fullscreen' : ''}`}
                    style={!outputFullscreen ? { width: 380, minWidth: 380, flexShrink: 0 } : {}}>
                      <div className="output-panel-inline-header">
                        <span style={{fontSize:12,fontWeight:500,color:'#1f2329'}}>输出面板</span>
                        <div style={{display:'flex',gap:4}}>
                          <button className="output-panel-btn" title="复制全部"
                            onClick={() => {
                              navigator.clipboard.writeText(outputContent).then(() => {
                                setOutputCopied(true); setTimeout(() => setOutputCopied(false), 1500);
                              });
                            }}
                          >{outputCopied ? '✓' : '📋'}</button>
                          <button className="output-panel-btn" title="下载 .md"
                            onClick={handleOutputDownload} disabled={!outputContent}
                          >⬇</button>
                          <button className="output-panel-btn" title={outputFullscreen ? '退出全屏' : '全屏'}
                            onClick={() => setOutputFullscreen(prev => !prev)}
                          >{outputFullscreen ? '✕' : '⛶'}</button>
                        </div>
                      </div>
                      <div className="output-panel-preview">
                        {outputContent ? (
                          <MessageRenderer content={outputContent} />
                        ) : (
                          <div className="output-empty-hint">
                            <div style={{textAlign:'center'}}>
                              <div style={{fontSize:24,marginBottom:8}}>📄</div>
                              <div style={{fontSize:13,color:'#8f959e'}}>Agent 输出文档将在此显示</div>
                              <div style={{fontSize:11,color:'#c4c9cc',marginTop:4}}>AI 在回复中使用 【OUTPUT_PANEL】标记即可推送</div>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ) : (
            <div className="session-empty light">
              <svg viewBox="0 0 64 64" fill="none" width="48" height="48" style={{color:'#8f959e'}}><path d="M8 12a4 4 0 014-4h40a4 4 0 014 4v32a4 4 0 01-4 4H14l-8 8V12z" stroke="currentColor" strokeWidth="1.5"/><path d="M20 24h24M20 32h16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
              <p style={{fontSize:13,color:'#8f959e'}}>选择左侧会话以查看详情</p>
              <p style={{fontSize:11,color:'#8f959e'}}>创建新会话开始对话</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
