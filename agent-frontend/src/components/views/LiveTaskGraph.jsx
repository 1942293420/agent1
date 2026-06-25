import React, { useMemo } from 'react';

const COLORS = {
  banni:   { stroke: '#22d3ee', text: '#22d3ee' },
  basir:   { stroke: '#a78bfa', text: '#a78bfa' },
  tester:  { stroke: '#fb7185', text: '#fb7185' },
};

const STATUS_COLORS = {
  done:      { fill: 'rgba(6, 78, 59, 0.4)', stroke: '#34d399', text: '#34d399', label: '完成' },
  running:   { fill: 'rgba(8, 51, 68, 0.5)', stroke: '#22d3ee', text: '#22d3ee', label: '执行中' },
  pending:   { fill: 'rgba(30, 41, 59, 0.4)', stroke: '#64748b', text: '#94a3b8', label: '等待' },
  failed:    { fill: 'rgba(136, 19, 55, 0.4)', stroke: '#fb7185', text: '#fb7185', label: '失败' },
};

export default function LiveTaskGraph({ nodes = [], className = '' }) {
  const layout = useMemo(() => {
    if (!nodes.length) return null;
    const nodeMap = {};
    nodes.forEach(n => { nodeMap[n.nodeId || n.node_id] = n; });

    const depths = {};
    function getDepth(nid, visited = new Set()) {
      if (visited.has(nid)) return 0;
      visited.add(nid);
      if (depths[nid] !== undefined) return depths[nid];
      const nd = nodeMap[nid];
      const deps = nd?.dependsOn || nd?.depends_on || [];
      if (!deps.length) { depths[nid] = 0; return 0; }
      depths[nid] = Math.max(...deps.map(d => getDepth(d, visited))) + 1;
      return depths[nid];
    }
    nodes.forEach(n => getDepth(n.nodeId || n.node_id));
    const layers = [];
    nodes.forEach(n => {
      const d = depths[n.nodeId || n.node_id] || 0;
      if (!layers[d]) layers[d] = [];
      layers[d].push(n);
    });

    const NODE_W = 170, NODE_H = 50, GAP_X = 20, GAP_Y = 70, SVG_W = 820;
    const positions = {};
    layers.forEach((layer, li) => {
      const tw = layer.length * NODE_W + (layer.length - 1) * GAP_X;
      const sx = Math.max(40, (SVG_W - tw) / 2);
      layer.forEach((nd, ni) => {
        positions[nd.nodeId || nd.node_id] = { x: sx + ni * (NODE_W + GAP_X), y: 20 + li * (NODE_H + GAP_Y) };
      });
    });
    const edges = [];
    nodes.forEach(nd => {
      (nd.dependsOn || nd.depends_on || []).forEach(dep => {
        const f = positions[dep], t = positions[nd.nodeId || nd.node_id];
        if (f && t) edges.push({ from: f, to: t, status: nd.status });
      });
    });
    const SVG_H = 20 + layers.length * (NODE_H + GAP_Y) + 60;
    return { layers, positions, edges, NODE_W, NODE_H, SVG_W, SVG_H };
  }, [nodes]);

  if (!layout) return null;

  const { positions, edges, NODE_W, NODE_H, SVG_W, SVG_H } = layout;

  return (
    <div className={`card ${className}`} style={{ padding: 0 }}>
      <div style={{ overflowX: 'auto', background: '#020617' }}>
        <svg width={SVG_W} height={SVG_H} viewBox={`0 0 ${SVG_W} ${SVG_H}`} style={{ display: 'block', minWidth: 800 }}>
          <defs>
            <pattern id="grid2" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#1e293b" strokeWidth="0.5" />
            </pattern>
            <marker id="arrowLive" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
              <polygon points="0 0, 8 3, 0 6" fill="#22d3ee" />
            </marker>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid2)" />
          {edges.map((e, i) => (
            <line key={i} x1={e.from.x + NODE_W} y1={e.from.y + NODE_H / 2}
              x2={e.to.x} y2={e.to.y + NODE_H / 2}
              stroke={e.status === 'running' ? '#22d3ee' : '#475569'} strokeWidth={e.status === 'running' ? 1.2 : 0.6}
              markerEnd="url(#arrowLive)" />
          ))}
          {nodes.map(nd => {
            const p = positions[nd.nodeId || nd.node_id];
            if (!p) return null;
            const sc = STATUS_COLORS[nd.status] || STATUS_COLORS.pending;
            const ac = COLORS[nd.agentName?.toLowerCase()] || COLORS.banni;
            const id = nd.nodeId || nd.node_id;
            const isRunning = nd.status === 'running';
            return (
              <g key={id}>
                <rect x={p.x} y={p.y} width={NODE_W} height={NODE_H} rx={6} fill="#0f172a" stroke={sc.stroke} strokeWidth={isRunning ? 1.5 : 0.8} />
                <rect x={p.x} y={p.y} width={NODE_W} height={NODE_H} rx={6} fill={sc.fill} stroke="none" />
                <rect x={p.x} y={p.y + 4} width={3} height={NODE_H - 8} rx={1.5} fill={ac.stroke} />
                <text x={p.x + 12} y={p.y + 19} fill="#e8ecf1" fontSize={11} fontWeight={600} fontFamily="var(--font-mono)">{id}</text>
                <text x={p.x + 12} y={p.y + 34} fill="#94a3b8" fontSize={9} fontFamily="sans-serif">{(nd.label || '').slice(0, 16)}</text>
                <rect x={p.x + NODE_W - 48} y={p.y + 6} width={40} height={15} rx={7} fill={sc.fill} stroke={sc.stroke} strokeWidth={0.5} />
                <text x={p.x + NODE_W - 28} y={p.y + 17} fill={sc.text} fontSize={9} fontWeight={500} textAnchor="middle">{sc.label}</text>
                {isRunning && <rect x={p.x} y={p.y} width={NODE_W} height={NODE_H} rx={6} fill="none" stroke="#22d3ee" strokeWidth={1.5} opacity={0.6}><animate attributeName="opacity" values="0.6;0.1;0.6" dur="1.5s" repeatCount="indefinite" /></rect>}
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
