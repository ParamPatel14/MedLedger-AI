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
