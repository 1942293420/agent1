import { useEffect, useRef, useCallback } from 'react';

export default function useEventSource(url, handlers = {}, options = {}) {
  const { enabled = true } = options;
  const esRef = useRef(null);
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  const cleanup = useCallback(() => {
    if (esRef.current) { esRef.current.close(); esRef.current = null; }
  }, []);

  useEffect(() => {
    if (!url || !enabled) return;
    const snapshotUrl = url.replace('/stream/', '/progress/');
    fetch(snapshotUrl).then(r => r.json()).then(data => {
      handlersRef.current.onInit?.(data);
    }).catch(() => {});

    const connect = () => {
      cleanup();
      try {
        const es = new EventSource(url);
        esRef.current = es;
        es.addEventListener('init', e => { try { handlersRef.current.onInit?.(JSON.parse(e.data)); } catch {} });
        es.addEventListener('node_status', e => {
          try {
            const d = JSON.parse(e.data);
            handlersRef.current.onNodeStatus?.({ nodeId: d.node_id, label: d.label, status: d.status, agentName: d.agent_name, durationMs: d.duration_ms, isBottleneck: d.is_bottleneck, bottleneckReason: d.bottleneck_reason, startedAt: d.started_at, finishedAt: d.finished_at, timestamp: d.timestamp });
          } catch {}
        });
        es.addEventListener('progress_event', e => { try { handlersRef.current.onProgressEvent?.(JSON.parse(e.data)); } catch {} });
        es.addEventListener('stats_update', e => { try { handlersRef.current.onStatsUpdate?.(JSON.parse(e.data)); } catch {} });
        es.addEventListener('parent_done', e => { try { handlersRef.current.onParentDone?.(JSON.parse(e.data)); es.close(); } catch {} });
        es.addEventListener('error', () => { if (es.readyState === EventSource.CLOSED) esRef.current = null; });
      } catch (err) { handlersRef.current.onError?.(err); }
    };
    connect();
    return cleanup;
  }, [url, enabled]);

  return { disconnect: cleanup };
}
