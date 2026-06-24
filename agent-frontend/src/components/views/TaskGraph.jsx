import React, { useState, useEffect, useMemo } from 'react';
import { api } from '../../api';

const STATUS_CONFIG = {
  done:       { bg:'rgba(29,158,117,0.15)', text:'#1D9E75', border:'rgba(29,158,117,0.4)', label:'完成' },
  running:    { bg:'rgba(55,138,221,0.15)', text:'#378ADD', border:'rgba(55,138,221,0.5)', label:'执行中', pulse: true },
  pending:    { bg:'rgba(186,117,23,0.12)', text:'#BA7517', border:'rgba(186,117,23,0.3)', label:'等待' },
  failed:     { bg:'rgba(226,75,74,0.15)',  text:'#E24B4A', border:'rgba(226,75,74,0.5)',  label:'失败' },
  skipped:    { bg:'rgba(128,128,128,0.10)', text:'#888',      border:'rgba(128,128,128,0.25)', label:'跳过' },
  timed_out:  { bg:'rgba(226,75,74,0.12)',  text:'#E24B4A', border:'rgba(226,75,74,0.4)',  label:'超时' },
};

const AGENT_COLORS = {
  banni: '#3370ff',
  basir: '#7C3AED',
  yunshu: '#F59E0B',
  default: '#378ADD',
};

function formatDuration(ms) {
  if (!ms || ms <= 0) return '—';
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms/1000).toFixed(1)}s`;
  const m = Math.floor(ms / 60000);
  const s = Math.round((ms % 60000) / 1000);
  return `${m}m${s}s`;
}

function NodeCard({ node, isExpanded, onToggle, edges, nodesById }) {
  const sc = STATUS_CONFIG[node.status] || STATUS_CONFIG.pending;
  const agentColor = AGENT_COLORS[node.agent_name?.toLowerCase()] || AGENT_COLORS.default;

  const isBlocked = node.status === 'pending' && node.depends_on?.some(dep => {
    const depNode = nodesById[dep];
    return depNode && (depNode.status === 'running' || depNode.status === 'failed');
  });

  return (
    <div className={`task-node${node.is_bottleneck ? ' bottleneck' : ''}${isBlocked ? ' blocked' : ''}`}
      style={{
        '--node-accent': agentColor,
        '--node-status-bg': sc.bg,
        '--node-status-text': sc.text,
        '--node-status-border': sc.border,
      }}
      onClick={onToggle}>
      {/* Node header */}
      <div className="node-header">
        <div className="node-status-bar" style={{ background: sc.text }} />
        <div className="node-meta">
          <span className="node-id">{node.node_id}</span>
          {node.agent_name && (
            <span className="node-agent" style={{ color: agentColor }}>{node.agent_name}</span>
          )}
        </div>
        <div className="node-status-tag" style={{ background: sc.bg, color: sc.text, border: `1px solid ${sc.border}` }}>
          {sc.pulse && <span className="status-pulse" style={{ background: sc.text }} />}
          {sc.label}
        </div>
      </div>

      {/* Node body (always visible) */}
      <div className="node-body">
        <span className="node-label">{node.label}</span>
        <span className="node-duration">{formatDuration(node.duration_ms)}</span>
      </div>

      {/* Expandable details */}
      {isExpanded && (
        <div className="node-details">
          {node.description && (
            <div className="detail-row">
              <span className="detail-label">描述</span>
              <span className="detail-value">{node.description}</span>
            </div>
          )}
          {node.depends_on?.length > 0 && (
            <div className="detail-row">
              <span className="detail-label">依赖</span>
              <span className="detail-value">
                {node.depends_on.map(d => (
                  <span key={d} className="dep-chip">{d}</span>
                ))}
              </span>
            </div>
          )}
          {node.action && (
            <div className="detail-row">
              <span className="detail-label">动作</span>
              <span className="detail-value"><code>{node.action}</code></span>
            </div>
          )}
          {node.started_at && (
            <div className="detail-row">
              <span className="detail-label">开始</span>
              <span className="detail-value">{new Date(node.started_at).toLocaleTimeString()}</span>
            </div>
          )}
          {node.is_bottleneck && node.bottleneck_reason && (
            <div className="detail-row bottleneck-row">
              <span className="detail-label">⚠️ 卡点</span>
              <span className="detail-value">{node.bottleneck_reason}</span>
            </div>
          )}
          {isBlocked && (
            <div className="detail-row blocked-row">
              <span className="detail-label">🔄 阻塞</span>
              <span className="detail-value">等待上游节点完成</span>
            </div>
          )}
          {node.progress_events_count > 0 && (
            <div className="detail-row">
              <span className="detail-label">进度事件</span>
              <span className="detail-value">{node.progress_events_count} 条</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function TaskGraph({ parentTaskId, onClose }) {
  const [graph, setGraph] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedNodes, setExpandedNodes] = useState(new Set());
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchGraph = async () => {
    try {
      const data = await api.get(`/parent-tasks/${parentTaskId}/graph/`);
      setGraph(data);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGraph();
  }, [parentTaskId]);

  // Auto-refresh for running tasks
  useEffect(() => {
    if (!autoRefresh || !graph) return;
    const isRunning = graph.nodes?.some(n => n.status === 'running' || n.status === 'pending');
    if (!isRunning) return;
    const interval = setInterval(fetchGraph, 3000);
    return () => clearInterval(interval);
  }, [autoRefresh, graph?.nodes]);

  const toggleNode = (nodeId) => {
    setExpandedNodes(prev => {
      const next = new Set(prev);
      next.has(nodeId) ? next.delete(nodeId) : next.add(nodeId);
      return next;
    });
  };

  // Compute layer positions for DAG layout
  const { layers, nodePositions, svgEdges, nodesById } = useMemo(() => {
    if (!graph?.nodes) return { layers: [], nodePositions: {}, svgEdges: [], nodesById: {} };

    const nodesById = {};
    graph.nodes.forEach(n => { nodesById[n.node_id] = n; });

    // Assign layers by topological depth
    const depths = {};
    const visited = new Set();

    function getDepth(nodeId) {
      if (depths[nodeId] !== undefined) return depths[nodeId];
      const node = nodesById[nodeId];
      if (!node) return 0;
      if (visited.has(nodeId)) return 0; // cycle guard
      visited.add(nodeId);
      const deps = node.depends_on || [];
      if (deps.length === 0) { depths[nodeId] = 0; return 0; }
      const maxDep = Math.max(...deps.map(d => getDepth(d)));
      depths[nodeId] = maxDep + 1;
      return depths[nodeId];
    }

    graph.nodes.forEach(n => getDepth(n.node_id));

    // Group by layer
    const layerMap = {};
    graph.nodes.forEach(n => {
      const d = depths[n.node_id] || 0;
      if (!layerMap[d]) layerMap[d] = [];
      layerMap[d].push(n);
    });

    const maxLayer = Math.max(...Object.keys(layerMap).map(Number));
    const layers = [];
    for (let i = 0; i <= maxLayer; i++) {
      if (layerMap[i]) layers.push(layerMap[i].sort((a, b) => a.seq - b.seq));
    }

    // Position nodes
    const nodeW = 220, nodeH = 80, gapX = 40, gapY = 30;
    const positions = {};
    layers.forEach((layer, li) => {
      const totalW = layer.length * nodeW + (layer.length - 1) * gapX;
      const startX = -(totalW / 2) + nodeW / 2;
      layer.forEach((node, ni) => {
        positions[node.node_id] = {
          x: startX + ni * (nodeW + gapX),
          y: li * (nodeH + gapY),
          layer: li,
          index: ni,
        };
      });
    });

    // SVG edges
    const edges = [];
    const edgeSet = new Set();
    (graph.edges || []).forEach(e => {
      const from = positions[e.from];
      const to = positions[e.to];
      if (from && to) {
        const key = `${e.from}->${e.to}`;
        if (!edgeSet.has(key)) {
          edgeSet.add(key);
          const midY = (from.y + to.y) / 2;
          edges.push({
            key,
            fromX: from.x,
            fromY: from.y + nodeH / 2,
            toX: to.x,
            toY: to.y - nodeH / 2,
            midY,
          });
        }
      }
    });

    return { layers, nodePositions: positions, svgEdges: edges, nodesById };
  }, [graph]);

  if (loading) {
    return (
      <div className="task-graph-loading">
        <div className="graph-spinner" />
        <span>加载任务图...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="task-graph-error">
        <span>⚠️ 加载失败: {error}</span>
        <button className="btn btn-ghost" onClick={fetchGraph}>重试</button>
      </div>
    );
  }

  if (!graph) return null;

  const progress = graph.total_nodes > 0
    ? ((graph.completed_nodes + graph.failed_nodes) / graph.total_nodes * 100).toFixed(0)
    : 0;

  const svgWidth = 900;
  const svgHeight = Math.max(400, layers.length * 120 + 40);

  return (
    <div className="task-graph-panel">
      {/* Header */}
      <div className="graph-header">
        <div className="graph-header-left">
          <h2 className="graph-title">任务 #{parentTaskId} 执行图</h2>
          <span className={`graph-parent-status status-${graph.parent_status?.toLowerCase()}`}>
            {graph.parent_status}
          </span>
        </div>
        <div className="graph-header-right">
          <div className="graph-stats">
            <span className="stat-item done">{graph.completed_nodes} 完成</span>
            {graph.running_nodes > 0 && <span className="stat-item running">{graph.running_nodes} 执行中</span>}
            {graph.failed_nodes > 0 && <span className="stat-item failed">{graph.failed_nodes} 失败</span>}
            <span className="stat-item pending">{graph.pending_nodes} 等待</span>
          </div>
          <div className="graph-progress-bar">
            <div className="graph-progress-fill" style={{ width: `${progress}%` }} />
          </div>
          <div className="graph-actions">
            <label className="auto-refresh-label">
              <input type="checkbox" checked={autoRefresh} onChange={e => setAutoRefresh(e.target.checked)} />
              自动刷新
            </label>
            <button className="btn btn-ghost" style={{fontSize:11}} onClick={fetchGraph}>🔄 刷新</button>
            <button className="btn btn-ghost" style={{fontSize:11}} onClick={onClose}>✕ 关闭</button>
          </div>
        </div>
      </div>

      {/* Bottleneck alerts */}
      {graph.bottlenecks?.length > 0 && (
        <div className="bottleneck-alerts">
          {graph.bottlenecks.map(b => (
            <div key={b.node_id} className="bottleneck-alert">
              <span className="alert-icon">⚠️</span>
              <span className="alert-node">{b.node_id}: {b.label}</span>
              <span className="alert-time">{formatDuration(b.duration_ms)}</span>
            </div>
          ))}
        </div>
      )}

      {/* Graph area */}
      <div className="graph-canvas-wrap">
        <svg className="graph-svg-edges"
          width={svgWidth} height={svgHeight}
          viewBox={`${-svgWidth/2} 0 ${svgWidth} ${svgHeight}`}>
          {svgEdges.map(e => (
            <g key={e.key}>
              <line
                x1={e.fromX} y1={e.fromY}
                x2={e.toX} y2={e.toY}
                stroke="rgba(120,140,180,0.4)" strokeWidth="1.5" />
              {/* Arrow head */}
              <polygon
                points={`${e.toX-4},${e.toY-8} ${e.toX+4},${e.toY-8} ${e.toX},${e.toY}`}
                fill="rgba(120,140,180,0.5)" />
            </g>
          ))}
        </svg>

        <div className="graph-layers">
          {layers.map((layer, li) => (
            <div key={li} className="graph-layer">
              {layer.map(node => {
                const pos = nodePositions[node.node_id] || {};
                return (
                  <NodeCard
                    key={node.node_id}
                    node={node}
                    isExpanded={expandedNodes.has(node.node_id)}
                    onToggle={() => toggleNode(node.node_id)}
                    nodesById={nodesById}
                  />
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
