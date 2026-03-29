export async function pingApi(name = 'MedLedger') {
  const res = await fetch(`/api/health/${encodeURIComponent(name)}`)
  if (!res.ok) throw new Error(`API request failed (${res.status})`)
  return res.json()
}

export async function checkDatabase() {
  const res = await fetch('/api/health/db')
  if (!res.ok) throw new Error(`DB health request failed (${res.status})`)
  return res.json()
}

export async function extractClinicalEntities(text) {
  const res = await fetch('/api/process', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })
  if (!res.ok) throw new Error(`NLP request failed (${res.status})`)
  return res.json()
}

export async function runPipelineText(text) {
  const res = await fetch('/api/upload/text', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })
  if (!res.ok) throw new Error(`Pipeline request failed (${res.status})`)
  return res.json()
}

export async function runAgentWorkflowTrace(text) {
  const res = await fetch('/api/process/trace', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })
  if (!res.ok) throw new Error(`Workflow request failed (${res.status})`)
  return res.json()
}

export async function runClaimExplain(text) {
  const res = await fetch('/api/process/explain', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })
  if (!res.ok) throw new Error(`Explain request failed (${res.status})`)
  return res.json()
}

export async function getExplainabilityAudit(auditId) {
  const res = await fetch(`/api/process/explain/audit/${encodeURIComponent(auditId)}`)
  if (!res.ok) throw new Error(`Audit request failed (${res.status})`)
  return res.json()
}

export async function startOneClickWorkflow({
  text,
  insurerNumber = '',
  autoCallIfNeeded = true,
  overrideGuardrails = false,
}) {
  const res = await fetch('/api/process/oneclick/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      text,
      insurer_number: insurerNumber || undefined,
      auto_call_if_needed: Boolean(autoCallIfNeeded),
      override_guardrails: Boolean(overrideGuardrails),
    }),
  })
  if (!res.ok) {
    const txt = await res.text().catch(() => '')
    throw new Error(`One-click start failed (${res.status})${txt ? `: ${txt}` : ''}`)
  }
  return res.json()
}

export async function getOneClickWorkflow(runId) {
  const res = await fetch(`/api/process/oneclick/${encodeURIComponent(runId)}`)
  if (!res.ok) {
    const txt = await res.text().catch(() => '')
    throw new Error(`One-click status failed (${res.status})${txt ? `: ${txt}` : ''}`)
  }
  return res.json()
}

export async function overrideOneClickWorkflow(runId) {
  const res = await fetch(`/api/process/oneclick/${encodeURIComponent(runId)}/override`, {
    method: 'POST',
  })
  if (!res.ok) {
    const txt = await res.text().catch(() => '')
    throw new Error(`One-click override failed (${res.status})${txt ? `: ${txt}` : ''}`)
  }
  return res.json()
}

async function uploadFile(path, file) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(path, {
    method: 'POST',
    body: form,
  })
  if (!res.ok) throw new Error(`Upload failed (${res.status})`)
  return res.json()
}

export async function uploadClinicalDocument(file) {
  return uploadFile('/api/upload', file)
}

export async function uploadHandwrittenPrescription(file) {
  return uploadFile('/api/upload/handwritten', file)
}

export async function listClinicalTerms() {
  const res = await fetch('/api/nlp/terms')
  if (!res.ok) throw new Error(`Term list failed (${res.status})`)
  return res.json()
}

export async function importClinicalTerms(terms) {
  const res = await fetch('/api/nlp/terms/import', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(terms),
  })
  if (!res.ok) throw new Error(`Term import failed (${res.status})`)
  return res.json()
}

export async function getDenialDashboard() {
  const res = await fetch('/api/denials/dashboard')
  if (!res.ok) throw new Error(`Denial dashboard failed (${res.status})`)
  return res.json()
}

export async function startVapiOutboundCall({ claimId, denialEventId = null, insurerNumber, assistantId = '', phoneNumberId = '' }) {
  const res = await fetch('/api/denials/vapi/call', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      claim_id: claimId,
      denial_event_id: denialEventId,
      insurer_number: insurerNumber,
      assistant_id: assistantId || undefined,
      phone_number_id: phoneNumberId || undefined,
    }),
  })
  if (!res.ok) {
    const txt = await res.text().catch(() => '')
    throw new Error(`Vapi call failed (${res.status})${txt ? `: ${txt}` : ''}`)
  }
  return res.json()
}

export async function syncVapiCall({ callId, claimId = '', denialEventId = null }) {
  const res = await fetch('/api/denials/vapi/sync', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      call_id: callId,
      claim_id: claimId || undefined,
      denial_event_id: denialEventId ?? undefined,
    }),
  })
  if (!res.ok) {
    const txt = await res.text().catch(() => '')
    throw new Error(`Vapi sync failed (${res.status})${txt ? `: ${txt}` : ''}`)
  }
  return res.json()
}

export async function listRules({ tpa = '', category = '', ruleType = '', active = true, limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams()
  if (tpa) params.set('tpa', tpa)
  if (category) params.set('category', category)
  if (ruleType) params.set('rule_type', ruleType)
  params.set('active', String(Boolean(active)))
  params.set('limit', String(limit))
  params.set('offset', String(offset))

  const res = await fetch(`/api/rules?${params.toString()}`)
  if (!res.ok) throw new Error(`Rule list failed (${res.status})`)
  return res.json()
}

export async function getRuleHistory(ruleId) {
  const res = await fetch(`/api/rules/${encodeURIComponent(ruleId)}/history`)
  if (!res.ok) throw new Error(`Rule history failed (${res.status})`)
  return res.json()
}

export async function getRuleSummary() {
  const res = await fetch('/api/rules/summary')
  if (!res.ok) throw new Error(`Rule summary failed (${res.status})`)
  return res.json()
}

export async function getRuleUpdates({ limit = 25 } = {}) {
  const params = new URLSearchParams()
  params.set('limit', String(limit))
  const res = await fetch(`/api/rules/updates?${params.toString()}`)
  if (!res.ok) throw new Error(`Rule updates failed (${res.status})`)
  return res.json()
}

export async function getRuleConflicts({ limitGroups = 25 } = {}) {
  const params = new URLSearchParams()
  params.set('limit_groups', String(limitGroups))
  const res = await fetch(`/api/rules/conflicts?${params.toString()}`)
  if (!res.ok) throw new Error(`Rule conflicts failed (${res.status})`)
  return res.json()
}
