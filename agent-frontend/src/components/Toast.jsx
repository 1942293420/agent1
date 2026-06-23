import React from 'react';

export default function Toast({ toasts }) {
  if (!toasts.length) return null;
  const icons = {
    success: <svg viewBox="0 0 16 16" fill="none" width="14" height="14"><circle cx="8" cy="8" r="6" stroke="#1D9E75" strokeWidth="1.5"/><path d="M5 8l2 2 4-4" stroke="#1D9E75" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>,
    error: <svg viewBox="0 0 16 16" fill="none" width="14" height="14"><circle cx="8" cy="8" r="6" stroke="#E24B4A" strokeWidth="1.5"/><path d="M6 6l4 4M10 6l-4 4" stroke="#E24B4A" strokeWidth="1.5" strokeLinecap="round"/></svg>,
    info: <svg viewBox="0 0 16 16" fill="none" width="14" height="14"><circle cx="8" cy="8" r="6" stroke="#378ADD" strokeWidth="1.5"/><path d="M8 7v4M8 5.5v.5" stroke="#378ADD" strokeWidth="1.5" strokeLinecap="round"/></svg>,
  };
  return (
    <div className="toast-container" aria-live="assertive">
      {toasts.map(t => (
        <div key={t.id} className={`toast ${t.type}`}>
          {icons[t.type] || icons.info}
          <span>{t.msg}</span>
        </div>
      ))}
    </div>
  );
}
