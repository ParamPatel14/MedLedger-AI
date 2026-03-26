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

  const renderTags = (items, colorClass) => {
    if (!items || items.length === 0) return <span className="text-slate-400 italic text-xs">None found</span>;
    return (
      <div className="flex flex-wrap gap-2">
        {items.map((item, i) => (
          <span key={i} className={`px-2 py-1 rounded-md text-xs font-medium border ${colorClass}`}>
            {item}
          </span>
        ))}
      </div>
    );
  }

  return (
    <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="text-base font-semibold text-slate-800">
        Clinical Entity Extraction
      </div>
      <p className="text-xs text-slate-500 mb-3">
        Enter a physician note to extract diagnoses, procedures, and medications.
      </p>
      <textarea
        className="w-full rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-800 outline-none ring-0 placeholder:text-slate-400 focus:border-sky-400 focus:ring-1 focus:ring-sky-400 transition-all"
        rows={4}
        value={clinicalText}
        onChange={(e) => setClinicalText(e.target.value)}
        placeholder="Paste physician note text here... (example: Pt w/ HTN and diabtes. BP elevated. Started on Metformin.)"
      />
      <div className="mt-3 flex items-center justify-between gap-3">
        <div className="text-xs text-slate-500 font-medium">
          {nlpState === 'loading'
            ? 'Processing with Medical NLP Models...'
            : nlpState === 'ok'
              ? 'Extraction Complete'
              : nlpState === 'error'
                ? 'Extraction Failed'
                : ''}
        </div>
        <button 
          className="btn btnPrimary text-white" 
          onClick={run} 
          disabled={!clinicalText.trim() || nlpState === 'loading'}
        >
          {nlpState === 'loading' ? 'Extracting...' : 'Run Extraction'}
        </button>
      </div>

      {nlpResult && !nlpResult.error && (
        <div className="mt-5 space-y-4 border-t border-slate-100 pt-4">
          <div>
            <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Diagnoses</h4>
            {renderTags(nlpResult.diagnosis, "bg-red-50 text-red-700 border-red-200")}
          </div>
          <div>
            <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Procedures</h4>
            {renderTags(nlpResult.procedures, "bg-sky-50 text-sky-700 border-sky-200")}
          </div>
          <div>
            <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Medications</h4>
            {renderTags(nlpResult.medications, "bg-emerald-50 text-emerald-700 border-emerald-200")}
          </div>

          {nlpResult.entities && nlpResult.entities.length > 0 && (
            <details className="mt-4 group">
              <summary className="text-xs font-medium text-slate-500 cursor-pointer hover:text-sky-600 transition-colors">
                View Raw Entity Data
              </summary>
              <pre className="mt-2 overflow-auto rounded-lg border border-slate-200 bg-slate-50 p-3 text-[11px] text-slate-700">
                {JSON.stringify(nlpResult.entities, null, 2)}
              </pre>
            </details>
          )}
        </div>
      )}

      {nlpResult && nlpResult.error && (
        <div className="mt-4 rounded-lg bg-red-50 p-3 border border-red-100 text-sm text-red-600">
          {nlpResult.error}
        </div>
      )}
    </div>
  )
}

