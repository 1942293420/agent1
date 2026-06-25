import React from 'react';

export default function StatusPanel({ stats = {}, nodes = [], parentStatus }) {
  const { total = 0, done = 0, running = 0, pending = 0, failed = 0, progressPct = 0 } = stats;
  const runningList = nodes.filter(n => n.status === 'running').map(n => `${n.nodeId || n.node_id}(${n.label})`).join(', ');
  const nextNodes = nodes.filter(n => n.status === 'pending').slice(0, 3).map(n => n.label);

  const parts = [];
  if (total > 0) parts.push(`已拆解 ${total} 个子任务`);
  if (done > 0) parts.push(`${done} 已完成`);
  if (running > 0) parts.push(`${running} 执行中: ${runningList}`);
  if (pending > 0) parts.push(`${pending} 等待`);
  if (failed > 0) parts.push(`${failed} 失败`);
  if (nextNodes.length > 0) parts.push(`下一步: ${nextNodes.join(', ')}`);
  const text = parts.join(' · ');

  const bar = [];
  for (let i = 0; i < 20; i++) {
    const pct = (i / 20) * 100;
    bar.push(pct < progressPct ? '█' : '░');
  }

  return (
    <div style={{ background: 'rgba(29,158,117,0.06)', borderRadius: 8, padding: '10px 16px', border: '1px solid rgba(29,158,117,0.2)', marginBottom: 12 }}>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'rgba(29,158,117,0.9)', lineHeight: 1.8 }}>{text}</div>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'rgba(29,158,117,0.7)', marginTop: 4 }}>{progressPct}% {bar.join('')}</div>
    </div>
  );
}
