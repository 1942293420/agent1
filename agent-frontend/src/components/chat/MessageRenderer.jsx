import React from 'react';
import { CodeBlock, SectionCard, RichTable, ScoreBadge, Callout, Checklist, ErrorBanner } from './blocks/index';

// Simple semantic markdown parser — detects structures and maps to components
export default function MessageRenderer({ content = '', isStreaming, onRetry, maxLength = 8000 }) {
  const text = String(content);

  // Check for errors first
  if (/Traceback|Error:|error:|✗.*失败|FAILED/i.test(text)) {
    const lines = text.split('\n');
    const errLine = lines.find(l => /Traceback|Error:|error:/i.test(l)) || '';
    return React.createElement('div', null,
      React.createElement('p', { style: { margin: 0 } }, text),
      React.createElement(ErrorBanner, { message: errLine.slice(0, 100) || '执行出错', onRetry })
    );
  }

  // Detect sections from headings
  const sectionPattern = /^(#{1,3})\s+(.*?)$/gm;
  const sections = [];
  let lastIdx = 0;
  let match;
  while ((match = sectionPattern.exec(text)) !== null) {
    if (match.index > lastIdx) {
      sections.push({ type: 'text', content: text.slice(lastIdx, match.index) });
    }
    const title = match[2];
    const variant = /亮点|优点|优势|✨/.test(title) ? 'positive' :
      /问题|风险|bug|漏洞|缺陷|严重/.test(title) ? 'negative' :
      /警告|提醒|注意/.test(title) ? 'warning' : 'neutral';
    sections.push({ type: 'heading', level: match[1].length, title, variant, start: match.index, end: match.index + match[0].length });
    lastIdx = match.index + match[0].length;
  }
  if (lastIdx < text.length) sections.push({ type: 'text', content: text.slice(lastIdx) });

  // Render sections
  if (sections.length > 1) {
    return React.createElement('div', null,
      sections.map((sec, i) => {
        if (sec.type === 'heading') {
          const body = text.slice(sec.end, sections[i + 1]?.start || undefined).trim();
          const bodyEl = renderBodyContent(body);
          return React.createElement('div', { key: i },
            React.createElement(SectionCard, { variant: sec.variant, title: sec.title }, bodyEl)
          );
        }
        return React.createElement('div', { key: i }, renderBodyContent(sec.content));
      })
    );
  }

  // Single content: render inline
  return renderBodyContent(text);
}

function renderBodyContent(text = '') {
  if (!text.trim()) return null;
  const elements = [];

  // Code blocks
  const parts = text.split(/(```(\w*)\n([\s\S]*?)```)/g);
  let i = 0;
  while (i < parts.length) {
    const part = parts[i];
    if (i > 0 && i % 4 === 1) {
      const lang = parts[i + 1] || 'text';
      const code = parts[i + 2] || '';
      elements.push(React.createElement(CodeBlock, { key: i, language: lang, code: code.trim(), maxLines: code.split('\n').length > 15 ? 15 : 0 }));
      i += 4;
    } else {
      if (part.trim()) {
        elements.push(renderTextBlock(part, i));
      }
      i++;
    }
  }

  return elements.length === 1 ? elements[0] : React.createElement('div', null, ...elements);
}

function renderTextBlock(text, key) {
  const els = [];

  // Tables
  if (text.includes('|') && /^\|.*\|$/m.test(text)) {
    const lines = text.split('\n').filter(l => l.includes('|'));
    const headerLine = lines[0];
    let dataStart = 1;
    if (lines[1] && lines[1].replace(/[\s\|\-:]/g, '') === '') dataStart = 2;
    const headers = (headerLine || '').split('|').filter(Boolean).map(h => h.trim());
    const rows = lines.slice(dataStart).map(l => l.split('|').filter(Boolean).map(c => c.trim()));
    if (headers.length > 0 && rows.length > 0) {
      els.push(React.createElement(RichTable, { key, headers, rows }));
      return els[0];
    }
  }

  // Score badges: detect "X.X/10" or "X/10" patterns
  const scoreMatch = text.match(/(\d+\.?\d*)\s*\/\s*(\d+)/);
  if (scoreMatch) {
    const score = parseFloat(scoreMatch[1]);
    const max = parseInt(scoreMatch[2]) || 10;
    const labelMatch = text.match(/(总体|综合|评分|score).*?(\d+\.?\d*)/i);
    els.push(React.createElement(ScoreBadge, { key, score, max, label: '评分' }));
    return els[0];
  }

  // Callout: blockquote with keywords
  if (/^>\s*.*?(结论|总结|建议|注意)/m.test(text)) {
    return React.createElement(Callout, { key, variant: /注意|警告/i.test(text) ? 'warning' : 'info' },
      text.replace(/^>\s*/gm, ''));
  }

  // Checklists
  if (/\[ \]/.test(text) || /\[x\]/i.test(text)) {
    const items = text.split('\n').filter(l => /\[[ x]\]/i.test(l)).map(l => ({
      text: l.replace(/^[-*]\s*\[[ x]\]\s*/i, ''),
      done: /\[x\]/i.test(l)
    }));
    if (items.length > 0) {
      els.push(React.createElement(Checklist, { key, items }));
      return els[0];
    }
  }

  // Plain text with markdown links
  const html = text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code style="background:rgba(0,0,0,.06);padding:1px 5px;border-radius:4px;font-family:monospace;font-size:12px">$1</code>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" style="color:#3370ff">$1</a>')
    .replace(/\n/g, '<br/>');

  return React.createElement('span', { key, dangerouslySetInnerHTML: { __html: html } });
}
