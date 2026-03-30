import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { PhoneCall, Radio, RefreshCcw } from 'lucide-react'

import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card'
import { Skeleton } from '../components/ui/skeleton'
import { cn } from '../lib/cn'
import { getDenialDashboard } from '../services/api'

function PageTitle() {
  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-[-0.03em] text-slate-900 md:text-3xl">Voice agent</h1>
      <p className="mt-1 max-w-3xl text-sm text-slate-600">
        Call history, transcripts, structured outputs, and a live call status panel designed for enterprise operations.
      </p>
    </div>
  )
}

function liveTone(status) {
  const s = String(status || '').toLowerCase()
  if (s.includes('active') || s.includes('in_progress') || s.includes('connected')) return { badge: 'success', dot: 'from-emerald-400 to-cyan-400' }
  if (s.includes('failed') || s.includes('error')) return { badge: 'error', dot: 'from-rose-500 to-fuchsia-500' }
  return { badge: 'info', dot: 'from-blue-500 to-violet-500' }
}

function WaveBars({ running }) {
  const bars = [12, 18, 10, 22, 14, 20, 12]
  const MotionDiv = motion.div
  return (
    <div className="flex items-end gap-1">
      {bars.map((h, i) => (
        <MotionDiv
          key={i}
          className="w-1.5 rounded-full bg-gradient-to-t from-blue-500 via-violet-500 to-cyan-400"
          style={{ height: h }}
          animate={running ? { scaleY: [0.4, 1, 0.55, 0.9] } : { scaleY: 0.25 }}
          transition={running ? { duration: 1.2, repeat: Infinity, ease: 'easeInOut', delay: i * 0.05 } : { duration: 0.2 }}
        />
      ))}
    </div>
  )
}

export default function VoiceAgent() {
  const [state, setState] = useState({ loading: true, error: '', calls: [] })
  const [selected, setSelected] = useState(null)

  const load = async () => {
    setState((s) => ({ ...s, loading: true, error: '' }))
    try {
      const d = await getDenialDashboard()
      const denied = Array.isArray(d?.denied_claims) ? d.denied_claims : []
      const calls = denied
        .map((r) => {
          const c = r?.call && typeof r.call === 'object' ? r.call : null
          if (!c) return null
          return {
            id: c.call_id || c.callId || `${r?.claim_id || ''}-${Math.random()}`,
            claimId: r?.claim_id || '',
            status: c.status || c.call_status || 'stored',
            startedAt: c.started_at || c.created_at || c.timestamp || '',
            transcript: c.transcript || c.summary || '',
            structured: c.structured_output || c.output || c.extracted || null,
          }
        })
        .filter(Boolean)
      setState({ loading: false, error: '', calls })
      if (!selected && calls.length) setSelected(calls[0])
    } catch (e) {
      setState({ loading: false, error: e?.message || 'Failed to load calls', calls: [] })
    }
  }

  useEffect(() => {
    let active = true
    ;(async () => {
      try {
        const d = await getDenialDashboard()
        if (!active) return
        const denied = Array.isArray(d?.denied_claims) ? d.denied_claims : []
        const calls = denied
          .map((r) => {
            const c = r?.call && typeof r.call === 'object' ? r.call : null
            if (!c) return null
            return {
              id: c.call_id || c.callId || `${r?.claim_id || ''}-${Math.random()}`,
              claimId: r?.claim_id || '',
              status: c.status || c.call_status || 'stored',
              startedAt: c.started_at || c.created_at || c.timestamp || '',
              transcript: c.transcript || c.summary || '',
              structured: c.structured_output || c.output || c.extracted || null,
            }
          })
          .filter(Boolean)
        setState({ loading: false, error: '', calls })
        setSelected((prev) => prev || calls[0] || null)
      } catch (e) {
        if (!active) return
        setState({ loading: false, error: e?.message || 'Failed to load calls', calls: [] })
      }
    })()
    return () => {
      active = false
    }
  }, [])

  const demoLive = useMemo(() => {
    return {
      status: 'active',
      counterparty: 'Payer IVR • BlueShield',
      intent: 'Denial appeal + claim status',
      callId: selected?.id || 'call_demo_102',
    }
  }, [selected])

  const tone = liveTone(demoLive.status)

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <PageTitle />
        <Button variant="outline" onClick={load} disabled={state.loading}>
          <RefreshCcw className="size-4" />
          Refresh
        </Button>
      </div>

      {state.error ? (
        <div className="glass-panel rounded-[28px] border border-rose-200/60 bg-rose-50/60 p-5 text-sm text-rose-700">
          {state.error}
        </div>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-5">
        <div className="xl:col-span-2">
          <Card variant="glass">
            <CardHeader>
              <div>
                <CardTitle>Call history</CardTitle>
                <CardDescription>Most recent denial-related calls.</CardDescription>
              </div>
              <Badge variant="info" className="bg-white/70">
                {state.loading ? 'Loading' : `${state.calls.length} calls`}
              </Badge>
            </CardHeader>
            <CardContent>
              {state.loading ? (
                <div className="space-y-2">
                  {Array.from({ length: 8 }).map((_, i) => (
                    <Skeleton key={i} className="h-12 w-full rounded-2xl" />
                  ))}
                </div>
              ) : state.calls.length ? (
                <div className="space-y-2">
                  {state.calls.slice(0, 12).map((c) => {
                    const active = selected?.id && String(selected.id) === String(c.id)
                    const t = liveTone(c.status)
                    return (
                      <button
                        key={c.id}
                        onClick={() => setSelected(c)}
                        className={cn(
                          'w-full rounded-2xl border border-white/70 bg-white/55 p-3 text-left shadow-[0_12px_40px_rgba(2,6,23,0.08)] outline-none transition hover:bg-white/75 focus-visible:ring-4 focus-visible:ring-[var(--ring)]',
                          active && 'bg-gradient-to-br from-blue-50/80 via-white/70 to-cyan-50/70',
                        )}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="truncate text-sm font-semibold text-slate-900">{String(c.claimId || 'Claim')}</div>
                            <div className="mt-1 truncate text-xs text-slate-600">{String(c.startedAt || '—')}</div>
                          </div>
                          <Badge variant={t.badge}>{String(c.status || 'stored')}</Badge>
                        </div>
                        <div className="mt-3 flex items-center gap-2">
                          <div className={cn('size-2.5 rounded-full bg-gradient-to-br', t.dot)} />
                          <div className="truncate text-xs text-slate-600">{String(c.id)}</div>
                        </div>
                      </button>
                    )
                  })}
                </div>
              ) : (
                <div className="rounded-[26px] border border-white/70 bg-white/55 p-5 text-sm text-slate-600">
                  No calls available yet. Start a denial workflow to generate call artifacts.
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="xl:col-span-3 space-y-4">
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Live call status</CardTitle>
                <CardDescription>Operator-grade visibility for active sessions.</CardDescription>
              </div>
              <Badge variant={tone.badge} className="bg-white/70">
                {demoLive.status}
              </Badge>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-[28px] border border-white/70 bg-white/55 p-5 shadow-[0_18px_60px_rgba(2,6,23,0.10)]">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <div className="grid size-11 place-items-center rounded-2xl bg-gradient-to-br from-blue-500/20 via-violet-500/15 to-cyan-400/20">
                        <PhoneCall className="size-5 text-slate-900/80" />
                      </div>
                      <div>
                        <div className="text-sm font-semibold text-slate-900">{demoLive.counterparty}</div>
                        <div className="mt-1 text-xs text-slate-600">{demoLive.intent}</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Radio className="size-4 text-rose-500" />
                      <div className="text-xs font-semibold text-slate-800">LIVE</div>
                    </div>
                  </div>
                  <div className="mt-5 flex items-center justify-between gap-4">
                    <WaveBars running />
                    <div className="text-right">
                      <div className="text-xs text-slate-600">Call ID</div>
                      <div className="mt-1 text-xs font-semibold text-slate-900">{demoLive.callId}</div>
                    </div>
                  </div>
                </div>

                <div className="rounded-[28px] border border-white/70 bg-white/55 p-5 shadow-[0_18px_60px_rgba(2,6,23,0.10)]">
                  <div className="text-sm font-semibold text-slate-900">Structured output</div>
                  <div className="mt-1 text-xs text-slate-600">Key-value fields extracted from the call.</div>
                  <div className="mt-4 grid gap-2">
                    {[
                      { k: 'Denial code', v: 'CO-16' },
                      { k: 'Payer representative', v: 'Agent #3182' },
                      { k: 'Next step', v: 'Submit corrected documentation' },
                      { k: 'Follow-up window', v: '48 hours' },
                    ].map((r) => (
                      <div key={r.k} className="flex items-center justify-between gap-3 rounded-2xl border border-white/70 bg-white/60 px-3 py-2">
                        <div className="text-xs font-semibold text-slate-700">{r.k}</div>
                        <div className="text-xs font-semibold text-slate-900">{r.v}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card variant="glass">
            <CardHeader>
              <div>
                <CardTitle>Transcript</CardTitle>
                <CardDescription>Searchable, auditable transcript with operator-friendly density.</CardDescription>
              </div>
              <Badge variant="neutral" className="bg-white/70">
                {selected ? 'Selected call' : 'Demo'}
              </Badge>
            </CardHeader>
            <CardContent>
              <div className="rounded-[28px] border border-white/70 bg-white/55 p-5 shadow-[0_18px_60px_rgba(2,6,23,0.10)]">
                <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Transcript</div>
                <div className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-slate-800">
                  {selected?.transcript ||
                    'Agent: Hi, this is MedLedger AI calling about claim A-10293.\nPayer: Please provide the denial reason.\nAgent: The denial indicates missing information (CO-16). We can submit the corrected documentation.\nPayer: Great. Please re-submit through the portal and include the itemized bill.\nAgent: Confirmed. Thank you.'}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
