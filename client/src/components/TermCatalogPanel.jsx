import { useEffect, useMemo, useState } from 'react'
import { importClinicalTerms, listClinicalTerms } from '../services/api'

export default function TermCatalogPanel() {
  const [terms, setTerms] = useState([])
  const [state, setState] = useState('idle')
  const [error, setError] = useState('')
  const [importText, setImportText] = useState('')

  const hasTerms = terms.length > 0

  const placeholder = useMemo(
    () =>
      JSON.stringify(
        [
          {
            type: 'diagnosis',
            canonical: 'Diabetes mellitus',
            synonyms: ['diabetes', 'dm'],
            enabled: true,
          },
          {
            type: 'procedure',
            canonical: 'Insulin therapy',
            synonyms: ['insulin'],
            enabled: true,
          },
        ],
        null,
        2,
      ),
    [],
  )

  const refresh = async () => {
    setState('loading')
    setError('')
    try {
      const data = await listClinicalTerms()
      setTerms(Array.isArray(data) ? data : [])
      setState('ok')
    } catch (e) {
      setState('error')
      setError(e?.message || 'Failed to load terms')
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  const runImport = async () => {
    setState('loading')
    setError('')
    try {
      const parsed = JSON.parse(importText)
      if (!Array.isArray(parsed)) {
        throw new Error('Import payload must be a JSON array')
      }
      const data = await importClinicalTerms(parsed)
      setTerms(Array.isArray(data) ? data : [])
      setImportText('')
      setState('ok')
    } catch (e) {
      setState('error')
      setError(e?.message || 'Failed to import terms')
    }
  }

  return (
    <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-base font-semibold text-slate-800">Term Catalog</div>
          <div className="mt-1 text-xs text-slate-500">
            This controls what the extractor can detect. Update dynamic dictionary on-the-fly.
          </div>
        </div>
        <button className="btn btnSecondary" onClick={refresh} disabled={state === 'loading'}>
          Refresh
        </button>
      </div>

      {error && (
        <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-600">
          {error}
        </div>
      )}

      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
          <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Import / Update Terms (JSON)</div>
          <textarea
            className="w-full rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-700 outline-none focus:border-sky-400 focus:ring-1 focus:ring-sky-400 transition-all"
            rows={10}
            value={importText}
            onChange={(e) => setImportText(e.target.value)}
            placeholder={placeholder}
          />
          <div className="mt-3 flex items-center justify-end gap-2">
            <button className="btn btnPrimary text-white" onClick={runImport} disabled={!importText.trim() || state === 'loading'}>
              Import terms
            </button>
          </div>
        </div>

        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
          <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Current Terms</div>
          <div className="mt-2 text-xs text-slate-500 font-medium">
            {state === 'loading'
              ? 'Loading...'
              : hasTerms
                ? `${terms.length} terms loaded`
                : 'No terms loaded yet'}
          </div>
          <pre className="mt-3 max-h-72 overflow-auto rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-700 shadow-inner">
            {JSON.stringify(terms, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  )
}

