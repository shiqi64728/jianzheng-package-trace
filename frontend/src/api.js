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

function json(method, payload) {
  return { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }
}

export const api = {
  health: () => request('/api/health'),
  modelInfo: () => request('/api/model/info'),
  warmup: () => request('/api/model/warmup', { method: 'POST' }),
  cases: () => request('/api/cases'),
  getCase: (caseId) => request(`/api/cases/${caseId}`),
  createCase: (caseName) => request('/api/cases', json('POST', { case_name: caseName, notes: '比赛匿名演示' })),
  uploadNode: (caseId, nodeId, surface, file) => {
    const body = new FormData()
    body.append('node_id', nodeId); body.append('surface', surface); body.append('file', file)
    return request(`/api/cases/${caseId}/nodes`, { method: 'POST', body })
  },
  analyze: (caseId) => request(`/api/cases/${caseId}/analyze`, { method: 'POST' }),
  risk: (caseId) => request(`/api/cases/${caseId}/risk`),
  createReview: (caseId, payload) => request(`/api/cases/${caseId}/reviews`, json('POST', payload)),
  reviews: (caseId) => request(`/api/cases/${caseId}/reviews`),
  importLogistics: (caseId, format, file) => {
    const body = new FormData(); body.append('data_format', format); body.append('file', file)
    return request(`/api/cases/${caseId}/logistics/import`, { method: 'POST', body })
  },
  logistics: (caseId) => request(`/api/cases/${caseId}/logistics`),
  createWorkOrder: (caseId, payload) => request(`/api/cases/${caseId}/work-orders`, json('POST', payload)),
  workOrders: (caseId) => request(`/api/cases/${caseId}/work-orders`),
  workOrderEvent: (id, payload) => request(`/api/work-orders/${id}/events`, json('POST', payload)),
  dashboardSummary: () => request('/api/dashboard/summary'),
  dashboardTrends: () => request('/api/dashboard/trends'),
  analyzeVideo: (file, interval = 5, topK = 5) => {
    const body = new FormData(); body.append('file', file); body.append('sample_interval_frames', interval); body.append('top_k', topK)
    return request('/api/video/analyze', { method: 'POST', body })
  },
  reportUrl: (caseId) => `${API_BASE}/api/cases/${caseId}/report`,
  assetUrl: (path) => `${API_BASE}${path}`,
}
