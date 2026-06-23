import React, { useState, useEffect, useRef } from 'react';
import { api } from '../../api';

export default function Sessions({ sessions, setSessions, agents, addToast, openModal }) {
  const [active, setActive] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [loadingMsgs, setLoadingMsgs] = useState(false);
  const [orchProgress, setOrchProgress] = useState(null);
  const [orchState, setOrchState] = useState('idle');
  const messagesEnd = useRef(null);

  const activeSession = sessions.find(s => s.id === active);

  // Poll messages for active conversation
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

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: 'instant' });
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || !active || sending) return;
    setSending(true);
    const text = input;
    setInput('');
    try {
      await api.post('/messages/', { conversation: active, role: 'user', content: text });
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
    start: { bg:'rgba(255,255,255,0.05)', text:'var(--text-muted)', border:'var(--border-subtle)' },
    summarizing: { bg:'rgba(186,117,23,0.12)', text:'#BA7517', border:'rgba(186,117,23,0.3)' },
  };

  return (
    <>
      <div className="view-header">
        <h1 className="view-title">会话中心</h1>
        <div className="view-actions">
          <button className="btn btn-primary" onClick={() => openModal('newSession')}>新建会话</button>
        </div>
      </div>

      <div className="session-layout">
        {/* Conversation list */}
        <div className="session-list-panel light">
          {sessions.length === 0 ? (
            <div style={{padding:20,textAlign:'center',color:'var(--text-muted)'}}>暂无会话</div>
          ) : sessions.map(s => (
            <div key={s.id} className={`session-item${active===s.id?' active':''}`} onClick={() => setActive(s.id)}>
              <div className="session-item-header">
                <span className="session-name">{s.title}</span>
                {s.agent_name && <span className="status-badge online" style={{fontSize:9}}>{s.agent_name}</span>}
              </div>
              <div style={{fontSize:10,color:'var(--text-muted)',marginBottom:4}}>
                {s.created_at ? new Date(s.created_at).toLocaleString() : ''}
                {s.feishu_chat_id ? ' · 💬飞书' : ''}
              </div>
              <div className="session-preview">
                {s.last_message?.content?.slice(0, 60) || `${s.message_count || 0} 条消息`}
              </div>
            </div>
          ))}
        </div>

        {/* Detail panel */}
        <div className="session-detail-panel light">
          {activeSession ? (
            <>
              {/* Header */}
              <div style={{padding:'14px 16px',borderBottom:'1px solid #dee2eb',display:'flex',alignItems:'center',justifyContent:'space-between',flexShrink:0,background:'#fff'}}>
                <div>
                  <div style={{fontSize:14,fontWeight:500,color:'#1f2329'}}>{activeSession.title}</div>
                  <div style={{fontSize:11,color:'#8f959e'}}>
                    {activeSession.agent_name || '未指定'} · {activeSession.message_count || 0} 条消息
                    {activeSession.feishu_chat_id ? ' · 💬飞书' : ''}
                  </div>
                </div>
                <div style={{display:'flex',gap:6,alignItems:'center'}}>
                  {orchState === 'running' ? (
                    <>
                      <button className="btn btn-ghost" style={{fontSize:11,padding:'4px 10px',color:'var(--amber)',borderColor:'rgba(186,117,23,0.4)'}} onClick={handlePause}>⏸ 暂停</button>
                      <button className="btn btn-ghost" style={{fontSize:11,padding:'4px 10px',color:'var(--red)',borderColor:'rgba(226,75,74,0.4)'}} onClick={handleStop}>⏹ 完成</button>
                    </>
                  ) : orchState === 'paused' ? (
                    <span style={{fontSize:11,color:'var(--amber)'}}>已暂停</span>
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
                    <div style={{height:'100%',borderRadius:2,background:'var(--cyan)',transition:'width 0.7s',width:`${(orchProgress.done/orchProgress.total)*100}%`}} />
                  </div>
                </div>
              )}

              {/* Messages */}
              <div className="session-messages">
                {loadingMsgs && messages.length === 0 ? (
                  <div style={{textAlign:'center',color:'var(--text-muted)',padding:20}}>加载中...</div>
                ) : messages.map(msg => {
                  if (isOrchNode(msg)) {
                    const meta = getOrchMeta(msg);
                    const c = orchColors[meta.orch] || orchColors.start;
                    return (
                      <div key={msg.id} style={{textAlign:'center'}}>
                        <span style={{fontSize:10,padding:'2px 10px',borderRadius:10,background:c.bg,border:`1px solid ${c.border}`,color:c.text}}>{msg.content}</span>
                      </div>
                    );
                  }
                  return (
                    <div key={msg.id} style={{display:'flex',flexDirection:'column',alignItems:msg.role==='user'?'flex-end':'flex-start'}}>
                      <div className="msg-meta">
                        {msg.role === 'user' ? '👤 用户' : '🤖 Agent'} · {msg.created_at ? new Date(msg.created_at).toLocaleTimeString() : ''}
                      </div>
                      <div className={`msg-bubble ${msg.role}`}>
                        {msg.role === 'user' && msg.metadata ? (
                          (() => { try { const m = JSON.parse(msg.metadata); if (m.html) return <div dangerouslySetInnerHTML={{ __html: m.html }} />; } catch {} return renderContent(msg.content); })()
                        ) : renderContent(msg.content)}
                      </div>
                    </div>
                  );
                })}
                <div ref={messagesEnd} />
              </div>

              {/* Input */}
              <div className="session-input-area">
                <textarea
                  placeholder="输入消息... (Enter 发送)"
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={e => { if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMessage();} }}
                />
                <button className="btn btn-primary" onClick={sendMessage} disabled={sending}>
                  {sending ? '...' : '发送'}
                </button>
              </div>
            </>
          ) : (
            <div className="session-empty light">
              <svg viewBox="0 0 64 64" fill="none" width="48" height="48" style={{color:'#8f959e'}}><path d="M8 12a4 4 0 014-4h40a4 4 0 014 4v32a4 4 0 01-4 4H14l-8 8V12z" stroke="currentColor" strokeWidth="1.5"/><path d="M20 24h24M20 32h16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
              <p style={{fontSize:13,color:'#8f959e'}}>选择左侧会话以查看详情</p>
              <p style={{fontSize:11,color:'#8f959e'}}>创建新会话开始对话</p>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
