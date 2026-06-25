import React, { useState, useCallback } from 'react';
import useEventSource from '../../hooks/useEventSource';
import StatsBar from './StatsBar';
import LiveTaskGraph from './LiveTaskGraph';
import ProgressTimeline from './ProgressTimeline';
import StatusPanel from './StatusPanel';

export default function RealtimeDashboard({ parentTaskId, className = '' }) {
  const [nodes, setNodes] = useState([]);
  const [stats, setStats] = useState({ total: 0, done: 0, running: 0, pending: 0, failed: 0, progressPct: 0, bottleneckCount: 0 });
  const [parentStatus, setParentStatus] = useState(null);
  const [events, setEvents] = useState([]);
  const [connected, setConnected] = useState(false);

  const handleInit = useCallback(data => {
    if (data.nodes) setNodes(data.nodes);
    if (data.stats) setStats(data.stats);
    if (data.parentStatus) setParentStatus(data.parentStatus);
    setConnected(true);
  }, []);

  const handleNodeStatus = useCallback(update => {
    setNodes(prev => prev.map(n => (n.nodeId || n.node_id) === update.nodeId ? { ...n, ...update } : n));
    setEvents(prev => [...prev.slice(-199), update]);
  }, []);

  const handleProgressEvent = useCallback(event => {
    setEvents(prev => [...prev.slice(-199), event]);
  }, []);

  const handleStatsUpdate = useCallback(update => {
    setStats(prev => ({ ...prev, ...update }));
    if (update.parentStatus) setParentStatus(update.parentStatus);
  }, []);

  const handleParentDone = useCallback(() => setConnected(false), []);
  const handleError = useCallback(() => setConnected(false), []);

  const url = parentTaskId ? `/api/parent-tasks/${parentTaskId}/stream/` : null;

  useEventSource(url, { onInit: handleInit, onNodeStatus: handleNodeStatus, onProgressEvent: handleProgressEvent, onStatsUpdate: handleStatsUpdate, onParentDone: handleParentDone, onError: handleError }, { enabled: !!parentTaskId });

  return (
    <div className={className}>
      <div className="view-header">
        <h1 className="view-title">实时任务看板</h1>
        <span style={{ fontSize: 11, color: connected ? 'var(--cyan)' : 'var(--text-muted)' }}>
          <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: connected ? 'var(--cyan)' : '#666', marginRight: 6, animation: connected ? 'pulse 1.5s infinite' : 'none' }} />
          {connected ? 'SSE 实时' : '轮询中'}
        </span>
      </div>
      <StatusPanel stats={stats} nodes={nodes} parentStatus={parentStatus} />
      <StatsBar stats={stats} parentStatus={parentStatus} />
      <div style={{ marginTop: 16, display: 'grid', gap: 16 }}>
        <LiveTaskGraph nodes={nodes} />
        <ProgressTimeline events={events} />
      </div>
    </div>
  );
}
