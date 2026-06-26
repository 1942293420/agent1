import React, { useState, useRef, useMemo } from 'react';
import { marked } from 'marked';
import * as XLSX from 'xlsx';

// Configure marked
marked.setOptions({
  breaks: true,
  gfm: true,
});

export default function OutputView() {
  const [content, setContent] = useState('');
  const [title, setTitle] = useState('');
  const [copied, setCopied] = useState(false);
  const [mode, setMode] = useState('edit'); // edit | preview | markdown | html | table
  const [renderMode, setRenderMode] = useState('markdown'); // markdown | html | table
  const [excelData, setExcelData] = useState(null); // { sheets: [{name, headers, rows}] }
  const [activeSheet, setActiveSheet] = useState(0);
  const [tableSort, setTableSort] = useState({ col: -1, asc: true });
  const fileInputRef = useRef(null);
  const textareaRef = useRef(null);

  const wordCount = content.trim() ? content.trim().split(/\s+/).length : 0;
  const charCount = content.length;

  const handleDownload = () => {
    const ext = renderMode === 'html' ? '.html' : renderMode === 'table' ? '.csv' : '.md';
    const mime = renderMode === 'html' ? 'text/html' : 'text/plain;charset=utf-8';
    const filename = (title.trim() || 'agent-output') + ext;
    const blob = new Blob([content], { type: mime });
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
    setExcelData(null);
  };

  // Parse CSV/TSV text to table data
  const parseTableText = (text) => {
    const lines = text.trim().split('\n');
    if (lines.length < 2) return null;
    const delimiter = text.includes('\t') ? '\t' : ',';
    const headers = lines[0].split(delimiter).map(h => h.trim().replace(/^"|"$/g, ''));
    const rows = lines.slice(1).map(line => {
      const cols = [];
      let inQuote = false;
      let buf = '';
      for (let i = 0; i < line.length; i++) {
        const ch = line[i];
        if (ch === '"') { inQuote = !inQuote; continue; }
        if (!inQuote && ch === delimiter) { cols.push(buf.trim()); buf = ''; continue; }
        buf += ch;
      }
      cols.push(buf.trim());
      return cols;
    }).filter(r => r.length >= headers.length || r.some(c => c));
    if (headers.length >= 2 && rows.length >= 1) return { headers, rows };
    return null;
  };

  // Handle file import (Excel/CSV)
  const handleFileImport = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (evt) => {
      try {
        const data = new Uint8Array(evt.target.result);
        const wb = XLSX.read(data, { type: 'array' });
        const sheets = wb.SheetNames.map(name => {
          const sheet = wb.Sheets[name];
          const json = XLSX.utils.sheet_to_json(sheet, { header: 1, defval: '' });
          if (json.length === 0) return { name, headers: [], rows: [] };
          const headers = (json[0] || []).map(h => String(h ?? ''));
          const rows = json.slice(1).map(r => headers.map((_, i) => String(r[i] ?? '')));
          return { name, headers, rows };
        }).filter(s => s.headers.length > 0);
        setExcelData({ sheets, fileName: file.name });
        setActiveSheet(0);
        setRenderMode('table');
        setMode('preview');
      } catch (err) {
        console.error('Excel parse error:', err);
        alert('文件解析失败：' + err.message);
      }
    };
    reader.readAsArrayBuffer(file);
    // Reset input so same file can be re-imported
    e.target.value = '';
  };

  // Markdown rendering using marked
  const renderMarkdown = (md) => {
    if (!md) return '';
    return marked.parse(md);
  };

  // Table detection from markdown content
  const detectTableData = useMemo(() => {
    if (!content) return null;
    // Try markdown table
    const lines = content.split('\n');
    const tableLines = lines.filter(l => l.includes('|') && /^\|.*\|$/.test(l.trim()) && !/^[\s\|:\-]+$/.test(l.trim().replace(/\|/g, '').replace(/[\s\-:]/g, '')));
    if (tableLines.length >= 2) {
      const headers = tableLines[0].split('|').filter(Boolean).map(h => h.trim());
      const rows = tableLines.slice(1).map(l => l.split('|').filter(Boolean).map(c => c.trim()));
      if (headers.length >= 2 && rows.length >= 1) return { headers, rows };
    }
    // Try CSV
    const csv = parseTableText(content);
    if (csv) return csv;
    return null;
  }, [content]);

  const tableData = detectTableData;

  // Sort table
  const sortedRows = useMemo(() => {
    if (!tableData || tableSort.col < 0) return tableData?.rows || [];
    const rows = [...(tableData.rows || [])];
    rows.sort((a, b) => {
      const va = (a[tableSort.col] || '').toLowerCase();
      const vb = (b[tableSort.col] || '').toLowerCase();
      const na = parseFloat(va), nb = parseFloat(vb);
      if (!isNaN(na) && !isNaN(nb)) return tableSort.asc ? na - nb : nb - na;
      return tableSort.asc ? va.localeCompare(vb) : vb.localeCompare(va);
    });
    return rows;
  }, [tableData, tableSort]);

  const handleSort = (colIdx) => {
    setTableSort(prev => ({
      col: colIdx,
      asc: prev.col === colIdx ? !prev.asc : true,
    }));
  };

  const renderPreview = () => {
    if (!content && !excelData) {
      return <span className="output-empty-hint">无内容 — 切换到「编辑」模式开始写作，或拖入 Excel/CSV 文件</span>;
    }

    // Excel mode
    if (renderMode === 'table' && excelData) {
      const sheet = excelData.sheets[activeSheet];
      if (!sheet) return <span className="output-empty-hint">无数据</span>;
      return (
        <div className="output-table-view">
          {excelData.sheets.length > 1 && (
            <div className="output-sheet-tabs">
              {excelData.sheets.map((s, i) => (
                <button
                  key={i}
                  className={`output-sheet-tab${i === activeSheet ? ' active' : ''}`}
                  onClick={() => setActiveSheet(i)}
                >
                  {s.name}
                </button>
              ))}
            </div>
          )}
          <div className="output-table-wrap">
            <table className="output-table">
              <thead>
                <tr>
                  <th className="output-row-num">#</th>
                  {sheet.headers.map((h, i) => (
                    <th key={i} onClick={() => handleSort(i)} className="output-sortable">
                      {h || `Col${i + 1}`}
                      {tableSort.col === i && <span className="output-sort-icon">{tableSort.asc ? ' ▲' : ' ▼'}</span>}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(tableSort.col >= 0 ? [...sheet.rows].sort((a, b) => {
                  const va = (a[tableSort.col] || '').toLowerCase();
                  const vb = (b[tableSort.col] || '').toLowerCase();
                  const na = parseFloat(va), nb = parseFloat(vb);
                  if (!isNaN(na) && !isNaN(nb)) return tableSort.asc ? na - nb : nb - na;
                  return tableSort.asc ? va.localeCompare(vb) : vb.localeCompare(va);
                }) : sheet.rows).map((row, ri) => (
                  <tr key={ri}>
                    <td className="output-row-num">{ri + 1}</td>
                    {row.map((cell, ci) => (
                      <td key={ci} title={cell}>{cell}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="output-table-info">
            {excelData.fileName} · {sheet.name} · {sheet.rows.length} 行 × {sheet.headers.length} 列
          </div>
        </div>
      );
    }

    // Text-based table mode (detected markdown table or CSV)
    if (renderMode === 'table' && tableData) {
      return (
        <div className="output-table-view">
          <div className="output-table-wrap">
            <table className="output-table">
              <thead>
                <tr>
                  <th className="output-row-num">#</th>
                  {tableData.headers.map((h, i) => (
                    <th key={i} onClick={() => handleSort(i)} className="output-sortable">
                      {h}
                      {tableSort.col === i && <span className="output-sort-icon">{tableSort.asc ? ' ▲' : ' ▼'}</span>}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sortedRows.map((row, ri) => (
                  <tr key={ri}>
                    <td className="output-row-num">{ri + 1}</td>
                    {row.map((cell, ci) => (
                      <td key={ci} title={cell}>{cell}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="output-table-info">
            {tableData.rows.length} 行 × {tableData.headers.length} 列
          </div>
        </div>
      );
    }

    // HTML mode
    if (renderMode === 'html') {
      return (
        <iframe
          className="output-html-frame"
          srcDoc={content}
          sandbox="allow-scripts"
          title="HTML Preview"
        />
      );
    }

    // Default: full markdown rendering with marked
    return (
      <div
        className="output-preview-content"
        dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }}
      />
    );
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
          {mode === 'preview' && (
            <div className="filter-tabs" style={{ marginLeft: 8 }}>
              <button
                className={`filter-tab${renderMode === 'markdown' ? ' active' : ''}`}
                onClick={() => setRenderMode('markdown')}
              >MD</button>
              <button
                className={`filter-tab${renderMode === 'html' ? ' active' : ''}`}
                onClick={() => setRenderMode('html')}
              >HTML</button>
              <button
                className={`filter-tab${renderMode === 'table' ? ' active' : ''}`}
                onClick={() => setRenderMode('table')}
              >📊 表格</button>
            </div>
          )}
          <button className="btn btn-ghost" onClick={handleCopy} disabled={!content}>
            {copied ? '✓ 已复制' : '📋 复制'}
          </button>
          <button className="btn btn-ghost" onClick={() => fileInputRef.current?.click()}>
            📂 导入
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".xlsx,.xls,.csv,.tsv"
            style={{ display: 'none' }}
            onChange={handleFileImport}
          />
          <button className="btn btn-primary" onClick={handleDownload} disabled={!content}>
            ⬇ 下载
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
              placeholder={`在此粘贴或输入 Markdown / HTML / CSV 内容...\n\n# 支持 Markdown 语法\n- **粗体** 和 *斜体*\n- \`行内代码\` 和代码块\n- 表格、列表、链接\n- HTML 片段\n\n也支持拖入或点击「📂 导入」上传 Excel/CSV 文件\n\n点击右上角「预览」查看渲染效果`}
              value={content}
              onChange={e => {
                setContent(e.target.value);
                // Auto-detect table if pasted CSV
              }}
              spellCheck={false}
            />
          ) : (
            <div className="output-preview">
              {renderPreview()}
            </div>
          )}
        </div>

        {/* Status bar */}
        <div className="output-statusbar">
          <span>{wordCount} 词 · {charCount} 字符</span>
          <span className="output-status-lines">
            {content ? content.split('\n').length + ' 行' : ''}
            {excelData ? ` · ${excelData.fileName}` : ''}
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
