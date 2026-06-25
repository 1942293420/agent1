const BASE = '/api';

function getCSRFToken() {
  const match = document.cookie.match(/csrftoken=([^;]+)/);
  return match ? match[1] : '';
}

async function request(url, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };
  // Add CSRF token for unsafe methods
  const method = (options.method || 'GET').toUpperCase();
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    const csrf = getCSRFToken();
    if (csrf) headers['X-CSRFToken'] = csrf;
  }
  const res = await fetch(BASE + url, {
    headers,
    ...options,
    method: method,
    credentials: 'include',
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${url}`);
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  get: (url, params) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : '';
    return request(url + qs);
  },
  post: (url, data) => request(url, { method: 'POST', body: JSON.stringify(data) }),
  patch: (url, data) => request(url, { method: 'PATCH', body: JSON.stringify(data) }),
  delete: (url) => request(url, { method: 'DELETE' }),
  parentTaskProgress: (id) => api.get(`/parent-tasks/${id}/progress/`),
  parentTaskStreamUrl: (id) => `/api/parent-tasks/${id}/stream/`,
};
