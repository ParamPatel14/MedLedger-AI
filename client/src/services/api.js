export async function pingApi(name = 'MedLedger') {
  const res = await fetch(`/api/hello/${encodeURIComponent(name)}`)
  if (!res.ok) throw new Error(`API request failed (${res.status})`)
  return res.json()
}

export async function checkDatabase() {
  const res = await fetch('/api/db/health')
  if (!res.ok) throw new Error(`DB health request failed (${res.status})`)
  return res.json()
}

export async function extractClinicalEntities(text) {
  const res = await fetch('/api/nlp/extract', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })
  if (!res.ok) throw new Error(`NLP request failed (${res.status})`)
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

