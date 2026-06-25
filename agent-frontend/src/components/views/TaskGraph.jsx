import React, { useState, useEffect, useMemo } from 'react';
import { api } from '../../api';

const AGENT_INFO = {
  banni:   { name: 'Banni 云筑', stroke: '#22d3ee', fill: 'rgba(8, 51, 68, 0.4)', emoji: '🔍' },
  basir:   { name: 'Basir 云鉴', stroke: '#a78bfa', fill: 'rgba(76, 29, 149, 0.35)', emoji: '🧠' },
  tester:  { name: '云衡 测试', stroke: '#fb7185', fill: 'rgba(136, 19, 55, 0.3)', emoji: '🔬' },
  yunshu:  { name: '云枢 调度', stroke: '#fbbf24', fill: 'rgba(120, 53, 15, 0.3)', emoji: '⚙️' },
};

const STATUS_COLORS = {
  done:      { fill: 'rgba(6, 78, 59, 0.4)', stroke: '#34d399', text: '#34d399', label: '✓ 完成' },
  running:   { fill: 'rgba(8, 51, 68, 0.5)', stroke: '#22d3ee', text: '#22d3ee', label: '▶ 执行中' },
  pending:   { fill: 'rgba(30, 41, 59, 0.4)', stroke: '#64748b', text: '#94a3b8', label: '○ 等待' },
  failed:    { fill: 'rgba(136, 19, 55, 0.4)', stroke: '#fb7185', text: '#fb7185', label: '✗ 失败' },
};

export default function TaskGraph({ parentTaskId, onClose }) {
  const [graph, setGraph] = useState(null);
  const [planText, setPlanText] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchGraph = async () => {
    try {
      const [gd, ptRes] = await Promise.all([
        api.get(`/parent-tasks/${parentTaskId}/graph/`),
        api.get(`/parent-tasks/${parentTaskId}/`).catch(() => null),
      ]);
      setGraph(gd);
      if (ptRes?.dispatch_plan) {
        try { setPlanText(typeof ptRes.dispatch_plan === 'string' ? ptRes.dispatch_plan : JSON.stringify(ptRes.dispatch_plan)); }
        catch { setPlanText(ptRes.dispatch_plan?.user_message || ptRes.dispatch_plan?.plan || ''); }
      }
      setError(null);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchGraph(); }, [parentTaskId]);

  useEffect(() => {
    if (!graph?.nodes) return;
    const active = graph.nodes.some(n => n.status === 'running' || n.status === 'pending');
    if (!active) return;
    const iv = setInterval(fetchGraph, 3000);
    return () => clearInterval(iv);
  }, [graph?.nodes]);

  const layout = useMemo(() => {
    if (!graph?.nodes?.length) return null;
    const nodes = graph.nodes;
    const nodeMap = {}; nodes.forEach(n => { nodeMap[n.node_id] = n; });
    const depths = {};
    function getDepth(nid, visited = new Set()) {
      if (visited.has(nid)) return 0;
      visited.add(nid);
      if (depths[nid] !== undefined) return depths[nid];
      const nd = nodeMap[nid];
      if (!nd?.depends_on?.length) { depths[nid] = 0; return 0; }
      depths[nid] = Math.max(...nd.depends_on.map(d => getDepth(d, visited))) + 1;
      return depths[nid];
    }
    nodes.forEach(n => getDepth(n.node_id));
    const layers = [];
    nodes.forEach(n => { const d = depths[n.node_id] || 0; if (!layers[d]) layers[d] = []; layers[d].push(n); });

    const NODE_W = 210, NODE_H = 66, GAP_X = 20, GAP_Y = 80, SVG_W = 920;
    const positions = {};
    layers.forEach((layer, li) => {
      const tw = layer.length * NODE_W + (layer.length - 1) * GAP_X;
      const sx = Math.max(30, (SVG_W - tw) / 2);
      layer.forEach((nd, ni) => { positions[nd.node_id] = { x: sx + ni * (NODE_W + GAP_X), y: 30 + li * (NODE_H + GAP_Y) }; });
    });
    const edges = [];
    nodes.forEach(nd => { (nd.depends_on || []).forEach(dep => {
      const f = positions[dep], t = positions[nd.node_id];
      if (f && t) edges.push({ from: f, to: t, status: nd.status });
    });});
    const SVG_H = 30 + layers.length * (NODE_H + GAP_Y) + 50;
    return { layers, positions, edges, nodeMap, NODE_W, NODE_H, SVG_W, SVG_H };
  }, [graph]);

  if (loading) return <div className="task-graph-loading"><div className="graph-spinner" /><span>加载任务图...</span></div>;
  if (error) return <div className="task-graph-error">❌ {error} <button className="btn btn-ghost" onClick={fetchGraph}>重试</button></div>;
  if (!layout) return <div className="task-graph-loading">无数据</div>;

  const { layers, positions, edges, NODE_W, NODE_H, SVG_W, SVG_H } = layout;
  const total = graph.nodes.length;
  const done = graph.nodes.filter(n => n.status === 'done').length;
  const running = graph.nodes.filter(n => n.status === 'running').length;

  return (
    <div className="card" style={{ background: '#020617', border: '1px solid #1e293b', borderRadius: 12, overflow: 'hidden' }}>
      {/* Header */}
      <div className="card-header" style={{ borderBottom: '1px solid #1e293b', padding: '12px 18px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#22d3ee', animation: 'pulse 2s infinite' }} />
          <span style={{ fontSize: 14, fontWeight: 600, color: '#e8ecf1', fontFamily: 'var(--font-mono)' }}>
            #{parentTaskId} · {total} 节点 · {graph.parent_status}
          </span>
        </div>
        <div style={{ display: 'flex', gap: 10, fontSize: 11 }}>
          <span style={{ color: '#34d399' }}>✓ {done}</span>
          <span style={{ color: '#22d3ee' }}>▶ {running}</span>
          <span style={{ color: '#64748b' }}>○ {total - done - running}</span>
          <button className="btn btn-ghost" style={{ fontSize: 10, color: '#94a3b8' }} onClick={fetchGraph}>🔄</button>
          {onClose && <button className="btn btn-ghost" style={{ fontSize: 10, color: '#94a3b8' }} onClick={onClose}>✕</button>}
        </div>
      </div>

      {/* PLAN panel */}
      {planText && (
        <div style={{ margin: '10px 16px', padding: '10px 14px', background: 'rgba(251,191,36,0.06)', border: '1px solid rgba(251,191,36,0.2)', borderRadius: 8, fontSize: 11, fontFamily: 'var(--font-mono)', color: '#fbbf24', maxHeight: 80, overflowY: 'auto', whiteSpace: 'pre-wrap' }}>
          📋 <strong>云枢 PLAN:</strong> {planText.slice(0, 500)}
        </div>
      )}

      {/* SVG Diagram */}
      <div style={{ overflowX: 'auto', background: '#020617' }}>
        <svg width={SVG_W} height={SVG_H} viewBox={`0 0 ${SVG_W} ${SVG_H}`} style={{ display: 'block', minWidth: 900 }}>
          <defs>
            <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#1e293b" strokeWidth="0.5" />
            </pattern>
            <marker id="aGray" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
              <polygon points="0 0, 8 3, 0 6" fill="#475569" />
            </marker>
            <marker id="aColor" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
              <polygon points="0 0, 8 3, 0 6" fill="#22d3ee" />
            </marker>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />

          {edges.map((e, i) => (
            <g key={i}>
              <line x1={e.from.x + NODE_W} y1={e.from.y + NODE_H / 2}
                x2={e.to.x} y2={e.to.y + NODE_H / 2}
                stroke={e.status === 'running' ? '#22d3ee' : '#475569'} strokeWidth={e.status === 'running' ? 1.5 : 0.8}
                strokeDasharray={e.status !== 'running' ? '4,3' : undefined}
                markerEnd={e.status === 'running' ? 'url(#aColor)' : 'url(#aGray)'} />
            </g>
          ))}

          {graph.nodes.map(nd => {
            const p = positions[nd.node_id];
            if (!p) return null;
            const agent = AGENT_INFO[nd.agent_name?.toLowerCase()] || AGENT_INFO.banni;
            const sc = STATUS_COLORS[nd.status] || STATUS_COLORS.pending;
            const isRunning = nd.status === 'running';
            return (
              <g key={nd.node_id}>
                <rect x={p.x} y={p.y} width={NODE_W} height={NODE_H} rx={8} fill="#0f172a" stroke={sc.stroke} strokeWidth={isRunning ? 1.8 : 0.8} />
                <rect x={p.x} y={p.y} width={NODE_W} height={NODE_H} rx={8} fill={sc.fill} stroke="none" />
                {/* Agent color left bar */}
                <rect x={p.x} y={p.y + 4} width={3} height={NODE_H - 8} rx={1.5} fill={agent.stroke} />
                {/* Agent name (primary) */}
                <text x={p.x + 14} y={p.y + 22} fill="#e8ecf1" fontSize={13} fontWeight={600} fontFamily="'Inter', sans-serif">{agent.emoji} {agent.name}</text>
                {/* Task description (secondary) */}
                <text x={p.x + 14} y={p.y + 40} fill="#94a3b8" fontSize={10} fontFamily="sans-serif">
                  {nd.node_id}: {(nd.label || '').length > 16 ? (nd.label || '').slice(0, 16) + '…' : nd.label || ''}
                </text>
                {/* Status badge */}
                <rect x={p.x + NODE_W - 78} y={p.y + 8} width={66} height={16} rx={8} fill={sc.fill} stroke={sc.stroke} strokeWidth={0.5} />
                <text x={p.x + NODE_W - 45} y={p.y + 19} fill={sc.text} fontSize={9} fontWeight={500} textAnchor="middle" fontFamily="sans-serif">{sc.label}</text>
                {/* Duration */}
                {nd.duration_ms > 0 && (
                  <text x={p.x + NODE_W - 78} y={p.y + NODE_H - 6} fill="#475569" fontSize={9} fontFamily="var(--font-mono)" textAnchor="end">
                    {(nd.duration_ms / 1000).toFixed(1)}s
                  </text>
                )}
                {/* Running pulse */}
                {isRunning && <rect x={p.x} y={p.y} width={NODE_W} height={NODE_H} rx={8} fill="none" stroke="#22d3ee" strokeWidth={1.8} opacity={0.5}>
                  <animate attributeName="opacity" values="0.5;0.1;0.5" dur="1.5s" repeatCount="indefinite" />
                </rect>}
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
