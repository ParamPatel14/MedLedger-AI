import { useEffect, useMemo, useState } from 'react'
import { getDenialDashboard } from '../services/api'

function pillClass(status) {
  const s = String(status || '').toLowerCase()
  if (s === 'approved') return 'bg-emerald-50 text-emerald-700 border-emerald-200'
  if (s === 'resubmitted') return 'bg-sky-50 text-sky-700 border-sky-200'
  if (s === 'denied') return 'bg-rose-50 text-rose-700 border-rose-200'
  if (s === 'query') return 'bg-amber-50 text-amber-800 border-amber-200'
  return 'bg-slate-50 text-slate-700 border-slate-200'
}

function stageLabel(stage) {
  const s = String(stage || '').toLowerCase()
  if (s === 'submitted') return 'Submitted'
  if (s === 'denied') return 'Denied'
  if (s === 'fixed') return 'Fixed'
  if (s === 'resubmitted') return 'Resubmitted'
  if (s === 'approved') return 'Approved'
  return '—'
}

function formatInr(amount) {
  const n = Number(amount)
  if (!Number.isFinite(n)) return '—'
  try {
    return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(n)
  } catch {
    return `₹${Math.round(n)}`
  }
}

function Timeline({ items }) {
  const steps = useMemo(() => {
    const order = ['submitted', 'denied', 'fixed', 'resubmitted', 'approved']
    const byStep = new Map()
    for (const it of Array.isArray(items) ? items : []) {
      const step = String(it?.step || '').toLowerCase()
      if (!step) continue
      if (!byStep.has(step)) byStep.set(step, it)
    }
    return order.map((k) => ({ key: k, item: byStep.get(k) }))
  }, [items])

  return (
    <div className="flex flex-wrap items-center gap-2">
      {steps.map((s, idx) => {
        const done = Boolean(s.item)
        const cls = done ? 'bg-slate-900 text-white border-slate-900' : 'bg-white text-slate-400 border-slate-200'
        return (
          <div key={s.key} className="flex items-center gap-2">
            <div className={`rounded-full border px-2 py-1 text-[11px] font-semibold ${cls}`}>{stageLabel(s.key)}</div>
            {idx < steps.length - 1 && <div className="h-px w-5 bg-slate-200" aria-hidden="true"></div>}
          </div>
        )
      })}
    </div>
  )
}

export default function DenialRecoveryPanel() {
  const [state, setState] = useState('idle')
  const [error, setError] = useState('')
  const [data, setData] = useState(null)
  const [expanded, setExpanded] = useState({})

  useEffect(() => {
    let active = true
    setState('loading')
    setError('')
    ;(async () => {
      try {
        const d = await getDenialDashboard()
        if (!active) return
        setData(d)
        setState('ok')
      } catch (e) {
        if (!active) return
        setState('error')
        setError(e?.message || 'Failed to load denial dashboard')
      }
    })()
    return () => {
      active = false
    }
  }, [])

  const refresh = async () => {
    setState('loading')
    setError('')
    try {
      const d = await getDenialDashboard()
      setData(d)
      setState('ok')
    } catch (e) {
      setState('error')
      setError(e?.message || 'Failed to load denial dashboard')
    }
  }

  const metrics = data?.metrics || {}
  const rows = Array.isArray(data?.denied_claims) ? data.denied_claims : []

  return (
    <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-base font-semibold text-slate-800">Denial Recovery Panel</div>
          <div className="mt-1 text-xs text-slate-500">Track denied claims, recovery progress, and outcomes.</div>
        </div>
        <button className="btn btnSecondary" onClick={refresh} disabled={state === 'loading'}>
          Refresh
        </button>
      </div>

      {error && (
        <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-600">{error}</div>
      )}

      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-500">Recovered Claims</div>
          <div className="mt-2 text-2xl font-semibold text-slate-900">{Number(metrics.recovered_claims || 0)}</div>
          <div className="mt-1 text-xs text-slate-500">
            {Number(metrics.denied_claims || 0)} denied · {Number(metrics.recovered_percent || 0).toFixed(1)}% recovered
          </div>
        </div>
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-500">Revenue Recovered</div>
          <div className="mt-2 text-2xl font-semibold text-slate-900">{formatInr(metrics.revenue_recovered || 0)}</div>
          <div className="mt-1 text-xs text-slate-500">Sum of approved previously-denied claims</div>
        </div>
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-500">Denied Claims</div>
          <div className="mt-2 text-2xl font-semibold text-slate-900">{Number(metrics.denied_claims || 0)}</div>
          <div className="mt-1 text-xs text-slate-500">{Number(metrics.total_claims || 0)} total claims tracked</div>
        </div>
      </div>

      <div className="mt-5 overflow-hidden rounded-lg border border-slate-200">
        <div className="grid grid-cols-12 gap-2 border-b border-slate-200 bg-slate-50 px-4 py-2 text-[11px] font-bold uppercase tracking-wider text-slate-500">
          <div className="col-span-3">Claim</div>
          <div className="col-span-2">Status</div>
          <div className="col-span-2">Progress</div>
          <div className="col-span-2 text-right">Amount</div>
          <div className="col-span-3">Timeline</div>
        </div>

        {state === 'loading' && (
          <div className="px-4 py-4 text-xs text-slate-500">Loading denial dashboard…</div>
        )}

        {state !== 'loading' && rows.length === 0 && (
          <div className="px-4 py-4 text-xs text-slate-500">No denied claims found.</div>
        )}

        {rows.map((r) => {
          const claimId = String(r?.claim_id || '')
          const isOpen = Boolean(expanded[claimId])
          const denialTypes = Array.isArray(r?.denial_types) ? r.denial_types : []
          const progress = r?.progress || {}
          const percent = Number(progress?.percent || 0)

          return (
            <div key={claimId} className="border-b border-slate-200 last:border-b-0">
              <button
                className="w-full text-left px-4 py-3 hover:bg-slate-50 transition-colors"
                onClick={() => setExpanded((p) => ({ ...p, [claimId]: !p[claimId] }))}
              >
                <div className="grid grid-cols-12 items-center gap-2">
                  <div className="col-span-3">
                    <div className="text-sm font-semibold text-slate-900">{claimId.slice(0, 8)}</div>
                    <div className="mt-0.5 text-xs text-slate-500">
                      Denials: {Number(r?.denials_count || 0)} · Corrections: {Number(r?.corrections_count || 0)} · Resub: {Number(r?.resubmissions_count || 0)}
                    </div>
                    {denialTypes.length > 0 && (
                      <div className="mt-1 text-[11px] text-slate-500">{denialTypes.join(', ')}</div>
                    )}
                  </div>

                  <div className="col-span-2">
                    <div className={`inline-flex items-center rounded-full border px-2 py-1 text-xs font-semibold ${pillClass(r?.status)}`}>
                      {String(r?.status || '—')}
                    </div>
                    <div className="mt-1 text-[11px] text-slate-500">{r?.updated_at ? String(r.updated_at) : ''}</div>
                  </div>

                  <div className="col-span-2">
                    <div className="text-xs font-semibold text-slate-700">{stageLabel(progress?.stage)}</div>
                    <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-slate-100">
                      <div className="h-2 rounded-full bg-slate-900" style={{ width: `${Math.max(0, Math.min(100, percent))}%` }} />
                    </div>
                    <div className="mt-1 text-[11px] text-slate-500">{percent}%</div>
                  </div>

                  <div className="col-span-2 text-right">
                    <div className="text-sm font-semibold text-slate-900">{formatInr(r?.amount)}</div>
                    <div className="mt-0.5 text-[11px] text-slate-500">Last conf: {Number(r?.last_confidence || 0).toFixed(2)}</div>
                  </div>

                  <div className="col-span-3">
                    <Timeline items={r?.timeline} />
                  </div>
                </div>
              </button>

              {isOpen && (
                <div className="px-4 pb-4">
                  <div className="rounded-lg border border-slate-200 bg-white p-3">
                    <div className="text-xs font-bold uppercase tracking-wider text-slate-500">Claim Timeline</div>
                    <div className="mt-2">
                      <Timeline items={r?.timeline} />
                    </div>
                    <pre className="mt-3 max-h-56 overflow-auto rounded-lg border border-slate-200 bg-slate-50 p-3 text-[11px] text-slate-700">
                      {JSON.stringify(
                        {
                          claim_id: r?.claim_id,
                          status: r?.status,
                          denial_types: r?.denial_types,
                          progress: r?.progress,
                          last_denial_event_id: r?.last_denial_event_id,
                          last_correction_id: r?.last_correction_id,
                          last_resubmission_id: r?.last_resubmission_id,
                        },
                        null,
                        2,
                      )}
                    </pre>
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
