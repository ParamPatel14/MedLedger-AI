import { useMemo, useState } from 'react'
import { getExplainabilityAudit, runClaimExplain } from '../services/api'

function formatScore(value) {
  const n = Number(value)
  if (Number.isNaN(n)) return '0.00'
  return n.toFixed(2)
}

function decisionColor(decision) {
  const d = String(decision || '').toUpperCase()
  if (d === 'APPROVE') return 'bg-emerald-50 text-emerald-700 border-emerald-200'
  if (d === 'WARN') return 'bg-amber-50 text-amber-800 border-amber-200'
  if (d === 'ESCALATE') return 'bg-orange-50 text-orange-700 border-orange-200'
  if (d === 'BLOCK') return 'bg-rose-50 text-rose-700 border-rose-200'
  return 'bg-slate-50 text-slate-700 border-slate-200'
}

function typeTitle(type) {
  const t = String(type || '').toLowerCase()
  if (t === 'clinical') return 'Diagnosis Reasoning'
  if (t === 'coding') return 'Code Assignment Logic'
  if (t === 'rule') return 'Rule Validation'
  if (t === 'policy') return 'Policy / Guardrails'
  if (t === 'svm') return 'Verification (Stages)'
  if (t === 'svm_verification') return 'Verification (Overall)'
  if (t === 'decision') return 'Decision'
  if (t === 'denial') return 'Denial / Refusal'
  return `Other (${t || 'unknown'})`
}

function ExplanationItem({ item }) {
  const [open, setOpen] = useState(false)
  const details = item?.details && typeof item.details === 'object' ? item.details : null
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-xs font-semibold text-slate-700">
          Confidence {formatScore(item?.confidence)}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-slate-500">{String(item?.type || '')}</span>
          {details ? (
            <button
              type="button"
              className="text-[11px] text-sky-700 underline"
              onClick={() => setOpen((v) => !v)}
            >
              {open ? 'Hide details' : 'Show details'}
            </button>
          ) : null}
        </div>
      </div>
      <div className="mt-1 text-sm text-slate-800">
        {String(item?.explanation || '')}
      </div>
      {open && details ? (
        <pre className="mt-2 max-h-48 overflow-auto rounded-lg border border-slate-200 bg-slate-50 p-2 text-[11px] text-slate-700">
          {JSON.stringify(details, null, 2)}
        </pre>
      ) : null}
    </div>
  )
}

function ExplanationList({ items }) {
  const list = Array.isArray(items) ? items : []
  if (!list.length) {
    return <div className="text-xs text-slate-400">No explanations available</div>
  }
  return (
    <div className="space-y-2">
      {list.map((x, i) => <ExplanationItem key={`${x?.type || 'exp'}-${i}`} item={x} />)}
    </div>
  )
}

export default function ClaimExplanationPanel() {
  const [text, setText] = useState('')
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const [auditStatus, setAuditStatus] = useState('idle')
  const [auditError, setAuditError] = useState(null)
  const [audit, setAudit] = useState(null)

  const grouped = useMemo(() => {
    const exps = Array.isArray(result?.explanations) ? result.explanations : []
    const buckets = {}
    for (const x of exps) {
      const t = String(x?.type || '').toLowerCase()
      if (!t) continue
      if (!buckets[t]) buckets[t] = []
      buckets[t].push(x)
    }
    return buckets
  }, [result])

  const otherExplanations = useMemo(() => {
    const exps = Array.isArray(result?.explanations) ? result.explanations : []
    const keep = new Set(['clinical', 'coding', 'rule'])
    return exps.filter((x) => !keep.has(String(x?.type || '').toLowerCase()))
  }, [result])

  const otherByType = useMemo(() => {
    const buckets = {}
    for (const x of otherExplanations) {
      const t = String(x?.type || '').toLowerCase() || 'other'
      if (!buckets[t]) buckets[t] = []
      buckets[t].push(x)
    }
    const order = ['policy', 'svm_verification', 'svm', 'decision', 'denial', 'other']
    const keys = Object.keys(buckets)
    keys.sort((a, b) => {
      const ia = order.indexOf(a)
      const ib = order.indexOf(b)
      if (ia === -1 && ib === -1) return a.localeCompare(b)
      if (ia === -1) return 1
      if (ib === -1) return -1
      return ia - ib
    })
    return { buckets, keys }
  }, [otherExplanations])

  const traceSteps = useMemo(() => {
    const steps = result?.trace?.steps
    return Array.isArray(steps) ? steps : []
  }, [result])

  return (
    <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-base font-semibold text-slate-800">
            Claim Explanation Panel
          </div>
          <p className="text-xs text-slate-500">
            Diagnosis reasoning, code assignment logic, and rule validation explanations.
          </p>
        </div>
        {result?.audit_id ? (
          <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[11px] text-slate-600">
            Audit {String(result.audit_id).slice(0, 8)}
          </span>
        ) : null}
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
          <label className="text-xs font-semibold text-slate-600">
            Clinical text
          </label>
          <textarea
            className="mt-2 w-full rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-800 outline-none focus:ring-2 focus:ring-sky-200"
            rows={6}
            value={text}
            placeholder="Paste clinical note text here…"
            onChange={(e) => setText(e.target.value)}
          />
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button
              type="button"
              className={`btn btnPrimary text-white ${status === 'loading' ? 'opacity-70 pointer-events-none' : ''}`}
              onClick={async () => {
                const payload = (text || '').trim()
                if (!payload) return
                setStatus('loading')
                setError(null)
                setResult(null)
                setAudit(null)
                setAuditError(null)
                setAuditStatus('idle')
                try {
                  const data = await runClaimExplain(payload)
                  setResult(data)
                  setStatus('done')
                } catch (e) {
                  setError(e?.message || 'Request failed')
                  setStatus('error')
                }
              }}
            >
              {status === 'loading' ? 'Explaining…' : 'Explain Claim'}
            </button>
            <button
              type="button"
              className="btn btnGhost"
              onClick={() => {
                setText('')
                setResult(null)
                setError(null)
                setStatus('idle')
                setAudit(null)
                setAuditError(null)
                setAuditStatus('idle')
              }}
            >
              Reset
            </button>
            {result?.audit_id ? (
              <button
                type="button"
                className={`btn btnGhost ${auditStatus === 'loading' ? 'opacity-70 pointer-events-none' : ''}`}
                onClick={async () => {
                  setAuditStatus('loading')
                  setAuditError(null)
                  setAudit(null)
                  try {
                    const data = await getExplainabilityAudit(result.audit_id)
                    setAudit(data)
                    setAuditStatus('done')
                  } catch (e) {
                    setAuditError(e?.message || 'Audit request failed')
                    setAuditStatus('error')
                  }
                }}
              >
                {auditStatus === 'loading' ? 'Loading audit…' : 'Load Audit JSON'}
              </button>
            ) : null}
          </div>
          {error && (
            <div className="mt-3 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700">
              {String(error)}
            </div>
          )}
          {auditError && (
            <div className="mt-3 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700">
              {String(auditError)}
            </div>
          )}
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="text-sm font-semibold text-slate-800">Decision</div>
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold ${decisionColor(
                  result?.decision,
                )}`}
              >
                {result?.decision ? String(result.decision).toUpperCase() : '—'}
              </span>
              <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-700">
                Confidence {formatScore(result?.confidence)}
              </span>
            </div>
          </div>

          <div className="mt-3">
            <div className="text-xs font-bold uppercase tracking-wider text-slate-500">
              Trace
            </div>
            {traceSteps.length ? (
              <div className="mt-2 flex flex-wrap gap-2">
                {traceSteps.slice(0, 8).map((s, i) => (
                  <span
                    key={`${s?.stage || 'step'}-${i}`}
                    className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[11px] text-slate-700"
                    title={String(s?.timestamp || '')}
                  >
                    {String(s?.stage || 'stage')}:{String(s?.status || '—')}
                  </span>
                ))}
              </div>
            ) : (
              <div className="mt-2 text-xs text-slate-400">No trace steps</div>
            )}
          </div>
        </div>
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-3">
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Diagnosis Reasoning
          </div>
          <div className="mt-3">
            <ExplanationList items={grouped.clinical || []} />
          </div>
        </div>

        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Code Assignment Logic
          </div>
          <div className="mt-3">
            <ExplanationList items={grouped.coding || []} />
          </div>
        </div>

        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Rule Validation
          </div>
          <div className="mt-3">
            <ExplanationList items={grouped.rule || []} />
          </div>
        </div>
      </div>

      {otherExplanations.length ? (
        <div className="mt-4 rounded-lg border border-slate-200 bg-white p-4">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Additional Explanation Types
          </div>
          <div className="mt-3 grid gap-3 lg:grid-cols-2">
            {otherByType.keys.map((k) => (
              <div key={k} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                <div className="text-xs font-bold uppercase tracking-wider text-slate-500">
                  {typeTitle(k)}
                </div>
                <div className="mt-3">
                  <ExplanationList items={otherByType.buckets[k]} />
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {audit ? (
        <div className="mt-4 rounded-lg border border-slate-200 bg-white p-3">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Audit JSON
          </div>
          <pre className="mt-2 max-h-72 overflow-auto rounded-lg border border-slate-200 bg-slate-50 p-3 text-[11px] text-slate-700">
            {JSON.stringify(audit, null, 2)}
          </pre>
        </div>
      ) : null}
    </div>
  )
}
