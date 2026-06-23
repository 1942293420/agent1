import React, { useState, useEffect, useRef } from 'react';
import { api } from '../../api';

const C = {
  green:  '#1D9E75',
  red:    '#E24B4A',
  yellow: '#BA7517',
  cyan:   '#00d4ff',
  blue:   '#378ADD',
  gray:   '#4a5568',
};

export default function Monitor() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const intervalRef = useRef(null);

  const fetchStatus = async () => {
    try {
      const res = await api.get('/system/pipeline-status/');
      setData(res); setError(null);
    } catch (e) {
      setError(e.message || '请求失败');
    }
  };

  useEffect(() => {
    fetchStatus();
    intervalRef.current = setInterval(fetchStatus, 5000);
    return () => clearInterval(intervalRef.current);
  }, []);

  if (error && !data) {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: C.red }}>
        <p>⚠️ 无法连接到监控服务</p>
        <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>{error}</p>
        <button onClick={fetchStatus} style={{ marginTop: 12, padding: '6px 16px', background: C.cyan, border: 'none', borderRadius: 6, cursor: 'pointer', color: '#080c14' }}>重试</button>
      </div>
    );
  }

  const w = data?.worker || {};
  const r = data?.redis_queue || {};
  const h = data?.hermes_engine || {};
  const m = data?.messages || {};

  // 各节点状态判定
  const nodes = [
    {
      id: 'worker', label: '系统监控', sub: 'Worker',
      emoji: '⚙️',
      status: w.status === 'active' ? 'ok' : 'err',
      stat: `${w.version || ''} · ${w.concurrency || 0}并发`,
      desc: w.status === 'active' ? '运行中' : '停止',
      color: w.status === 'active' ? C.green : C.red,
    },
    {
      id: 'redis', label: 'Redis', sub: '消息队列',
      emoji: '📬',
      status: r.status === 'connected' ? 'ok' : 'err',
      stat: `队列 ${r.queue_length ?? '?'} 条`,
      desc: r.queue_length > 0 ? '🔄 处理中' : '⏳ 空闲等待',
      color: r.status === 'connected' ? (r.queue_length > 0 ? C.yellow : C.blue) : C.red,
    },
    {
      id: 'hermes', label: 'Hermes', sub: 'AI 引擎',
      emoji: '🧠',
      status: h.status === 'active' ? 'ok' : (h.status === 'idle' ? 'idle' : 'err'),
      stat: `${h.active_processes ?? 0} 进程`,
      desc: h.status === 'active' ? '✅ 运行中' : h.status === 'idle' ? '😴 待命' : '❌ 异常',
      color: h.status === 'active' ? C.green : (h.status === 'idle' ? C.cyan : C.red),
    },
    {
      id: 'reply', label: '回复', sub: '消息入库',
      emoji: '💬',
      status: 'ok',
      stat: `${m.replies ?? 0} 条 AI 回复`,
      desc: m.pending > 0 ? `⚠️ ${m.pending} 条待处理` : '✅ 无积压',
      color: m.pending > 0 ? C.yellow : C.green,
    },
  ];

  const allOk = nodes.every(n => n.status === 'ok');

  return (
    <div style={{ padding: 24, height: '100%', overflowY: 'auto' }}>
      {/* 顶部状态栏 */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 16, marginBottom: 32,
        padding: '14px 20px', borderRadius: 10,
        background: allOk ? 'rgba(29,158,117,0.06)' : 'rgba(226,75,74,0.06)',
        border: `1px solid ${allOk ? 'rgba(29,158,117,0.25)' : 'rgba(226,75,74,0.25)'}`,
      }}>
        <div style={{
          width: 10, height: 10, borderRadius: '50%',
          background: allOk ? C.green : C.red,
          boxShadow: `0 0 8px ${allOk ? C.green : C.red}`,
        }} />
        <span style={{ fontSize: 15, fontWeight: 600, color: allOk ? C.green : C.red }}>
          {allOk ? '🟢 全链路正常' : '🔴 链路异常'}
        </span>
        <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-muted)' }}>
          更新 {new Date((data?.timestamp || 0) * 1000).toLocaleTimeString()} · 每 2s 刷新
        </span>
      </div>

      {/* ====== 主流水线图 ====== */}
      <div style={{
        marginBottom: 32, padding: '28px 20px',
        background: 'var(--bg-panel)', borderRadius: 12,
        border: '1px solid var(--border-subtle)',
      }}>
        <div style={{
          display: 'flex', alignItems: 'stretch', justifyContent: 'center',
          gap: 0, position: 'relative',
        }}>
          {nodes.map((node, i) => (
            <React.Fragment key={node.id}>
              {/* 节点卡片 */}
              <div style={{
                flex: '1 1 0', maxWidth: 200, minWidth: 140,
                textAlign: 'center',
              }}>
                {/* 节点圆 */}
                <div style={{
                  width: 72, height: 72, borderRadius: '50%', margin: '0 auto 10px',
                  background: `${node.color}15`,
                  border: `2.5px solid ${node.color}`,
                  display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                  boxShadow: `0 0 12px ${node.color}30`,
                  transition: 'all 0.3s',
                }}>
                  <span style={{ fontSize: 22 }}>{node.emoji}</span>
                  <span style={{ fontSize: 9, color: node.color, fontWeight: 700, marginTop: 2 }}>
                    {node.label}
                  </span>
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-secondary)', fontWeight: 600 }}>
                  {node.sub}
                </div>
                <div style={{
                  fontSize: 12, fontWeight: 700, color: node.color, marginTop: 4,
                }}>
                  {node.stat}
                </div>
                <div style={{
                  fontSize: 10, color: 'var(--text-muted)', marginTop: 2,
                }}>
                  {node.desc}
                </div>
                {/* 状态指示灯 */}
                <div style={{ marginTop: 6 }}>
                  <div style={{
                    display: 'inline-block', width: 6, height: 6, borderRadius: '50%',
                    background: node.color,
                    boxShadow: `0 0 4px ${node.color}`,
                    marginRight: 4,
                  }} />
                  <span style={{ fontSize: 9, color: node.color }}>
                    {node.status === 'ok' ? '正常' : node.status === 'idle' ? '待命' : '异常'}
                  </span>
                </div>
              </div>

              {/* 连接器（最后一个不显示） */}
              {i < nodes.length - 1 && (
                <div style={{
                  flex: '0 0 60px', display: 'flex', flexDirection: 'column',
                  alignItems: 'center', justifyContent: 'center',
                }}>
                  <div style={{ position: 'relative', width: '100%', height: 2 }}>
                    {/* 管道背景 */}
                    <div style={{
                      position: 'absolute', top: 0, left: 0, right: 0, height: 2,
                      background: `linear-gradient(90deg, ${nodes[i].color}40, ${nodes[i+1].color}40)`,
                      borderRadius: 1,
                    }} />
                    {/* 流动动画点 */}
                    <div style={{
                      position: 'absolute', top: -2, width: 6, height: 6,
                      borderRadius: '50%', background: C.cyan,
                      boxShadow: '0 0 6px #00d4ff',
                      animation: 'flowLine 1.5s ease-in-out infinite',
                    }} />
                  </div>
                  <span style={{ fontSize: 14, color: 'var(--text-muted)', marginTop: 2 }}>→</span>
                </div>
              )}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* 底部指标卡片 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 14 }}>
        <Card title="📊 消息统计">
          <KV k="总消息" v={m.total} />
          <KV k="已处理" v={m.processed} color={C.green} />
          <KV k="待处理" v={m.pending} color={m.pending > 0 ? C.yellow : 'var(--text-muted)'} alert={m.pending > 0} />
          <KV k="AI 回复" v={m.replies} />
          <KV k="近5分钟" v={`${m.last_5min ?? 0} 条`} />
        </Card>
        <Card title="⚙️ 系统监控">
          <KV k="PID" v={w.pid} />
          <KV k="版本" v={`${w.version} · ${w.concurrency}并发`} />
          <KV k="运行时长" v={uptime(w.uptime_seconds)} />
        </Card>
        <Card title="📬 Redis">
          <KV k="连接" v={r.status === 'connected' ? '✅ 正常' : '❌ 断开'} color={r.status === 'connected' ? C.green : C.red} />
          <KV k="队列名" v="msg_queue" />
          <KV k="消息数" v={r.queue_length ?? '?'} color={r.queue_length > 0 ? C.yellow : 'var(--text-primary)'} />
          <KV k="编排信号" v={r.orch_signals ?? 0} />
        </Card>
        <Card title="🧠 Hermes">
          <KV k="状态" v={h.status === 'active' ? '✅ 活跃' : h.status === 'idle' ? '😴 空闲' : '❓ 未知'} />
          <KV k="进程数" v={h.active_processes ?? '?'} />
          {(h.details || []).slice(0, 2).map((proc, i) => (
            <div key={i} style={{ fontSize: 9, color: 'var(--text-muted)', padding: '2px 6px', background: 'var(--bg-elevated)', borderRadius: 4, marginTop: 4, wordBreak: 'break-all' }}>
              {proc.length > 70 ? proc.slice(0, 70) + '...' : proc}
            </div>
          ))}
        </Card>
      </div>

      {/* CSS 动画 */}
      <style>{`
        @keyframes flowLine {
          0% { left: 0; opacity: 1; }
          100% { left: calc(100% - 6px); opacity: 0.3; }
        }
      `}</style>
    </div>
  );
}

function uptime(s) {
  if (!s || s < 0) return '—';
  return `${Math.floor(s/3600)}h ${Math.floor((s%3600)/60)}m ${s%60}s`;
}

function Card({ title, children }) {
  return (
    <div className="card" style={{ padding: 14 }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 10 }}>{title}</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>{children}</div>
    </div>
  );
}

function KV({ k, v, color, alert }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11 }}>
      <span style={{ color: 'var(--text-muted)' }}>{k}</span>
      <span style={{
        color: color || 'var(--text-primary)', fontWeight: 600,
        ...(alert ? { animation: 'pulse 1.5s ease-in-out infinite' } : {}),
      }}>
        {v ?? '—'}
      </span>
    </div>
  );
}
