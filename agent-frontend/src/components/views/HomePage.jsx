import React, { useEffect, useState } from 'react';

const NODES = [
  { id: 'feishu',   label: '飞书 Bot',      sub: '用户交互',   x: 60,  y: 60,  w: 140, h: 60, color: '#fbbf24', cats: ['外部'] },
  { id: 'web',      label: 'Web Chat',      sub: 'Vite + React', x: 60,  y: 160, w: 140, h: 60, color: '#22d3ee', cats: ['外部'] },
  { id: 'api',      label: 'Django REST',   sub: ':8001 gunicorn', x: 300, y: 60, w: 170, h: 60, color: '#34d399', cats: ['网关'] },
  { id: 'redis',    label: 'Redis Queue',   sub: 'Pub/Sub + List', x: 300, y: 200, w: 170, h: 50, color: '#fb923c', cats: ['网关'] },
  { id: 'worker',   label: 'Worker Pool',   sub: '20 并发',      x: 560, y: 100, w: 150, h: 70, color: '#a78bfa', cats: ['核心'] },
  { id: 'yunshu',   label: '云枢 调度器',    sub: 'PLAN→SPAWN→WAIT', x: 780, y: 30, w: 160, h: 60, color: '#f59e0b', cats: ['Agent'] },
  { id: 'banni',    label: 'Banni 云筑',     sub: '搜索/工程',   x: 780, y: 120, w: 130, h: 55, color: '#22d3ee', cats: ['Agent'] },
  { id: 'basir',    label: 'Basir 云鉴',     sub: '分析/推理',   x: 930, y: 120, w: 130, h: 55, color: '#a78bfa', cats: ['Agent'] },
  { id: 'yunheng',  label: '云衡 测试',      sub: 'TDD/安全',    x: 780, y: 200, w: 130, h: 55, color: '#fb7185', cats: ['Agent'] },
  { id: 'sqlite',   label: 'SQLite WAL',    sub: '持久存储',     x: 560, y: 220, w: 150, h: 50, color: '#a78bfa', cats: ['核心'] },
  { id: 'sse',      label: 'SSE Stream',    sub: '实时推送',     x: 1000, y: 30, w: 130, h: 55, color: '#34d399', cats: ['推送'] },
  { id: 'monitor',  label: 'TaskNode 监控',  sub: '可视化看板',   x: 1000, y: 110, w: 130, h: 55, color: '#34d399', cats: ['推送'] },
];

const EDGES = [
  ['feishu', 'api'], ['web', 'api'], ['api', 'redis'], ['redis', 'worker'],
  ['worker', 'yunshu'], ['yunshu', 'banni'], ['yunshu', 'basir'], ['yunshu', 'yunheng'],
  ['worker', 'sqlite'], ['api', 'sqlite'],
  ['yunshu', 'sse'], ['yunshu', 'monitor'],
];

const SVG_W = 1200;
const SVG_H = 320;

export default function HomePage() {
  const [t, setT] = useState(0);

  useEffect(() => {
    const iv = setInterval(() => setT(prev => prev + 1), 50);
    return () => clearInterval(iv);
  }, []);

  const nodeMap = {};
  NODES.forEach(n => { nodeMap[n.id] = n; });

  // Particle animations along edges
  const particles = EDGES.map(([from, to], i) => {
    const f = nodeMap[from], tgt = nodeMap[to];
    if (!f || !tgt) return null;
    const progress = ((t * 0.3 + i * 37) % 100) / 100;
    const px = f.x + f.w + (tgt.x - f.x - f.w) * progress;
    const py = f.y + f.h / 2 + (tgt.y + tgt.h / 2 - f.y - f.h / 2) * progress;
    return { key: `${from}→${to}`, px, py, color: nodeMap[from].color, progress };
  }).filter(Boolean);

  return (
    <div style={{ background: '#08090a', minHeight: '100vh', fontFamily: "'Inter', system-ui, sans-serif", color: '#f7f8f8' }}>
      {/* Hero */}
      <div style={{ padding: '60px 40px 30px', textAlign: 'center' }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
          <div style={{ width: 14, height: 14, borderRadius: '50%', background: '#22d3ee', boxShadow: '0 0 20px rgba(34,211,238,0.4)', animation: 'pulse 2s infinite' }} />
          <h1 style={{ fontSize: 32, fontWeight: 600, letterSpacing: '-0.02em', margin: 0 }}>Agent<span style={{ color: '#22d3ee' }}>OS</span></h1>
        </div>
        <p style={{ fontSize: 16, color: '#94a3b8', maxWidth: 560, margin: '0 auto 20px', lineHeight: 1.6 }}>
          多 Agent 协同平台 — 云枢调度 · 三引擎协同 · 实时可视化监控
        </p>
        <div style={{ display: 'flex', gap: 10, justifyContent: 'center', flexWrap: 'wrap' }}>
          <span style={{ fontSize: 11, padding: '4px 12px', borderRadius: 20, background: 'rgba(34,211,238,0.1)', color: '#22d3ee', border: '1px solid rgba(34,211,238,0.2)' }}>PLAN → SPAWN → REFLECT → REPLY</span>
          <span style={{ fontSize: 11, padding: '4px 12px', borderRadius: 20, background: 'rgba(167,139,250,0.1)', color: '#a78bfa', border: '1px solid rgba(167,139,250,0.2)' }}>Redis Pub/Sub + SSE 实时流</span>
          <span style={{ fontSize: 11, padding: '4px 12px', borderRadius: 20, background: 'rgba(52,211,153,0.1)', color: '#34d399', border: '1px solid rgba(52,211,153,0.2)' }}>TaskNode 可视化 DAG</span>
        </div>
      </div>

      {/* Animated Architecture SVG */}
      <div style={{ maxWidth: SVG_W + 40, margin: '0 auto', padding: '0 20px', overflowX: 'auto' }}>
        <svg width={SVG_W} height={SVG_H} viewBox={`0 0 ${SVG_W} ${SVG_H}`} style={{ display: 'block', margin: '0 auto' }}>
          <defs>
            <pattern id="grid2" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#1a1d23" strokeWidth="0.5" />
            </pattern>
            <marker id="arr" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
              <polygon points="0 0, 8 3, 0 6" fill="#475569" />
            </marker>
            <filter id="glow"><feGaussianBlur stdDeviation="4" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid2)" />

          {/* Category labels */}
          {['外部系统', '网关层', '核心引擎', 'Agent 矩阵', '推送与监控'].map((label, i) => {
            const xPos = [10, 280, 540, 770, 980][i];
            return (
              <g key={label}>
                <rect x={xPos} y={SVG_H - 20} width={i === 0 ? 160 : i === 1 ? 200 : i === 4 ? 180 : 150} height={16} rx={8} fill="none" stroke="#1e293b" strokeWidth="1" />
                <text x={i === 0 ? xPos + 80 : i === 1 ? xPos + 100 : i === 4 ? xPos + 90 : xPos + 75} y={SVG_H - 8} fill="#475569" fontSize={9} textAnchor="middle">{label}</text>
              </g>
            );
          })}

          {/* Edges */}
          {EDGES.map(([from, to], i) => {
            const f = nodeMap[from], tgt = nodeMap[to];
            if (!f || !tgt) return null;
            const opacity = 0.3 + 0.3 * Math.sin(t * 0.05 + i);
            return (
              <line key={`e${i}`} x1={f.x + f.w} y1={f.y + f.h / 2} x2={tgt.x} y2={tgt.y + tgt.h / 2}
                stroke={f.color} strokeWidth={1} opacity={opacity}
                markerEnd="url(#arr)" />
            );
          })}

          {/* Particles */}
          {particles.map(p => (
            <circle key={p.key + (p.progress * 100 | 0)} cx={p.px} cy={p.py} r={p.progress < 0.05 || p.progress > 0.95 ? 2.5 : 1.5}
              fill={p.color} opacity={0.6 + 0.4 * Math.sin(p.progress * Math.PI)} filter="url(#glow)" />
          ))}

          {/* Nodes */}
          {NODES.map(nd => {
            const pulse = nd.id === 'yunshu' ? 0.5 + 0.3 * Math.sin(t * 0.04) : nd.id === 'worker' ? 0.7 + 0.2 * Math.sin(t * 0.06) : 0;
            return (
              <g key={nd.id}>
                <rect x={nd.x} y={nd.y} width={nd.w} height={nd.h} rx={8}
                  fill="rgba(15,16,17,0.95)" stroke={nd.color} strokeWidth={1}
                  style={{ filter: pulse ? `drop-shadow(0 0 ${8 * pulse}px ${nd.color}40)` : undefined }} />
                <rect x={nd.x} y={nd.y + 4} width={3} height={nd.h - 8} rx={1.5} fill={nd.color} />
                <text x={nd.x + 14} y={nd.y + 24} fill="#f7f8f8" fontSize={12} fontWeight={600}
                  fontFamily="'Inter', sans-serif">{nd.label}</text>
                <text x={nd.x + 14} y={nd.y + 42} fill={nd.color} fontSize={10}
                  fontFamily="'JetBrains Mono', monospace">{nd.sub}</text>
              </g>
            );
          })}
        </svg>
      </div>

      {/* Feature Grid */}
      <div style={{ maxWidth: 1040, margin: '40px auto', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 16, padding: '0 20px' }}>
        {[
          { icon: '⚡', title: '方案 B 调度', desc: '代码接管 SPAWN，LLM 只输出 PLAN，消除协议理解依赖', color: '#f59e0b' },
          { icon: '🔍', title: 'Banni 云筑', desc: '搜索、代码编写、文件操作、飞书文档创建', color: '#22d3ee' },
          { icon: '🧠', title: 'Basir 云鉴', desc: '数据分析、逻辑推理、报告生成、架构分析', color: '#a78bfa' },
          { icon: '🔬', title: '云衡 测试', desc: 'TDD 测试驱动、代码审查、安全扫描、缺陷诊断', color: '#fb7185' },
          { icon: '📡', title: 'SSE 实时推送', desc: 'Redis Pub/Sub → SSE 流，毫秒级进度同步', color: '#34d399' },
          { icon: '📊', title: 'TaskNode 监控', desc: 'DAG 节点图 + 实时仪表盘 + 瓶颈检测', color: '#22d3ee' },
        ].map((f, i) => (
          <div key={i} style={{ background: '#0f1011', borderRadius: 10, border: '1px solid #191a1b', padding: '20px 18px', transition: 'all 0.2s' }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = f.color + '40'; e.currentTarget.style.transform = 'translateY(-2px)'; }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = '#191a1b'; e.currentTarget.style.transform = ''; }}>
            <div style={{ fontSize: 24, marginBottom: 10 }}>{f.icon}</div>
            <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 6px' }}>{f.title}</h3>
            <p style={{ fontSize: 12, color: '#64748b', margin: 0, lineHeight: 1.5 }}>{f.desc}</p>
          </div>
        ))}
      </div>

      {/* Stats */}
      <div style={{ maxWidth: 1040, margin: '20px auto 60px', display: 'flex', gap: 20, justifyContent: 'center', flexWrap: 'wrap', padding: '0 20px' }}>
        {[
          { num: '3', label: 'Agent 引擎', color: '#22d3ee' },
          { num: '20', label: '并发 Worker', color: '#a78bfa' },
          { num: 'SSE', label: '实时推送', color: '#34d399' },
          { num: 'v4.1', label: '方案 B', color: '#f59e0b' },
        ].map((s, i) => (
          <div key={i} style={{ textAlign: 'center', minWidth: 100 }}>
            <div style={{ fontSize: 28, fontWeight: 700, color: s.color, fontFamily: "'JetBrains Mono', monospace" }}>{s.num}</div>
            <div style={{ fontSize: 11, color: '#64748b', marginTop: 4 }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div style={{ textAlign: 'center', padding: '20px', borderTop: '1px solid #191a1b', fontSize: 12, color: '#475569' }}>
        AgentOS v4.1 · 方案 B · 2026
      </div>
    </div>
  );
}
