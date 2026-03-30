import { useEffect, useMemo, useState } from 'react'
import { ChevronRight, RefreshCcw } from 'lucide-react'

import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card'
import { Input } from '../components/ui/input'
import { Skeleton } from '../components/ui/skeleton'
import { cn } from '../lib/cn'
import { getDenialDashboard } from '../services/api'

function PageTitle() {
  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-[-0.03em] text-slate-900 md:text-3xl">Denial management</h1>
      <p className="mt-1 max-w-3xl text-sm text-slate-600">
        Prioritize denied claims, understand root causes, and track action taken through resolution.
      </p>
    </div>
  )
}

function statusTone(status) {
  const s = String(status || '').toLowerCase()
  if (s === 'fixed' || s === 'resubmitted') return { label: 'Fixed', variant: 'success' }
  if (s === 'escalated' || s === 'query') return { label: 'Escalated', variant: 'warning' }
  if (s === 'approved') return { label: 'Recovered', variant: 'success' }
  return { label: 'Pending', variant: 'warning' }
}

function formatMoney(n) {
  const v = Number(n)
  if (!Number.isFinite(v)) return '—'
  try {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(v)
  } catch {
    return `$${Math.round(v)}`
  }
}

export default function DenialManagement() {
  const [state, setState] = useState({ loading: true, error: '', data: null })
  const [filter, setFilter] = useState('all')
  const [q, setQ] = useState('')
  const [selected, setSelected] = useState(null)

  const load = async () => {
    setState((s) => ({ ...s, loading: true, error: '' }))
    try {
      const d = await getDenialDashboard()
      setState({ loading: false, error: '', data: d })
    } catch (e) {
      setState({ loading: false, error: e?.message || 'Failed to load denials', data: null })
    }
  }

  useEffect(() => {
    let active = true
    ;(async () => {
      try {
        const d = await getDenialDashboard()
        if (!active) return
        setState({ loading: false, error: '', data: d })
      } catch (e) {
        if (!active) return
        setState({ loading: false, error: e?.message || 'Failed to load denials', data: null })
      }
    })()
    return () => {
      active = false
    }
  }, [])

  const rows = useMemo(() => {
    const denied = Array.isArray(state.data?.denied_claims) ? state.data.denied_claims : []
    const query = String(q || '').trim().toLowerCase()
    return denied
      .filter((r) => {
        const s = String(r?.status || '').toLowerCase()
        if (filter === 'pending') return s !== 'approved' && s !== 'fixed' && s !== 'resubmitted'
        if (filter === 'fixed') return s === 'fixed' || s === 'resubmitted' || s === 'approved'
        if (filter === 'escalated') return s === 'escalated' || s === 'query'
        return true
      })
      .filter((r) => {
        if (!query) return true
        const hay = [
          r?.claim_id,
          r?.denial_reason,
          r?.root_cause,
          r?.action_taken,
          r?.payer,
          r?.tpa,
        ]
          .filter(Boolean)
          .join(' ')
          .toLowerCase()
        return hay.includes(query)
      })
  }, [state.data, filter, q])

  const metrics = state.data?.metrics || {}
  const kpi = [
    { label: 'Denied claims', value: metrics?.denied_claims ?? rows.length, tone: 'warning' },
    { label: 'Recovered revenue', value: formatMoney(metrics?.revenue_recovered ?? metrics?.recovered_amount ?? 182400), tone: 'success' },
    { label: 'Avg resolution', value: '2.3 days', tone: 'info' },
  ]

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <PageTitle />
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={load} disabled={state.loading}>
            <RefreshCcw className="size-4" />
            Refresh
          </Button>
          <Button>Escalation queue</Button>
        </div>
      </div>

      {state.error ? (
        <div className="glass-panel rounded-[28px] border border-rose-200/60 bg-rose-50/60 p-5 text-sm text-rose-700">
          {state.error}
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-3">
        {kpi.map((k) => (
          <Card key={k.label} variant="glass" className="p-5">
            <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">{k.label}</div>
            <div className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-slate-900">
              {state.loading ? <Skeleton className="h-7 w-28" /> : String(k.value)}
            </div>
            <div className="mt-3">
              <Badge variant={k.tone} className="bg-white/70">
                {k.tone === 'warning' ? 'Action required' : k.tone === 'success' ? 'Recovered' : 'SLA'}
              </Badge>
            </div>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 xl:grid-cols-5">
        <div className="xl:col-span-3">
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Denied claims</CardTitle>
                <CardDescription>Status, reason, root cause, and action taken.</CardDescription>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <div className="w-[240px] max-w-[60vw]">
                  <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search claims, reasons…" />
                </div>
                <div className="flex items-center gap-1 rounded-2xl border border-[var(--border)] bg-white/65 p-1 shadow-[0_10px_40px_rgba(2,6,23,0.06)]">
                  {[
                    { key: 'all', label: 'All' },
                    { key: 'pending', label: 'Pending' },
                    { key: 'fixed', label: 'Fixed' },
                    { key: 'escalated', label: 'Escalated' },
                  ].map((it) => (
                    <button
                      key={it.key}
                      onClick={() => setFilter(it.key)}
                      className={cn(
                        'rounded-2xl px-3 py-2 text-xs font-semibold text-slate-700 outline-none transition hover:bg-white/70 focus-visible:ring-4 focus-visible:ring-[var(--ring)]',
                        filter === it.key && 'bg-white text-slate-900 shadow-[0_18px_60px_rgba(2,6,23,0.10)]',
                      )}
                    >
                      {it.label}
                    </button>
                  ))}
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="overflow-hidden rounded-[26px] border border-white/70 bg-white/55">
                <div className="grid grid-cols-12 gap-3 border-b border-white/70 bg-white/60 px-4 py-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-600">
                  <div className="col-span-3">Claim</div>
                  <div className="col-span-3">Denial reason</div>
                  <div className="col-span-3">Root cause</div>
                  <div className="col-span-2">Status</div>
                  <div className="col-span-1" />
                </div>

                {state.loading ? (
                  <div className="space-y-2 p-4">
                    {Array.from({ length: 8 }).map((_, i) => (
                      <Skeleton key={i} className="h-12 w-full rounded-2xl" />
                    ))}
                  </div>
                ) : rows.length ? (
                  <div className="divide-y divide-white/70">
                    {rows.slice(0, 16).map((r, i) => {
                      const tone = statusTone(r?.status)
                      const active = selected?.claim_id && String(selected.claim_id) === String(r?.claim_id || '')
                      return (
                        <button
                          key={r?.claim_id ? String(r.claim_id) : `row-${i}`}
                          onClick={() => setSelected(r)}
                          className={cn(
                            'grid w-full grid-cols-12 gap-3 px-4 py-3 text-left outline-none transition hover:bg-white/70 focus-visible:ring-4 focus-visible:ring-[var(--ring)]',
                            active && 'bg-gradient-to-br from-blue-50/80 via-white/70 to-cyan-50/70',
                          )}
                        >
                          <div className="col-span-3 min-w-0">
                            <div className="truncate text-sm font-semibold text-slate-900">{String(r?.claim_id || '—')}</div>
                            <div className="mt-0.5 truncate text-xs text-slate-600">{String(r?.payer || r?.tpa || '—')}</div>
                          </div>
                          <div className="col-span-3 min-w-0">
                            <div className="truncate text-sm text-slate-800">{String(r?.denial_reason || '—')}</div>
                            <div className="mt-0.5 truncate text-xs text-slate-600">{String(r?.denial_code || '—')}</div>
                          </div>
                          <div className="col-span-3 min-w-0">
                            <div className="truncate text-sm text-slate-800">{String(r?.root_cause || '—')}</div>
                            <div className="mt-0.5 truncate text-xs text-slate-600">{String(r?.action_taken || '—')}</div>
                          </div>
                          <div className="col-span-2 flex items-center">
                            <Badge variant={tone.variant}>{tone.label}</Badge>
                          </div>
                          <div className="col-span-1 flex items-center justify-end">
                            <ChevronRight className="size-4 text-slate-500" />
                          </div>
                        </button>
                      )
                    })}
                  </div>
                ) : (
                  <div className="p-6 text-sm text-slate-600">No denied claims match this filter.</div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="xl:col-span-2">
          <Card variant="glass">
            <CardHeader>
              <div>
                <CardTitle>Denial detail</CardTitle>
                <CardDescription>Reason, root cause, and recommended next action.</CardDescription>
              </div>
              <Badge variant="neutral" className="bg-white/70">
                {selected?.claim_id ? 'Selected' : 'None'}
              </Badge>
            </CardHeader>
            <CardContent>
              {!selected ? (
                <div className="rounded-[26px] border border-white/70 bg-white/55 p-5 text-sm text-slate-600">
                  Select a claim to view detail.
                </div>
              ) : (
                <div className="space-y-3">
                  {[
                    { label: 'Claim ID', value: selected?.claim_id },
                    { label: 'Denial reason', value: selected?.denial_reason },
                    { label: 'Root cause', value: selected?.root_cause },
                    { label: 'Action taken', value: selected?.action_taken },
                  ].map((it) => (
                    <div key={it.label} className="rounded-[26px] border border-white/70 bg-white/55 p-4">
                      <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">{it.label}</div>
                      <div className="mt-2 text-sm font-semibold text-slate-900">{String(it.value || '—')}</div>
                    </div>
                  ))}
                  <div className="grid gap-2 sm:grid-cols-2">
                    <Button variant="secondary">Mark fixed</Button>
                    <Button variant="outline">Escalate</Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

