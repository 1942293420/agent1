import React, { useState, useRef } from 'react';

export default function OutputView() {
  const [content, setContent] = useState('');
  const [title, setTitle] = useState('');
  const [copied, setCopied] = useState(false);
  const [mode, setMode] = useState('edit'); // edit | preview
  const textareaRef = useRef(null);

  const wordCount = content.trim() ? content.trim().split(/\s+/).length : 0;
  const charCount = content.length;

  const handleDownload = () => {
    const filename = (title.trim() || 'agent-output') + '.md';
    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };

  const handleClear = () => {
    if (content && !confirm('确定清空内容？')) return;
    setContent('');
    setTitle('');
  };

  // Simple markdown → HTML (headings, bold, italic, code, links, lists, paragraphs)
  const renderMarkdown = (md) => {
    if (!md) return '';
    let html = md
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      // Code blocks
      .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="md-code"><code>$2</code></pre>')
      // Inline code
      .replace(/`([^`]+)`/g, '<code class="md-inline">$1</code>')
      // Headings
      .replace(/^#### (.+)$/gm, '<h4>$1</h4>')
      .replace(/^### (.+)$/gm, '<h3>$1</h3>')
      .replace(/^## (.+)$/gm, '<h2>$1</h2>')
      .replace(/^# (.+)$/gm, '<h1>$1</h1>')
      // Bold / italic
      .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      // Links
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>')
      // Unordered lists
      .replace(/^- (.+)$/gm, '<li>$1</li>')
      .replace(/(<li>[\s\S]*?<\/li>)/g, '<ul>$1</ul>')
      // Ordered lists
      .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
      // Horizontal rules
      .replace(/^---$/gm, '<hr>')
      // Blockquotes
      .replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
      // Paragraphs (double newlines)
      .replace(/\n\n/g, '</p><p>')
      // Single newlines → <br>
      .replace(/\n/g, '<br>');
    html = '<p>' + html + '</p>';
    // Fix nested <p> inside <pre>
    html = html.replace(/<pre class="md-code">([\s\S]*?)<\/pre>/g, (m, code) => {
      return '<pre class="md-code"><code>' + code.replace(/<\/?p>/g, '').replace(/<br>/g, '\n') + '</code></pre>';
    });
    return html;
  };

  const handlePaste = (e) => {
    // Allow default paste behavior
  };

  return (
    <>
      <div className="view-header">
        <h1 className="view-title">输出面板</h1>
        <div className="view-actions">
          <div className="filter-tabs">
            <button className={`filter-tab${mode === 'edit' ? ' active' : ''}`} onClick={() => setMode('edit')}>
              ✏️ 编辑
            </button>
            <button className={`filter-tab${mode === 'preview' ? ' active' : ''}`} onClick={() => setMode('preview')}>
              👁 预览
            </button>
          </div>
          <button className="btn btn-ghost" onClick={handleCopy} disabled={!content}>
            {copied ? '✓ 已复制' : '📋 复制'}
          </button>
          <button className="btn btn-primary" onClick={handleDownload} disabled={!content}>
            ⬇ 下载 .md
          </button>
        </div>
      </div>

      <div className="output-layout">
        {/* Title input */}
        <input
          className="output-title-input"
          type="text"
          placeholder="文档标题（可选，用作文件名）"
          value={title}
          onChange={e => setTitle(e.target.value)}
        />

        {/* Content area */}
        <div className="output-content-area">
          {mode === 'edit' ? (
            <textarea
              ref={textareaRef}
              className="output-editor"
              placeholder={`在此粘贴或输入 Markdown 内容...

# 支持 Markdown 语法
- **粗体** 和 *斜体*
- \`行内代码\`
- 代码块
- [链接](https://example.com)
- 列表和标题

点击右上角「预览」查看渲染效果`}
              value={content}
              onChange={e => setContent(e.target.value)}
              onPaste={handlePaste}
              spellCheck={false}
            />
          ) : (
            <div
              className="output-preview"
              dangerouslySetInnerHTML={{ __html: renderMarkdown(content) || '<span class="output-empty-hint">无内容 — 切换到「编辑」模式开始写作</span>' }}
            />
          )}
        </div>

        {/* Status bar */}
        <div className="output-statusbar">
          <span>{wordCount} 词 · {charCount} 字符</span>
          <span className="output-status-lines">
            {content ? content.split('\n').length + ' 行' : ''}
          </span>
          {content && (
            <button className="output-clear-btn" onClick={handleClear} title="清空内容">
              🗑 清空
            </button>
          )}
        </div>
      </div>
    </>
  );
}
