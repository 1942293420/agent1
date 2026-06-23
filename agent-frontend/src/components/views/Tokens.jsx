import React, { useState, useEffect } from 'react';
import { api } from '../../api';

export default function TokensView({ tasks, loading }) {
  const [tokenStats, setTokenStats] = useState(null);

  useEffect(() => {
    // No dedicated token endpoint yet — compute from tasks/conversations
    // Placeholder: show system stats
    const stats = {
      totalTasks: tasks.length,
      completedTasks: tasks.filter(t => t.status === 'completed').length,
      pendingTasks: tasks.filter(t => t.status === 'pending').length,
      runningTasks: tasks.filter(t => t.status === 'in_progress' || t.status === 'running').length,
    };
    setTokenStats(stats);
  }, [tasks]);

  if (!tokenStats) return <div style={{padding:40,textAlign:'center',color:'var(--text-muted)'}}>加载中...</div>;

  const total = tokenStats.totalTasks || 1;

  return (
    <>
      <div className="view-header">
        <h1 className="view-title">Tokens 消耗统计</h1>
        <span className="live-indicator"><span className="live-dot" />实时</span>
      </div>

      <div className="metrics-grid">
        <div className="metric-card blue">
          <div className="metric-icon"><span style={{fontSize:18}}>📊</span></div>
          <div className="metric-body">
            <span className="metric-label">总任务</span>
            <span className="metric-value">{tokenStats.totalTasks}</span>
          </div>
        </div>
        <div className="metric-card green">
          <div className="metric-icon"><span style={{fontSize:18}}>✅</span></div>
          <div className="metric-body">
            <span className="metric-label">已完成</span>
            <span className="metric-value">{tokenStats.completedTasks}</span>
            <span className="metric-delta up">{Math.round(tokenStats.completedTasks / total * 100)}%</span>
          </div>
        </div>
        <div className="metric-card amber">
          <div className="metric-icon"><span style={{fontSize:18}}>⏳</span></div>
          <div className="metric-body">
            <span className="metric-label">待处理</span>
            <span className="metric-value">{tokenStats.pendingTasks}</span>
          </div>
        </div>
        <div className="metric-card coral">
          <div className="metric-icon"><span style={{fontSize:18}}>🔄</span></div>
          <div className="metric-body">
            <span className="metric-label">运行中</span>
            <span className="metric-value">{tokenStats.runningTasks}</span>
          </div>
        </div>
        <div className="metric-card purple">
          <div className="metric-icon"><span style={{fontSize:18}}>💰</span></div>
          <div className="metric-body">
            <span className="metric-label">估算 Tokens</span>
            <span className="metric-value" style={{fontSize:18}}>{tokenStats.totalTasks * 2500}</span>
            <span className="metric-delta">~2.5k/任务</span>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header"><h2 className="card-title">消耗明细</h2></div>
        <p style={{color:'var(--text-muted)',fontSize:13,lineHeight:1.8}}>
          Token 精确统计需要后端集成 LLM API 计费模块。<br/>
          当前基于任务数量估算：完成 {tokenStats.completedTasks}/{total} 任务，
          估算消耗约 <strong style={{color:'var(--cyan)'}}>{(tokenStats.totalTasks * 2500).toLocaleString()}</strong> tokens。
        </p>
        <div style={{marginTop:16}}>
          <div className="progress-wrap" style={{marginBottom:8}}>
            <span style={{fontSize:11,color:'var(--text-muted)',width:60}}>完成率</span>
            <div className="progress-bar">
              <div className="progress-fill" style={{width:`${Math.round(tokenStats.completedTasks/total*100)}%`,background:'var(--green)'}} />
            </div>
            <span className="progress-val">{Math.round(tokenStats.completedTasks/total*100)}%</span>
          </div>
          <div className="progress-wrap" style={{marginBottom:8}}>
            <span style={{fontSize:11,color:'var(--text-muted)',width:60}}>运行中</span>
            <div className="progress-bar">
              <div className="progress-fill" style={{width:`${Math.round(tokenStats.runningTasks/total*100)}%`,background:'var(--amber)'}} />
            </div>
            <span className="progress-val">{Math.round(tokenStats.runningTasks/total*100)}%</span>
          </div>
        </div>
      </div>
    </>
  );
}
