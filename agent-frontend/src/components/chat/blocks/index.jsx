import React, { useState } from 'react';

export function ScoreBadge({ score, max, label, summary }) {
  const m = max || 10;
  const pct = Math.round((score / m) * 100);
  const color = pct >= 80 ? '#22c55e' : pct >= 60 ? '#f59e0b' : '#ef4444';
  return React.createElement('div', { className: 'score-badge' },
    React.createElement('div', { className: 'score-ring' },
      React.createElement('svg', { width: 44, height: 44, viewBox: '0 0 44 44' },
        React.createElement('circle', { cx: 22, cy: 22, r: 18, fill: 'none', stroke: '#e5e7eb', strokeWidth: 3 }),
        React.createElement('circle', { cx: 22, cy: 22, r: 18, fill: 'none', stroke: color, strokeWidth: 3, strokeDasharray: pct * 1.13 + ' 113', strokeLinecap: 'round' })
      ),
      React.createElement('div', { className: 'score-value', style: { color: color } }, score)
    ),
    React.createElement('div', null,
      label && React.createElement('div', { className: 'score-text' }, label),
      summary && React.createElement('div', { className: 'score-summary' }, summary)
    )
  );
}

export function SectionCard({ variant, title, children }) {
  return React.createElement('div', { className: 'card-' + variant, style: { padding: '10px 14px', borderRadius: 10, margin: '8px 0' } },
    React.createElement('div', { style: { fontWeight: 600, fontSize: 13, marginBottom: 4 } }, title),
    React.createElement('div', { style: { fontSize: 13, lineHeight: 1.6 } }, children)
  );
}

export function CodeBlock({ language, code, showCopy, maxLines }) {
  const [copied, setCopied] = useState(false);
  const [collapsed, setCollapsed] = useState(!!maxLines);
  const dotColors = { js: '#f7df1e', py: '#3572A5', python: '#3572A5', json: '#f78c6c', sh: '#89e051', bash: '#89e051', sql: '#f78c6c', yml: '#ef4444', yaml: '#ef4444', md: '#c792ea' };
  const dot = dotColors[language] || '#64748b';
  return React.createElement('div', { className: 'code-block' },
    React.createElement('div', { className: 'code-header' },
      React.createElement('span', { className: 'code-lang' },
        React.createElement('span', { className: 'code-lang-dot', style: { background: dot } }),
        ' ' + (language || 'text')
      ),
      (showCopy !== false) && React.createElement('button', { className: 'code-copy-btn', onClick: function() { navigator.clipboard.writeText(code); setCopied(true); setTimeout(function() { setCopied(false); }, 2000); } }, copied ? '\u2713 \u5df2\u590d\u5236' : '\ud83d\udccb \u590d\u5236')
    ),
    React.createElement('pre', {
      className: 'code-content' + (collapsed ? ' collapsed' : ''),
      dangerouslySetInnerHTML: { __html: code.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;') }
    }),
    maxLines > 0 && React.createElement('button', { className: 'code-expand-btn', onClick: function() { setCollapsed(!collapsed); } }, collapsed ? '\u5c55\u5f00\u5168\u90e8' : '\u6536\u8d77')
  );
}

export function CodeTabs({ tabs, defaultTab }) {
  const [active, setActive] = useState(defaultTab || 0);
  return React.createElement('div', { className: 'code-tabs' },
    React.createElement('div', { className: 'code-tab-bar' },
      tabs.map(function(t, i) {
        return React.createElement('button', { key: i, className: 'code-tab' + (i === active ? ' active' : ''), onClick: function() { setActive(i); } }, t.label || t.language);
      })
    ),
    tabs.map(function(t, i) { return i === active && React.createElement(CodeBlock, { key: i, language: t.language, code: t.code }); })
  );
}

export function RichTable({ headers, rows }) {
  function badgeClass(v) { var s = String(v || ''); if (/P0|CRITICAL/i.test(s)) return 'badge-p0'; if (/P1|HIGH/i.test(s)) return 'badge-p1'; if (/P2|MEDIUM/i.test(s)) return 'badge-p2'; return ''; }
  return React.createElement('table', { className: 'rich-table' },
    React.createElement('thead', null, React.createElement('tr', null, headers.map(function(h, i) { return React.createElement('th', { key: i }, h); }))),
    React.createElement('tbody', null, rows.map(function(row, ri) {
      return React.createElement('tr', { key: ri }, row.map(function(cell, ci) {
        var val = (cell && cell.value) || cell;
        var b = badgeClass((cell && cell.badge) || val);
        return React.createElement('td', { key: ci }, b ? React.createElement('span', { className: b }, val) : val);
      }));
    }))
  );
}

export function Callout({ variant, children }) {
  return React.createElement('div', { className: 'callout callout-' + (variant || 'info') }, children);
}

export function Checklist({ items }) {
  var list = items || [];
  var [state, setState] = useState(list);
  return React.createElement('ul', { className: 'checklist' },
    state.map(function(item, i) {
      return React.createElement('li', { key: i, onClick: function() { setState(function(prev) { return prev.map(function(it, idx) { return idx === i ? Object.assign({}, it, { done: !it.done }) : it; }); }); } },
        React.createElement('div', { className: 'checklist-dot' + (item.done ? ' done' : '') }),
        React.createElement('span', { className: 'checklist-text' + (item.done ? ' done' : '') }, item.text)
      );
    })
  );
}

export function ErrorBanner({ message, onRetry, detail }) {
  return React.createElement('div', { className: 'error-banner' },
    React.createElement('span', { className: 'error-banner-icon' }, '\u26a0\ufe0f'),
    React.createElement('div', null,
      React.createElement('div', { className: 'error-banner-msg' }, message),
      detail && React.createElement('div', { className: 'error-banner-detail' }, detail)
    ),
    onRetry && React.createElement('button', { className: 'error-banner-retry', onClick: onRetry }, '\u91cd\u8bd5')
  );
}

export function TruncatedBanner({ totalLength, shownLength, logRef }) {
  var pct = Math.round((shownLength / totalLength) * 100);
  return React.createElement('div', { className: 'truncated-banner' },
    '\u5185\u5bb9\u5df2\u622a\u65ad\uff08\u663e\u793a ' + pct + '%\uff0c' + shownLength + '/' + totalLength + ' \u5b57\u7b26\uff09',
    logRef && React.createElement('div', { style: { marginTop: 4 } }, '\ud83d\udcc1 \u5b8c\u6574\u5185\u5bb9\uff1a' + logRef)
  );
}

export function SkeletonShell({ lines }) {
  var lns = lines || [{ width: '80%' }, { width: '60%' }, { width: '70%' }];
  return React.createElement('div', { className: 'skeleton-msg' },
    lns.map(function(l, i) { return React.createElement('div', { key: i, className: 'skeleton-line', style: { width: l.width } }); })
  );
}

export function InlineTag({ variant, label }) {
  return React.createElement('span', { className: 'inline-tag ' + (variant || 'default') }, label);
}

export function DiffView({ fileName, hunks }) {
  var h = hunks || [];
  return React.createElement('div', { className: 'diff-view' },
    fileName && React.createElement('div', { className: 'diff-header' }, fileName),
    h.map(function(hunk, hi) {
      return React.createElement(React.Fragment, { key: hi },
        hunk.lines.map(function(line, li) {
          return React.createElement('div', { key: li, className: 'diff-line diff-' + line.type },
            React.createElement('span', { className: 'diff-line-num' }, line.type === 'add' ? (hunk.newStart || 0) + li : line.type === 'rem' ? (hunk.oldStart || 0) + li : ''),
            React.createElement('span', { className: 'diff-content' }, (line.type === 'add' ? '+ ' : line.type === 'rem' ? '- ' : '  ') + line.content)
          );
        })
      );
    })
  );
}

var FI = { code: '\ud83d\udc0d', doc: '\ud83d\udcc4', image: '\ud83d\uddbc\ufe0f', archive: '\ud83d\udce6' };
export function FileAttachment({ fileName, fileType, fileSize, meta }) {
  var ft = fileType || 'doc';
  return React.createElement('div', { className: 'file-card' },
    React.createElement('div', { className: 'file-card-icon ' + ft }, FI[ft] || '\ud83d\udcc4'),
    React.createElement('div', { className: 'file-card-info' },
      React.createElement('div', { className: 'file-card-name' }, fileName),
      (fileSize || meta) && React.createElement('div', { className: 'file-card-meta' }, [fileSize, meta].filter(Boolean).join(' \u00b7 '))
    )
  );
}

export function ImageGallery({ images }) {
  var imgs = images || [];
  var [lb, setLb] = useState(null);
  return React.createElement(React.Fragment, null,
    React.createElement('div', { className: 'img-gallery' },
      imgs.map(function(img, i) { return React.createElement('img', { key: i, src: img.src, alt: img.caption || '', onClick: function() { setLb(i); }, style: { cursor: 'pointer' } }); })
    ),
    lb !== null && React.createElement('div', { onClick: function() { setLb(null); }, style: { position: 'fixed', inset: 0, background: 'rgba(0,0,0,.85)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' } },
      React.createElement('img', { src: imgs[lb].src, alt: '', style: { maxWidth: '90vw', maxHeight: '90vh', borderRadius: 8 } })
    )
  );
}

export function ImageCompare({ before, after }) {
  return React.createElement('div', { className: 'img-compare' },
    React.createElement('div', { className: 'img-compare-item' },
      React.createElement('span', { className: 'img-compare-label before' }, 'Before'),
      React.createElement('img', { src: before && before.src, alt: 'Before' })
    ),
    React.createElement('div', { className: 'img-compare-item' },
      React.createElement('span', { className: 'img-compare-label after' }, 'After'),
      React.createElement('img', { src: after && after.src, alt: 'After' })
    )
  );
}
