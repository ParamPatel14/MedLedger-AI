import { useEffect, useMemo, useState } from 'react'
import { TrendingUp, ShieldOff, Zap, AlertTriangle, Phone, RefreshCw, Send } from 'lucide-react'
import { getDenialDashboard, runDenialAgent, startVapiOutboundCall, syncVapiCall } from '../services/api'
import { Button } from './ui/button'

function pillClass(status) {
  const s = String(status || '').toLowerCase()
  if (s === 'approved') return 'statusBadge approved'
  if (s === 'resubmitted') return 'statusBadge resubmitted'
  if (s === 'denied') return 'statusBadge denied'
  if (s === 'query') return 'statusBadge query'
  return 'statusBadge default'
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
    <div>
      {/* ── Top action bar ── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div>
          <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Live claim recovery tracking and business impact metrics.</div>
        </div>
        <Button variant="outline" size="sm" onClick={refresh} disabled={state === 'loading'}>
          <RefreshCw size={13} />
          {state === 'loading' ? 'Loading…' : 'Refresh'}
        </Button>
      </div>

      {/* ── KPI Cards ── */}
      <div className="kpiGrid">
        <div className="kpiCard green">
          <div className="kpiCardTop">
            <span className="kpiCardLabel">Revenue Recovered</span>
            <div className="kpiCardIconWrap"><TrendingUp size={15} strokeWidth={2.5} /></div>
          </div>
          <div className="kpiCardValue">{formatInr(metrics.revenue_recovered || 0)}</div>
          <div className="kpiCardSub">₹ recovered from previously-denied claims</div>
        </div>
        <div className="kpiCard blue">
          <div className="kpiCardTop">
            <span className="kpiCardLabel">Denial Reduction</span>
            <div className="kpiCardIconWrap"><ShieldOff size={15} strokeWidth={2.5} /></div>
          </div>
          <div className="kpiCardValue">{Number(metrics.denial_reduction_percent ?? metrics.recovered_percent ?? 0).toFixed(1)}%</div>
          <div className="kpiCardSub">{Number(metrics.recovered_claims || 0)} recovered · {Number(metrics.denied_claims || 0)} denied</div>
        </div>
        <div className="kpiCard teal">
          <div className="kpiCardTop">
            <span className="kpiCardLabel">Automation Rate</span>
            <div className="kpiCardIconWrap"><Zap size={15} strokeWidth={2.5} /></div>
          </div>
          <div className="kpiCardValue">{Number(metrics.automation_percent || 0).toFixed(1)}%</div>
          <div className="kpiCardSub">Denied claims with auto correction or resubmission</div>
        </div>
        <div className="kpiCard amber">
          <div className="kpiCardTop">
            <span className="kpiCardLabel">Denial Rate</span>
            <div className="kpiCardIconWrap"><AlertTriangle size={15} strokeWidth={2.5} /></div>
          </div>
          <div className="kpiCardValue">{Number(metrics.denial_rate_percent || 0).toFixed(1)}%</div>
          <div className="kpiCardSub">{Number(metrics.denied_claims || 0)} denied · {Number(metrics.total_claims || 0)} total</div>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-600">{error}</div>
      )}

      <div className="panel" style={{ marginBottom: 20 }}>
        <div className="panelHead">
          <div>
            <div className="panelHeadTitle">Automated Call (Vapi)</div>
            <div className="panelHeadSub">On localhost, webhooks can't reach your machine. Use "Sync Result" after the call ends.</div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Button variant="outline" size="sm" onClick={startCall} disabled={callState !== 'idle'}>
              <Phone size={13} />
              {callState === 'starting' ? 'Starting…' : 'Call Insurer'}
            </Button>
            <Button variant="outline" size="sm" onClick={syncCall} disabled={syncState !== 'idle' || !(callInfo?.call_id || callInfo?.callId)}>
              <RefreshCw size={13} />
              {syncState === 'syncing' ? 'Syncing…' : 'Sync Result'}
            </Button>
            <Button
              size="sm"
              onClick={resubmit}
              disabled={resubmitState !== 'idle' || !selectedClaimId || !selectedDenialEventId || Boolean(selectedRow?.needs_call)}
            >
              <Send size={13} />
              {resubmitState === 'running' ? 'Resubmitting…' : 'Resubmit'}
            </Button>
          </div>
        </div>
        <div className="panelBody">

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
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {[
          { key: 'needs_call', title: 'Needs Call', subtitle: 'Denials missing details — call insurer to proceed', items: needsCallRows },
          { key: 'active', title: 'In Progress', subtitle: 'Denied / currently resubmitting', items: otherRows },
          { key: 'solved', title: 'Recovered', subtitle: 'Successfully approved after resubmission', items: solvedRows },
        ]
          .filter((s) => (s.key === 'solved' ? (Array.isArray(s.items) ? s.items.length > 0 : false) : true))
          .map((section) => {
          const list = Array.isArray(section.items) ? section.items : []
          return (
            <div key={section.key} className="panel">
              <div className="panelHead">
                <div>
                  <div className="panelHeadTitle">
                    {section.title}
                    <span style={{ fontWeight: 500, color: 'var(--text-muted)', marginLeft: 6 }}>({list.length})</span>
                  </div>
                  <div className="panelHeadSub">{section.subtitle}</div>
                </div>
              </div>

              <div style={{ overflowX: 'auto' }}>
              <table className="dataTable" style={{ minWidth: 680 }}>
                <thead>
                  <tr>
                    <th style={{ width: '22%' }}>Claim</th>
                    <th style={{ width: '14%' }}>Status</th>
                    <th style={{ width: '16%' }}>Progress</th>
                    <th style={{ width: '13%', textAlign: 'right' }}>Amount</th>
                    <th>Timeline</th>
                  </tr>
                </thead>
                <tbody>
                  {state === 'loading' && (
                    <tr><td colSpan={5} style={{ color: 'var(--text-muted)', padding: '16px 14px', fontSize: 13 }}>Loading…</td></tr>
                  )}
                  {state !== 'loading' && list.length === 0 && (
                    <tr><td colSpan={5} style={{ color: 'var(--text-muted)', padding: '16px 14px', fontSize: 13 }}>No claims in this section.</td></tr>
                  )}
                  {list.map((r) => {
                    const claimId = String(r?.claim_id || '')
                    const isSelected = claimId === selectedClaimId
                    const isOpen = Boolean(expanded[claimId])
                    const denialTypes = Array.isArray(r?.denial_types) ? r.denial_types : []
                    const progress = r?.progress || {}
                    const percent = Number(progress?.percent || 0)
                    return (
                      <>
                        <tr
                          key={claimId}
                          className={isSelected ? 'selected' : ''}
                          style={{ cursor: 'pointer' }}
                          onClick={() => {
                            setSelectedClaimId(claimId)
                            setSelectedDenialEventId(r?.last_denial_event_id ?? null)
                            setExpanded((p) => ({ ...p, [claimId]: !p[claimId] }))
                          }}
                        >
                          <td>
                            <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--text-strong)', fontFamily: 'var(--font-mono)' }}>{claimId.slice(0, 8)}</div>
                            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                              D:{Number(r?.denials_count || 0)} · C:{Number(r?.corrections_count || 0)} · R:{Number(r?.resubmissions_count || 0)}
                            </div>
                            {denialTypes.length > 0 && (
                              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{denialTypes.join(', ')}</div>
                            )}
                          </td>
                          <td>
                            <span className={pillClass(r?.status)}>{String(r?.status || '—')}</span>
                            {r?.updated_at && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3 }}>{String(r.updated_at)}</div>}
                          </td>
                          <td>
                            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-strong)', marginBottom: 5 }}>{stageLabel(progress?.stage)}</div>
                            <div className="progressBar"><div className="progressBarFill" style={{ width: `${Math.max(0, Math.min(100, percent))}%` }} /></div>
                            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3 }}>{percent}%</div>
                          </td>
                          <td style={{ textAlign: 'right' }}>
                            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-strong)' }}>{formatInr(r?.amount)}</div>
                            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>conf: {Number(r?.last_confidence || 0).toFixed(2)}</div>
                          </td>
                          <td><Timeline items={r?.timeline} /></td>
                        </tr>
                        {isOpen && (
                          <tr key={`${claimId}-detail`}>
                            <td colSpan={5} style={{ background: 'var(--surface-2)', padding: '12px 14px' }}>
                              <div style={{ marginBottom: 8, fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-muted)' }}>Claim Detail</div>
                              <Timeline items={r?.timeline} />
                              <pre style={{ marginTop: 10, fontSize: 11, background: 'white', border: '1px solid var(--border)', borderRadius: 6, padding: '10px 12px', overflowX: 'auto', maxHeight: 200, color: 'var(--text)' }}>
                                {JSON.stringify({ claim_id: r?.claim_id, status: r?.status, denial_types: r?.denial_types, progress: r?.progress, last_denial_event_id: r?.last_denial_event_id }, null, 2)}
                              </pre>
                            </td>
                          </tr>
                        )}
                      </>
                    )
                  })}
                </tbody>
              </table>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
