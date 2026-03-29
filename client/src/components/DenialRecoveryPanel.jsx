import { useEffect, useMemo, useState } from 'react'
import { getDenialDashboard, runDenialAgent, startVapiOutboundCall, syncVapiCall } from '../services/api'

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
  const [selectedClaimId, setSelectedClaimId] = useState('')
  const [selectedDenialEventId, setSelectedDenialEventId] = useState(null)
  const [insurerNumber, setInsurerNumber] = useState('')
  const [callState, setCallState] = useState('idle')
  const [callError, setCallError] = useState('')
  const [callInfo, setCallInfo] = useState(null)
  const [syncState, setSyncState] = useState('idle')
  const [syncError, setSyncError] = useState('')
  const [syncInfo, setSyncInfo] = useState(null)
  const [resubmitState, setResubmitState] = useState('idle')
  const [resubmitError, setResubmitError] = useState('')
  const [resubmitInfo, setResubmitInfo] = useState(null)

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
  const needsCallRows = rows.filter((r) => r?.needs_call)
  const solvedRows = rows.filter((r) => String(r?.status || '').toLowerCase() === 'approved')
  const otherRows = rows.filter((r) => !r?.needs_call && String(r?.status || '').toLowerCase() !== 'approved')
  const selectedRow = rows.find((r) => String(r?.claim_id || '') === String(selectedClaimId || '')) || null
  const selectedCall = selectedRow?.call || null

  const startCall = async () => {
    if (!selectedClaimId) {
      setCallError('Select a claim first (click a claim row).')
      return
    }
    const num = String(insurerNumber || '').trim()
    if (!num || !num.startsWith('+')) {
      setCallError('Enter insurer phone number in E.164 format (example: +14155552671).')
      return
    }
    setCallError('')
    setCallInfo(null)
    setSyncError('')
    setSyncInfo(null)
    setResubmitError('')
    setResubmitInfo(null)
    setCallState('starting')
    try {
      const out = await startVapiOutboundCall({
        claimId: selectedClaimId,
        denialEventId: selectedDenialEventId,
        insurerNumber: num,
      })
      setCallInfo(out)
      setCallState('idle')
    } catch (e) {
      setCallState('idle')
      setCallError(e?.message || 'Failed to start call')
    }
  }

  const syncCall = async () => {
    const callId = String(callInfo?.call_id || callInfo?.callId || '').trim()
    if (!callId) {
      setSyncError('No call_id available to sync.')
      return
    }
    setSyncError('')
    setSyncInfo(null)
    setSyncState('syncing')
    try {
      const out = await syncVapiCall({ callId, claimId: selectedClaimId, denialEventId: selectedDenialEventId })
      setSyncInfo(out)
      setSyncState('idle')
      await refresh()
    } catch (e) {
      setSyncState('idle')
      setSyncError(e?.message || 'Sync failed')
    }
  }

  const resubmit = async () => {
    if (!selectedClaimId || !selectedDenialEventId) {
      setResubmitError('Select a claim and denial event first (click a claim row).')
      return
    }
    setResubmitError('')
    setResubmitInfo(null)
    setResubmitState('running')
    try {
      const out = await runDenialAgent({ claimId: selectedClaimId, denialEventId: selectedDenialEventId })
      setResubmitInfo(out)
      setResubmitState('idle')
      await refresh()
    } catch (e) {
      setResubmitState('idle')
      setResubmitError(e?.message || 'Resubmit failed')
    }
  }

  useEffect(() => {
    const callId = String(callInfo?.call_id || callInfo?.callId || '').trim()
    if (!callId) return
    if (!selectedClaimId) return
    let active = true
    let attempts = 0
    const iv = setInterval(async () => {
      if (!active) return
      if (syncState !== 'idle') return
      attempts += 1
      if (attempts > 40) {
        clearInterval(iv)
        return
      }
      try {
        const out = await syncVapiCall({ callId, claimId: selectedClaimId, denialEventId: selectedDenialEventId })
        if (!active) return
        if (out && typeof out === 'object' && out.stored) {
          setSyncInfo(out)
          await refresh()
          clearInterval(iv)
        }
      } catch {
        if (attempts > 8) {
          clearInterval(iv)
        }
      }
    }, 8000)
    return () => {
      active = false
      clearInterval(iv)
    }
  }, [callInfo, selectedClaimId, selectedDenialEventId, syncState])

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

      <div className="mt-4 grid gap-3 md:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-500">Revenue Recovered</div>
          <div className="mt-2 text-2xl font-semibold text-slate-900">{formatInr(metrics.revenue_recovered || 0)}</div>
          <div className="mt-1 text-xs text-slate-500">₹ recovered from previously-denied claims</div>
        </div>
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-500">Denial Reduction</div>
          <div className="mt-2 text-2xl font-semibold text-slate-900">
            {Number(metrics.denial_reduction_percent ?? metrics.recovered_percent ?? 0).toFixed(1)}%
          </div>
          <div className="mt-1 text-xs text-slate-500">
            {Number(metrics.recovered_claims || 0)} recovered · {Number(metrics.denied_claims || 0)} denied
          </div>
        </div>
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-500">Automation</div>
          <div className="mt-2 text-2xl font-semibold text-slate-900">
            {Number(metrics.automation_percent || 0).toFixed(1)}%
          </div>
          <div className="mt-1 text-xs text-slate-500">Denied claims with auto correction/resubmission</div>
        </div>
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-500">Denial Rate</div>
          <div className="mt-2 text-2xl font-semibold text-slate-900">
            {Number(metrics.denial_rate_percent || 0).toFixed(1)}%
          </div>
          <div className="mt-1 text-xs text-slate-500">
            {Number(metrics.denied_claims || 0)} denied · {Number(metrics.total_claims || 0)} total
          </div>
        </div>
      </div>

      <div className="mt-5 rounded-lg border border-slate-200 bg-slate-50 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-sm font-semibold text-slate-800">Automated Call (Vapi)</div>
            <div className="mt-1 text-xs text-slate-500">
              On localhost, webhooks can’t reach your machine. Use “Sync Result” after the call ends, or use a public URL (ngrok) for live webhooks.
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button className="btn btnSecondary" onClick={startCall} disabled={callState !== 'idle'}>
              {callState === 'starting' ? 'Starting…' : 'Call Insurer'}
            </button>
            <button className="btn btnSecondary" onClick={syncCall} disabled={syncState !== 'idle' || !(callInfo?.call_id || callInfo?.callId)}>
              {syncState === 'syncing' ? 'Syncing…' : 'Sync Result'}
            </button>
            <button
              className="btn btnPrimary text-white"
              onClick={resubmit}
              disabled={resubmitState !== 'idle' || !selectedClaimId || !selectedDenialEventId || Boolean(selectedRow?.needs_call)}
            >
              {resubmitState === 'running' ? 'Resubmitting…' : 'Resubmit'}
            </button>
          </div>
        </div>

        <div className="mt-3 grid gap-3 md:grid-cols-2">
          <div className="rounded-lg border border-slate-200 bg-white p-3">
            <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Selected Claim</div>
            <div className="mt-2 text-xs text-slate-700">
              {selectedClaimId ? (
                <div className="font-semibold text-slate-900">{selectedClaimId}</div>
              ) : (
                <div className="text-slate-500">Click a claim row to select it.</div>
              )}
              {selectedDenialEventId ? <div className="mt-1 text-[11px] text-slate-500">Denial event: {String(selectedDenialEventId)}</div> : null}
            </div>
            <div className="mt-3">
              <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Insurer Phone Number</div>
              <input
                className="mt-2 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-slate-400"
                placeholder="+14155552671"
                value={insurerNumber}
                onChange={(e) => setInsurerNumber(e.target.value)}
              />
              <div className="mt-1 text-[11px] text-slate-500">Use E.164 format with +country code.</div>
            </div>
            {callError && <div className="mt-2 rounded-lg border border-red-200 bg-red-50 p-2 text-xs text-red-600">{callError}</div>}
            {syncError && <div className="mt-2 rounded-lg border border-red-200 bg-red-50 p-2 text-xs text-red-600">{syncError}</div>}
            {resubmitError && <div className="mt-2 rounded-lg border border-red-200 bg-red-50 p-2 text-xs text-red-600">{resubmitError}</div>}
          </div>

          <div className="rounded-lg border border-slate-200 bg-white p-3">
            <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Call Result</div>
            {callInfo ? (
              <pre className="mt-2 max-h-56 overflow-auto rounded-lg border border-slate-200 bg-slate-50 p-3 text-[11px] text-slate-700">
                {JSON.stringify(callInfo, null, 2)}
              </pre>
            ) : (
              <div className="mt-2 text-xs text-slate-500">When the call ends, Vapi will POST the end-of-call report to your configured Server URL.</div>
            )}
            {syncInfo && (
              <div className="mt-3">
                <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Sync Result</div>
                <pre className="mt-2 max-h-56 overflow-auto rounded-lg border border-slate-200 bg-slate-50 p-3 text-[11px] text-slate-700">
                  {JSON.stringify(syncInfo, null, 2)}
                </pre>
              </div>
            )}
            {resubmitInfo && (
              <div className="mt-3">
                <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Resubmit Result</div>
                <pre className="mt-2 max-h-56 overflow-auto rounded-lg border border-slate-200 bg-slate-50 p-3 text-[11px] text-slate-700">
                  {JSON.stringify(resubmitInfo, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </div>

        {selectedClaimId ? (
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <div className="rounded-lg border border-slate-200 bg-white p-3">
              <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Call Summary</div>
              <div className="mt-2 text-xs text-slate-700">
                {selectedCall?.summary ? String(selectedCall.summary) : <span className="text-slate-500">No call summary yet.</span>}
              </div>
              {selectedCall?.status ? <div className="mt-2 text-[11px] text-slate-500">Call status: {String(selectedCall.status)}</div> : null}
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-3">
              <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Transcript</div>
              {selectedCall?.transcript ? (
                <pre className="mt-2 max-h-56 overflow-auto rounded-lg border border-slate-200 bg-slate-50 p-3 text-[11px] text-slate-700">
                  {String(selectedCall.transcript)}
                </pre>
              ) : (
                <div className="mt-2 text-xs text-slate-500">No transcript yet.</div>
              )}
            </div>
          </div>
        ) : null}
      </div>

      <div className="mt-5 space-y-3">
        {[
          { key: 'needs_call', title: 'Needs Call', subtitle: 'Denials missing details (call insurer)', items: needsCallRows },
          { key: 'active', title: 'In Progress', subtitle: 'Denied / resubmitting', items: otherRows },
          { key: 'solved', title: 'Solved', subtitle: 'Recovered (approved)', items: solvedRows },
        ]
          .filter((s) => (s.key === 'solved' ? (Array.isArray(s.items) ? s.items.length > 0 : false) : true))
          .map((section) => {
          const list = Array.isArray(section.items) ? section.items : []
          return (
            <div key={section.key} className="overflow-hidden rounded-lg border border-slate-200">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-slate-50 px-4 py-3">
                <div>
                  <div className="text-sm font-semibold text-slate-800">
                    {section.title} <span className="text-slate-500">({list.length})</span>
                  </div>
                  <div className="mt-1 text-xs text-slate-500">{section.subtitle}</div>
                </div>
              </div>

              <div className="grid grid-cols-12 gap-2 border-b border-slate-200 bg-white px-4 py-2 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                <div className="col-span-3">Claim</div>
                <div className="col-span-2">Status</div>
                <div className="col-span-2">Progress</div>
                <div className="col-span-2 text-right">Amount</div>
                <div className="col-span-3">Timeline</div>
              </div>

              {state === 'loading' && (
                <div className="px-4 py-4 text-xs text-slate-500">Loading denial dashboard…</div>
              )}

              {state !== 'loading' && list.length === 0 && (
                <div className="px-4 py-4 text-xs text-slate-500">No claims in this section.</div>
              )}

              {list.map((r) => {
          const claimId = String(r?.claim_id || '')
          const isOpen = Boolean(expanded[claimId])
          const denialTypes = Array.isArray(r?.denial_types) ? r.denial_types : []
          const progress = r?.progress || {}
          const percent = Number(progress?.percent || 0)

          return (
            <div key={claimId} className="border-b border-slate-200 last:border-b-0">
              <button
                className="w-full text-left px-4 py-3 hover:bg-slate-50 transition-colors"
                onClick={() => {
                  setSelectedClaimId(claimId)
                  setSelectedDenialEventId(r?.last_denial_event_id ?? null)
                  setExpanded((p) => ({ ...p, [claimId]: !p[claimId] }))
                }}
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
          )
        })}
      </div>
    </div>
  )
}
