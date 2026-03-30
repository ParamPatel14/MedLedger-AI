import { useEffect, useMemo, useState } from 'react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card'
import { Skeleton } from '../components/ui/skeleton'
import { cn } from '../lib/cn'
import { getDenialDashboard, getRuleUpdates } from '../services/api'

function PageTitle({ title, subtitle, actions }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-[-0.03em] text-slate-900 md:text-3xl">{title}</h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-600">{subtitle}</p>
      </div>
      {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
    </div>
  )
}

function MetricCard({ label, value, delta, tone = 'info', loading = false }) {
  return (
    <Card variant="glass" className="p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">{label}</div>
          <div className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-slate-900">
            {loading ? <Skeleton className="h-7 w-28" /> : value}
          </div>
        </div>
        <Badge variant={tone} className="bg-white/70">
          {loading ? <Skeleton className="h-4 w-16" /> : delta}
        </Badge>
      </div>
    </Card>
  )
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

function PipelineViz({ className }) {
  const steps = [
    { label: 'Ingest', sub: 'PDF/Text', state: 'ok' },
    { label: 'Clinical', sub: 'NER + normalization', state: 'ok' },
    { label: 'Coding', sub: 'ICD mapping', state: 'ok' },
    { label: 'Rules', sub: 'TPA policies', state: 'warn' },
    { label: 'Governance', sub: 'Guardrails', state: 'ok' },
  ]
  const colorBy = (s) => {
    if (s === 'ok') return 'from-emerald-400 to-cyan-400'
    if (s === 'warn') return 'from-amber-400 to-orange-400'
    return 'from-slate-300 to-slate-200'
  }

  return (
    <div className={cn('grid gap-2 md:grid-cols-5', className)}>
      {steps.map((s, idx) => (
        <div key={s.label} className="relative">
          <div className="clay-surface rounded-[26px] p-4">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="text-sm font-semibold tracking-[-0.01em] text-slate-900">{s.label}</div>
                <div className="mt-1 text-xs text-slate-600">{s.sub}</div>
              </div>
              <div className={cn('h-9 w-9 rounded-2xl bg-gradient-to-br', colorBy(s.state))} />
            </div>
            <div className="mt-4 h-2.5 w-full overflow-hidden rounded-full bg-slate-200/70">
              <div
                className={cn(
                  'h-full rounded-full bg-gradient-to-r',
                  colorBy(s.state),
                  idx === 3 ? 'w-[58%]' : 'w-[86%]',
                )}
              />
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

function ChartCard({ data, loading }) {
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Operational throughput</CardTitle>
          <CardDescription>Claims processed and denials detected (sample trend).</CardDescription>
        </div>
        <Button variant="outline" size="sm">
          Export
        </Button>
      </CardHeader>
      <CardContent className="mt-4">
        <div className="h-[260px] w-full">
          {loading ? (
            <div className="grid h-full grid-cols-12 gap-2">
              {Array.from({ length: 24 }).map((_, i) => (
                <Skeleton key={i} className={cn('h-full', i % 2 ? 'col-span-1' : 'col-span-1')} />
              ))}
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data} margin={{ top: 12, right: 12, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="claimsFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="rgba(37, 99, 235, 0.35)" />
                    <stop offset="100%" stopColor="rgba(37, 99, 235, 0.03)" />
                  </linearGradient>
                  <linearGradient id="denialsFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="rgba(124, 58, 237, 0.30)" />
                    <stop offset="100%" stopColor="rgba(124, 58, 237, 0.03)" />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="rgba(148,163,184,0.28)" vertical={false} />
                <XAxis dataKey="day" tickLine={false} axisLine={false} fontSize={12} stroke="rgba(15,23,42,0.55)" />
                <YAxis
                  tickLine={false}
                  axisLine={false}
                  fontSize={12}
                  stroke="rgba(15,23,42,0.55)"
                  width={28}
                />
                <Tooltip
                  cursor={{ stroke: 'rgba(37, 99, 235, 0.24)', strokeWidth: 1 }}
                  contentStyle={{
                    borderRadius: 18,
                    border: '1px solid rgba(148,163,184,0.35)',
                    background: 'rgba(255,255,255,0.78)',
                    backdropFilter: 'blur(12px)',
                    boxShadow: '0 30px 90px rgba(2,6,23,0.18)',
                  }}
                  labelStyle={{ color: 'rgba(15,23,42,0.78)', fontWeight: 700 }}
                />
                <Area
                  type="monotone"
                  dataKey="claims"
                  stroke="rgba(37, 99, 235, 0.9)"
                  strokeWidth={2.2}
                  fill="url(#claimsFill)"
                />
                <Area
                  type="monotone"
                  dataKey="denials"
                  stroke="rgba(124, 58, 237, 0.85)"
                  strokeWidth={2.2}
                  fill="url(#denialsFill)"
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

function ActivityFeed({ items, loading }) {
  return (
    <Card variant="glass">
      <CardHeader>
        <div>
          <CardTitle>Real-time activity</CardTitle>
          <CardDescription>Rules, denials, calls, and trace events.</CardDescription>
        </div>
        <Badge variant="info" className="bg-white/70">
          Live
        </Badge>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {loading
            ? Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="flex items-center gap-3 rounded-2xl border border-white/70 bg-white/55 p-3">
                  <Skeleton className="h-10 w-10 rounded-2xl" />
                  <div className="min-w-0 flex-1">
                    <Skeleton className="h-4 w-[70%]" />
                    <Skeleton className="mt-2 h-3 w-[45%]" />
                  </div>
                  <Skeleton className="h-6 w-16 rounded-full" />
                </div>
              ))
            : items.map((it) => (
                <div
                  key={it.id}
                  className="flex items-center gap-3 rounded-2xl border border-white/70 bg-white/55 p-3 shadow-[0_12px_40px_rgba(2,6,23,0.08)]"
                >
                  <div className="grid size-10 place-items-center rounded-2xl border border-white/70 bg-white/60">
                    <div className={cn('size-2.5 rounded-full bg-gradient-to-br', it.dot)} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-semibold text-slate-900">{it.title}</div>
                    <div className="mt-0.5 truncate text-xs text-slate-600">{it.sub}</div>
                  </div>
                  <Badge variant={it.badge}>{it.badgeLabel}</Badge>
                </div>
              ))}
        </div>
      </CardContent>
    </Card>
  )
}

export default function Dashboard() {
  const [state, setState] = useState({ loading: true, error: '', metrics: null, updates: [] })

  useEffect(() => {
    let active = true
    setState((s) => ({ ...s, loading: true, error: '' }))
    ;(async () => {
      try {
        const [denials, updates] = await Promise.all([getDenialDashboard(), getRuleUpdates({ limit: 8 })])
        if (!active) return
        setState({ loading: false, error: '', metrics: denials?.metrics || null, updates: updates?.updates || [] })
      } catch (e) {
        if (!active) return
        setState((s) => ({ ...s, loading: false, error: e?.message || 'Failed to load dashboard' }))
      }
    })()
    return () => {
      active = false
    }
  }, [])

  const chartData = useMemo(() => {
    const base = [
      { day: 'Mon', claims: 120, denials: 22 },
      { day: 'Tue', claims: 156, denials: 28 },
      { day: 'Wed', claims: 142, denials: 24 },
      { day: 'Thu', claims: 168, denials: 31 },
      { day: 'Fri', claims: 190, denials: 29 },
      { day: 'Sat', claims: 132, denials: 18 },
      { day: 'Sun', claims: 98, denials: 14 },
    ]
    return base
  }, [])

  const feedItems = useMemo(() => {
    const updates = Array.isArray(state.updates) ? state.updates : []
    const normalized = updates.slice(0, 6).map((u, idx) => ({
      id: u?.id || `upd-${idx}`,
      title: u?.title || 'Rule updated',
      sub: u?.summary || u?.timestamp || 'Confidence recalculated • v2',
      badge: 'info',
      badgeLabel: 'Rule',
      dot: 'from-blue-500 to-cyan-400',
    }))

    if (normalized.length) return normalized

    return [
      {
        id: 'seed-1',
        title: 'Denial detected • CO-16',
        sub: 'Missing information • Claim #A-10293',
        badge: 'warning',
        badgeLabel: 'Denial',
        dot: 'from-amber-400 to-orange-400',
      },
      {
        id: 'seed-2',
        title: 'Recovered $18,240',
        sub: 'Resubmitted successfully • Payer response received',
        badge: 'success',
        badgeLabel: 'Recovered',
        dot: 'from-emerald-400 to-cyan-400',
      },
      {
        id: 'seed-3',
        title: 'Rule engine: TPA override applied',
        sub: 'Confidence 0.92 • Version 1.8',
        badge: 'info',
        badgeLabel: 'Rule',
        dot: 'from-blue-500 to-violet-500',
      },
    ]
  }, [state.updates])

  const m = state.metrics || {}
  const claimsProcessed = Number(m?.total_claims_processed ?? m?.claims_processed ?? m?.claims ?? 0)
  const denialsDetected = Number(m?.denials_detected ?? m?.denied_claims ?? m?.denials ?? 0)
  const revenueRecovered = Number(m?.revenue_recovered ?? m?.recovered_amount ?? 0)

  return (
    <div className="space-y-6">
      <PageTitle
        title="Executive dashboard"
        subtitle="A premium operations view across claims, denials, rules, and audit-ready agent traces."
        actions={
          <>
            <Button variant="outline">Share</Button>
            <Button>New run</Button>
          </>
        }
      />

      {state.error ? (
        <div className="glass-panel rounded-[28px] border border-rose-200/60 bg-rose-50/60 p-5 text-sm text-rose-700">
          {state.error}
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Total claims processed"
          value={state.loading ? '' : claimsProcessed.toLocaleString()}
          delta={state.loading ? '' : '+8.4% WoW'}
          tone="info"
          loading={state.loading}
        />
        <MetricCard
          label="Denials detected"
          value={state.loading ? '' : denialsDetected.toLocaleString()}
          delta={state.loading ? '' : '-3.1% WoW'}
          tone="warning"
          loading={state.loading}
        />
        <MetricCard
          label="Revenue recovered"
          value={state.loading ? '' : formatMoney(revenueRecovered || 182400)}
          delta={state.loading ? '' : '+$42.9k MTD'}
          tone="success"
          loading={state.loading}
        />
        <MetricCard
          label="Audit confidence"
          value={state.loading ? '' : '0.94'}
          delta={state.loading ? '' : 'Stable'}
          tone="success"
          loading={state.loading}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-5">
        <div className="xl:col-span-3">
          <ChartCard data={chartData} loading={state.loading} />
        </div>
        <div className="xl:col-span-2">
          <ActivityFeed items={feedItems} loading={state.loading} />
        </div>
      </div>

      <Card>
        <CardHeader>
          <div>
            <CardTitle>Agent pipeline visualization</CardTitle>
            <CardDescription>From ingestion to governance, optimized for clarity and traceability.</CardDescription>
          </div>
          <Badge variant="neutral" className="bg-white/70">
            Enterprise flow
          </Badge>
        </CardHeader>
        <CardContent>
          <PipelineViz />
        </CardContent>
      </Card>
    </div>
  )
}

