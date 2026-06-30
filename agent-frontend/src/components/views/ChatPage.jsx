import React, { useState, useEffect, useRef } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { api } from '../../api';

function fmt(t) { if (!t) return ''; try { return new Date(t).toLocaleTimeString(); } catch { return ''; } }

/* ── Feishu-style light blue-gray theme ── */
const L = {
  bg: '#eef1f6',
  panel: '#ffffff',
  border: '#dee2eb',
  text: '#1f2329',
  textMuted: '#8f959e',
  textSecondary: '#646a73',
  bubbleAI: '#f2f4f7',
  bubbleAIborder: '#e4e8ee',
  bubbleUser: '#3370ff',
  bubbleUserBorder: '#2860d6',
  bubbleUserText: '#ffffff',
  headerBg: '#ffffff',
  inputBg: '#f2f4f7',
  inputFocus: '#3370ff',
};

const orchColors = {
  done:    { bg:'rgba(29,158,117,0.1)',  border:'rgba(29,158,117,0.3)',  text:'#1D9E75' },
  error:   { bg:'rgba(226,75,74,0.1)',   border:'rgba(226,75,74,0.3)',   text:'#E24B4A' },
  received:{ bg:'rgba(55,138,221,0.1)',   border:'rgba(55,138,221,0.3)',   text:'#378ADD' },
  start:   { bg:'rgba(0,0,0,0.04)',       border:'rgba(0,0,0,0.08)',       text:'#65676b' },
  summarizing:{ bg:'rgba(186,117,23,0.1)',border:'rgba(186,117,23,0.3)',  text:'#BA7517' },
  stopped: { bg:'rgba(226,75,74,0.1)',    border:'rgba(226,75,74,0.4)',   text:'#E24B4A' },
};

// Redirect to unified Sessions page
export default function ChatPage() {
  return <Navigate to="/sessions" replace />;
}

/* ─── legacy ChatPage preserved below for reference ─── */
const _ChatPage = () => {
  const [conversations, setConversations] = useState([]);
  const [agents, setAgents] = useState([]);
  const [activeConv, setActiveConv] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [input, setInput] = useState('');
  const [showNew, setShowNew] = useState(false);
  const [newAgentId, setNewAgentId] = useState('');
  const [newTitle, setNewTitle] = useState('');
  const [showSidebar, setShowSidebar] = useState(true);
  const [copiedId, setCopiedId] = useState(null);
  const [showScrollBtn, setShowScrollBtn] = useState(false);
  const messagesEnd = useRef(null);
  const chatContainer = useRef(null);
  const scrollPositions = useRef({});

  useEffect(() => {
    (async () => {
      try {
        const [cRes, aRes] = await Promise.all([
          api.get('/conversations/', { page_size: 200 }),
          api.get('/agents/', { page_size: 50 }),
        ]);
        setConversations(cRes.results || cRes || []);
        setAgents(aRes.results || aRes || []);
      } catch (e) { console.error(e); }
      finally { setLoading(false); }
    })();
  }, []);

  const isNearBottom = () => {
    const el = chatContainer.current;
    if (!el) return true;
    return el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  };
  const getDistanceFromBottom = () => {
    const el = chatContainer.current;
    if (!el) return 0;
    return el.scrollHeight - el.scrollTop - el.clientHeight;
  };

  const saveScrollPosition = (convId) => {
    if (!convId || !chatContainer.current) return;
    scrollPositions.current[convId] = {
      top: chatContainer.current.scrollTop,
      distFromBottom: getDistanceFromBottom(),
      wasAtBottom: isNearBottom(),
    };
  };

  const restoreScrollPosition = (convId) => {
    const el = chatContainer.current;
    if (!el) return;
    const saved = scrollPositions.current[convId];
    if (!saved) {
      messagesEnd.current?.scrollIntoView({ behavior: 'instant' });
      return;
    }
    if (saved.wasAtBottom) {
      messagesEnd.current?.scrollIntoView({ behavior: 'instant' });
    } else {
      el.scrollTop = Math.max(0, el.scrollHeight - saved.distFromBottom);
    }
  };

  // SSE 实时事件流
  const esRef = useRef(null);
  const switchingRef = useRef(false);
  const userScrolledUp = useRef(false);

  useEffect(() => {
    if (!activeConv) return;
    const convId = activeConv; // ⭐ 闭包捕获，cleanup 时不变
    let cancelled = false;
    switchingRef.current = true;

    (async () => {
      try {
        const data = await api.get('/conversations/' + convId + '/');
        if (!cancelled) setMessages(data.messages || []);
      } catch {}
    })();

    const es = new EventSource('/api/events/?conversation_id=' + convId);
    esRef.current = es;

    es.addEventListener('message-update', (e) => {
      try {
        const evt = JSON.parse(e.data);
        if (evt.conversation_id !== convId) return;
        api.get('/conversations/' + convId + '/').then(data => {
          if (!cancelled && data.messages) {
            setMessages(prev => data.messages.length !== prev.length ? data.messages : prev);
          }
        }).catch(() => {});
      } catch {}
    });

    es.onerror = () => {};

    return () => {
      // ⭐ 用闭包 convId 保存，不受 activeConv 新值影响
      saveScrollPosition(convId);
      cancelled = true;
      es.close();
      esRef.current = null;
    };
  }, [activeConv]);

  // 消息加载后恢复滚动位置（双层 RAF 等布局稳定）
  const prevMsgLen = useRef(0);
  const rafRef = useRef(null);
  useEffect(() => {
    if (messages.length === 0) return;
    if (messages.length !== prevMsgLen.current || switchingRef.current) {
      prevMsgLen.current = messages.length;
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      rafRef.current = requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          restoreScrollPosition(activeConv);
          switchingRef.current = false;
        });
      });
    }
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [messages, activeConv]);

  // 首次加载自动选第一个对话
  useEffect(() => {
    if (!loading && conversations.length > 0 && !activeConv) {
      setActiveConv(conversations[0].id);
    }
  }, [loading, conversations, activeConv]);

  // 消息更新时智能滚动（仅当用户未主动上滚 + 非切换中）
  useEffect(() => {
    if (messages.length > 0 && !switchingRef.current && !userScrolledUp.current) {
      messagesEnd.current?.scrollIntoView({ behavior: 'instant' });
    }
    setShowScrollBtn(userScrolledUp.current);
  }, [messages]);

  const handleConvClick = (convId) => {
    if (activeConv && activeConv !== convId) {
      saveScrollPosition(activeConv); // 同步保存（第一层保险）
    }
    setActiveConv(convId);
  };

  const createConv = async () => {
    if (!newAgentId) return;
    try {
      const data = await api.post('/conversations/', { title: newTitle || '新对话', agent: parseInt(newAgentId) });
      setConversations(prev => [data, ...prev]);
      setActiveConv(data.id);
      setShowNew(false);
      setNewAgentId('');
      setNewTitle('');
    } catch (e) { console.error(e); }
  };

  const sendMsg = async (e) => {
    e?.preventDefault();
    if (!input.trim() || !activeConv || sending) return;
    setSending(true);
    const text = input;
    setInput('');
    try {
      await api.post('/messages/', { conversation: activeConv, role: 'user', content: text });
      userScrolledUp.current = false;
      const data = await api.get('/conversations/' + activeConv + '/');
      setMessages(data.messages || []);
      // 发送后强制滚到底部
      setTimeout(() => messagesEnd.current?.scrollIntoView({ behavior: 'smooth' }), 100);
    } catch (e) { console.error(e); }
    finally { setSending(false); }
  };

  const copyMsg = async (msg) => {
    let text = msg.content || '';
    if (msg.metadata) {
      try { const m = JSON.parse(msg.metadata); if (m.html) { const tmp = document.createElement('div'); tmp.innerHTML = m.html; text = tmp.innerText || ''; } } catch {}
    }
    // 优先 Clipboard API，HTTP 环境用 execCommand 兜底
    if (navigator.clipboard && window.isSecureContext) {
      try { await navigator.clipboard.writeText(text); } catch {}
    } else {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand('copy'); } catch {}
      document.body.removeChild(ta);
    }
    setCopiedId(msg.id);
    setTimeout(() => setCopiedId(null), 1500);
  };

  const renderContent = (msg) => {
    if (msg.role === 'user' && msg.metadata) {
      try {
        const meta = JSON.parse(msg.metadata);
        if (meta.html) return <div dangerouslySetInnerHTML={{ __html: meta.html }} />;
      } catch {}
    }
    const content = msg.content || '';
    const parts = content.split(/(!\[[^\]]*\]\([^)]+\))/g);
    return parts.map((part, i) => {
      const m = part.match(/^!\[([^\]]*)\]\(([^)]+)\)$/);
      if (m && m[2].startsWith('data:image/')) return <img key={i} src={m[2]} alt={m[1]} style={{maxWidth:300,borderRadius:8,margin:'4px 0'}} />;
      return <span key={i} style={{whiteSpace:'pre-wrap',wordBreak:'break-word'}}>{part}</span>;
    });
  };

  const isOrchNode = (msg) => {
    if (msg.role !== 'system' || !msg.metadata) return false;
    try { return !!JSON.parse(msg.metadata).orch; } catch { return false; }
  };
  const getOrchMeta = (msg) => {
    try { return JSON.parse(msg.metadata || '{}'); } catch { return {}; }
  };

  const conv = conversations.find(c => c.id === activeConv);

  return (
    <div style={{ display: 'flex', height: '100dvh', width: '100%', overflow: 'hidden', position: 'fixed', inset: 0, zIndex: 100, maxWidth: '100vw' }}>
      {/* ── Left sidebar — dark sci-fi matching global ── */}
      <div className={showSidebar ? 'chat-sidebar open' : 'chat-sidebar'}
        style={{
          width: 300, minWidth: 300, display: 'flex', flexDirection: 'column',
          background: 'var(--bg-panel)', borderRight: '1px solid var(--border-subtle)',
          transition: 'transform 0.25s ease',
        }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 16px', borderBottom: '1px solid var(--border-subtle)', flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <svg viewBox="0 0 32 32" fill="none" width="28" height="28">
              <polygon points="16,2 30,10 30,22 16,30 2,22 2,10" fill="none" stroke="#00d4ff" strokeWidth="1.5"/>
              <polygon points="16,8 24,13 24,19 16,24 8,19 8,13" fill="none" stroke="#00d4ff" strokeWidth="1" opacity="0.5"/>
              <circle cx="16" cy="16" r="3" fill="#00d4ff"/>
            </svg>
            <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>对话</span>
          </div>
          <button className="btn btn-primary" style={{ fontSize: 11, padding: '4px 10px' }} onClick={() => setShowNew(true)}>+ 新建</button>
        </div>
        {/* Conv list */}
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {conversations.map(c => {
            const isProcessing = c.last_message && c.last_message.role !== 'agent';
            const isActive = activeConv === c.id;
            return (
            <div key={c.id} onClick={() => handleConvClick(c.id)}
              style={{
                padding: '12px 16px', cursor: 'pointer',
                background: isActive
                  ? 'var(--bg-active)'
                  : isProcessing
                    ? 'rgba(51, 112, 255, 0.08)'
                    : 'transparent',
                borderLeft: isActive
                  ? '2px solid var(--cyan)'
                  : isProcessing
                    ? '2px solid #3370ff'
                    : '2px solid transparent',
                transition: 'all 0.15s',
              }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                {isProcessing && <span style={{
                  width: 6, height: 6, borderRadius: '50%', background: '#3370ff',
                  flexShrink: 0, animation: 'pulse 1.5s ease-in-out infinite'
                }} />}
                <div style={{ color: 'var(--text-primary)', fontSize: 13, fontWeight: 500, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.title}</div>
              </div>
              <div style={{ color: 'var(--text-muted)', fontSize: 10 }}>
                {c.agent_name || '未指定'} · {c.message_count || 0} 条
                {c.feishu_chat_id ? ' · 💬' : ''}
                {isProcessing ? ' · ⏳ 处理中' : ''}
              </div>
            </div>
          )})}
        </div>
        {/* Footer */}
        <div style={{ padding: '10px 16px', borderTop: '1px solid var(--border-subtle)', flexShrink: 0 }}>
          <Link to="/" style={{ color: 'var(--text-muted)', fontSize: 12, textDecoration: 'none' }}>← 返回仪表盘</Link>
        </div>
      </div>

      {/* ── Right — light chat area ── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, height: '100%', background: L.bg }}>
        {!activeConv ? (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16, color: L.textMuted }}>
            <svg viewBox="0 0 64 64" fill="none" width="56" height="56"><path d="M8 12a4 4 0 014-4h40a4 4 0 014 4v32a4 4 0 01-4 4H14l-8 8V12z" stroke={L.textMuted} strokeWidth="1.5"/><path d="M20 24h24M20 32h16" stroke={L.textMuted} strokeWidth="1.5" strokeLinecap="round"/></svg>
            <p style={{ fontSize: 14 }}>选择一个对话或创建新的</p>
          </div>
        ) : (
          <>
            {/* Chat header */}
            <div style={{ display: 'flex', alignItems: 'center', padding: '12px 16px', background: L.panel, borderBottom: '1px solid ' + L.border, flexShrink: 0 }}>
              <button onClick={() => setShowSidebar(v => !v)}
                style={{ display: 'none', marginRight: 8, background: 'none', border: 'none', cursor: 'pointer', color: L.textMuted, fontSize: 18 }}>
                ☰
              </button>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: L.text }}>{conv?.title}</div>
                <div style={{ fontSize: 11, color: L.textMuted }}>{conv?.agent_name || ''}{conv?.feishu_chat_id ? ' · 💬 飞书' : ''}</div>
              </div>
            </div>

            {/* Messages */}
            <div ref={chatContainer}
              className="chat-messages-area"
              onScroll={() => {
                const nearBottom = isNearBottom();
                setShowScrollBtn(!nearBottom);
                userScrolledUp.current = !nearBottom;
                if (!switchingRef.current && activeConv) {
                  saveScrollPosition(activeConv);
                }
              }}
              style={{ flex: 1, overflowY: 'auto', padding: '16px 8%', display: 'flex', flexDirection: 'column', gap: 8, position: 'relative' }}>
              {messages.map(msg => {
                if (isOrchNode(msg)) {
                  const meta = getOrchMeta(msg);
                  const c = orchColors[meta.orch] || orchColors.start;
                  const icons = { done:'✅', error:'❌', received:'📥', summarizing:'📝', stopped:'⏹️' };
                  return (
                    <div key={msg.id} style={{ display:'flex', justifyContent:'center' }}>
                      <span style={{
                        fontSize: 10, padding: '3px 14px', borderRadius: 10,
                        background: c.bg, border: `1px solid ${c.border}`, color: c.text,
                        maxWidth: '80%', textAlign: 'center',
                      }}>
                        {icons[meta.orch] || '⚙️'} {msg.content}
                      </span>
                    </div>
                  );
                }
                const isUser = msg.role === 'user';
                return (
                  <div key={msg.id} style={{ display: 'flex', justifyContent: isUser ? 'flex-end' : 'flex-start' }}>
                    <div style={{
                      maxWidth: '72%', padding: '10px 14px', borderRadius: 14, fontSize: 13, lineHeight: 1.65,
                      background: isUser ? L.bubbleUser : L.bubbleAI,
                      border: '1px solid ' + (isUser ? L.bubbleUserBorder : L.bubbleAIborder),
                      color: isUser ? L.bubbleUserText : L.text,
                      borderBottomRightRadius: isUser ? 4 : 14,
                      borderBottomLeftRadius: isUser ? 14 : 4,
                      position: 'relative',
                    }}>
                      <button onClick={() => copyMsg(msg)}
                        style={{
                          position:'absolute', top:4, right:8,
                          fontSize:12, background:'none', border:'none', cursor:'pointer',
                          color: isUser ? 'rgba(255,255,255,0.4)' : L.textMuted,
                          padding:2, lineHeight:1, opacity:0.6
                        }}>
                        {copiedId === msg.id ? '✓' : '📋'}
                      </button>
                      {msg.role === 'system' ? (
                        <span style={{color:L.textMuted,fontSize:12,fontStyle:'italic'}}>{msg.content}</span>
                      ) : renderContent(msg)}
                      <div style={{display:'flex',alignItems:'center',justifyContent:'flex-end',gap:6,marginTop:4}}>
                        <span style={{fontSize:10,color:isUser ? 'rgba(255,255,255,0.6)' : L.textMuted}}>{fmt(msg.created_at)}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
              <div ref={messagesEnd} />
              {/* 回到底部按钮 */}
              {showScrollBtn && (
                <button onClick={() => { messagesEnd.current?.scrollIntoView({ behavior: 'smooth' }); }}
                  style={{
                    position: 'sticky', bottom: 16, left: '50%', transform: 'translateX(-50%)',
                    width: 36, height: 36, borderRadius: '50%',
                    background: 'var(--cyan)', color: '#080c14', border: 'none',
                    cursor: 'pointer', fontSize: 16, display: 'flex', alignItems: 'center', justifyContent: 'center',
                    boxShadow: '0 2px 8px rgba(0,212,255,0.3)', zIndex: 10, opacity: 0.9,
                  }}>
                  ↓
                </button>
              )}
            </div>

            {/* Input */}
            <div style={{ padding: '12px 8%', background: L.panel, borderTop: '1px solid ' + L.border, display: 'flex', gap: 10, flexShrink: 0 }}>
              <input value={input} onChange={e => setInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') sendMsg(); }}
                placeholder="输入消息... (Enter 发送)"
                style={{
                  flex: 1, background: L.inputBg, border: '1px solid ' + L.border,
                  borderRadius: 10, padding: '10px 16px', color: L.text, fontSize: 13,
                  outline: 'none', transition: 'border-color 0.18s',
                }}
                onFocus={e => e.target.style.borderColor = L.inputFocus}
                onBlur={e => e.target.style.borderColor = L.border}
              />
              <button onClick={sendMsg} disabled={sending} className="btn btn-primary" style={{borderRadius:10,padding:'8px 20px'}}>
                {sending ? '...' : '发送'}
              </button>
            </div>
          </>
        )}
      </div>

      {/* ── New conversation modal ── */}
      {showNew && (
        <div className="modal-overlay open" onClick={() => setShowNew(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">新建对话</h3>
              <button className="modal-close" onClick={() => setShowNew(false)}>
                <svg viewBox="0 0 16 16" fill="none" width="16" height="16"><path d="M3 3l10 10M13 3L3 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
              </button>
            </div>
            <div className="form-group">
              <label className="form-label">对话标题</label>
              <input className="form-input" value={newTitle} onChange={e => setNewTitle(e.target.value)} placeholder="给对话起个名字..." />
            </div>
            <div className="form-group">
              <label className="form-label">选择 Agent</label>
              <select className="form-input" value={newAgentId} onChange={e => setNewAgentId(e.target.value)}>
                <option value="">选择 Agent...</option>
                {agents.map(a => <option key={a.id} value={a.id}>{a.name} — {a.portrait || a.description || ''}</option>)}
              </select>
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setShowNew(false)}>取消</button>
              <button className="btn btn-primary" onClick={createConv} disabled={!newAgentId}>创建对话</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
