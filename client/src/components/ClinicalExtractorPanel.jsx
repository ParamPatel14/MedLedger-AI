import { useState } from 'react'
import { extractClinicalEntities } from '../services/api'

export default function ClinicalExtractorPanel() {
  const [clinicalText, setClinicalText] = useState('')
  const [nlpResult, setNlpResult] = useState(null)
  const [nlpState, setNlpState] = useState('idle')

  const run = async () => {
    setNlpState('loading')
    setNlpResult(null)
    try {
      const data = await extractClinicalEntities(clinicalText)
      setNlpResult(data)
      setNlpState('ok')
    } catch (e) {
      setNlpResult({ error: e?.message || 'Failed to extract entities' })
      setNlpState('error')
    }
  }

  return (
    <div className="mt-4 rounded-xl border border-white/10 bg-white/5 p-4">
      <div className="text-sm font-semibold text-white/90">
        Clinical understanding (entity extraction)
      </div>
      <textarea
        className="mt-2 w-full rounded-lg border border-white/10 bg-black/20 p-3 text-sm text-white/90 outline-none ring-0 placeholder:text-white/40 focus:border-white/20"
        rows={4}
        value={clinicalText}
        onChange={(e) => setClinicalText(e.target.value)}
        placeholder="Paste physician note text here... (example: Patient has diabetes and underwent insulin therapy.)"
      />
      <div className="mt-3 flex items-center justify-between gap-3">
        <div className="text-xs text-white/60">
          {nlpState === 'loading'
            ? 'Extracting...'
            : nlpState === 'ok'
              ? 'Done'
              : nlpState === 'error'
                ? 'Failed'
                : ''}
        </div>
        <button className="btn btnSecondary" onClick={run} disabled={!clinicalText.trim() || nlpState === 'loading'}>
          Run extraction
        </button>
      </div>
      {nlpResult && (
        <pre className="mt-3 overflow-auto rounded-lg border border-white/10 bg-black/30 p-3 text-xs text-white/80">
          {JSON.stringify(nlpResult, null, 2)}
        </pre>
      )}
    </div>
  )
}

