const API_BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/$/, '')

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options)
  if (!response.ok) {
    let payload = {}
    try { payload = await response.json() } catch { payload = {} }
    throw new Error(payload?.error?.message || `请求失败（${response.status}）`)
  }
  const type = response.headers.get('content-type') || ''
  return type.includes('application/json') ? response.json() : response.text()
}

export const api = {
  health: () => request('/api/health'),
  modelInfo: () => request('/api/model/info'),
  warmup: () => request('/api/model/warmup', { method: 'POST' }),
  createCase: (caseName) => request('/api/cases', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ case_name: caseName, notes: '比赛匿名演示' }),
  }),
  uploadNode: (caseId, nodeId, surface, file) => {
    const body = new FormData()
    body.append('node_id', nodeId)
    body.append('surface', surface || 'front')
    body.append('file', file)
    return request(`/api/cases/${caseId}/nodes`, { method: 'POST', body })
  },
  analyze: (caseId) => request(`/api/cases/${caseId}/analyze`, { method: 'POST' }),
  createReview: (caseId, payload) => request(`/api/cases/${caseId}/reviews`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }),
  reviews: (caseId) => request(`/api/cases/${caseId}/reviews`),
  reportUrl: (caseId) => `${API_BASE}/api/cases/${caseId}/report`,
}
