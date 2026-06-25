import React from 'react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ errorInfo });
    console.error('[ErrorBoundary]', error, errorInfo);
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{
          padding: '40px 20px', textAlign: 'center',
          color: 'var(--text-secondary)', background: 'var(--bg-deep)',
          minHeight: '100dvh', display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: 16
        }}>
          <div style={{fontSize: 48}}>⚠️</div>
          <h2 style={{color: 'var(--red)', fontSize: 18}}>页面加载异常</h2>
          <p style={{fontSize: 13, maxWidth: 500, color: 'var(--text-muted)'}}>
            {this.state.error?.message || '未知错误'}
          </p>
          <button
            className="btn btn-primary"
            onClick={() => { this.setState({ error: null, errorInfo: null }); window.location.reload(); }}
          >
            重新加载
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
