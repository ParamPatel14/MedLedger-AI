import { useCallback, useEffect, useMemo, useState } from 'react'
import { History, RefreshCcw, SlidersHorizontal } from 'lucide-react'

import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card'
import { Input } from '../components/ui/input'
import { Skeleton } from '../components/ui/skeleton'
import { cn } from '../lib/cn'
import { getRuleHistory, getRuleSummary, listRules } from '../services/api'

function PageTitle() {
  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-[-0.03em] text-slate-900 md:text-3xl">Rule engine</h1>
      <p className="mt-1 max-w-3xl text-sm text-slate-600">
        Explore active rules by TPA and category, track confidence + versions, and inspect change history.
      </p>
    </div>
  )
}

function confidenceTone(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return 'neutral'
  if (n >= 0.92) return 'success'
  if (n >= 0.78) return 'info'
  if (n >= 0.6) return 'warning'
  return 'error'
}

function fmt(x) {
  if (x === null || x === undefined) return '—'
  return String(x)
}

export default function RuleEngine() {
  const [summary, setSummary] = useState({ loading: true, error: '', data: null })
  const [state, setState] = useState({ loading: true, error: '', items: [] })
  const [tpa, setTpa] = useState('')
  const [category, setCategory] = useState('')
  const [selectedId, setSelectedId] = useState('')
  const [historyState, setHistoryState] = useState({ loading: false, error: '', data: null })

  const loadSummary = useCallback(async () => {
    setSummary({ loading: true, error: '', data: null })
    try {
      const d = await getRuleSummary()
      setSummary({ loading: false, error: '', data: d })
    } catch (e) {
      setSummary({ loading: false, error: e?.message || 'Failed to load summary', data: null })
    }
  }, [])

  const runSearch = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: '' }))
    try {
      const payload = await listRules({
        tpa: String(tpa || '').trim(),
        category: String(category || '').trim(),
        active: true,
        limit: 60,
        offset: 0,
      })
      setState({ loading: false, error: '', items: Array.isArray(payload?.items) ? payload.items : [] })
    } catch (e) {
      setState({ loading: false, error: e?.message || 'Failed to load rules', items: [] })
    }
  }, [tpa, category])

  useEffect(() => {
    let active = true
    ;(async () => {
      try {
        const [s, p] = await Promise.all([getRuleSummary(), listRules({ active: true, limit: 60, offset: 0 })])
        if (!active) return
        setSummary({ loading: false, error: '', data: s })
        const items = Array.isArray(p?.items) ? p.items : []
        setState({ loading: false, error: '', items })
        setSelectedId((prev) => prev || String(items?.[0]?.id || ''))
      } catch (e) {
        if (!active) return
        setSummary({ loading: false, error: '', data: null })
        setState({ loading: false, error: e?.message || 'Failed to load rule engine', items: [] })
      }
    })()
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    if (!selectedId) return
    let active = true
    setHistoryState({ loading: true, error: '', data: null })
    ;(async () => {
      try {
        const h = await getRuleHistory(selectedId)
        if (!active) return
        setHistoryState({ loading: false, error: '', data: h })
      } catch (e) {
        if (!active) return
        setHistoryState({ loading: false, error: e?.message || 'Failed to load history', data: null })
      }
    })()
    return () => {
      active = false
    }
  }, [selectedId])

  const items = state.items
  const selected = useMemo(() => items.find((r) => String(r?.id || '') === String(selectedId || '')) || null, [items, selectedId])
  const events = useMemo(() => (Array.isArray(historyState.data?.events) ? historyState.data.events : []), [historyState.data])

  const kpis = useMemo(() => {
    const d = summary.data || {}
    return [
      { label: 'Active rules', value: d?.active_rules ?? d?.active ?? items.length ?? 0, tone: 'info' },
      { label: 'TPAs covered', value: d?.tpas ?? d?.tpa_count ?? '—', tone: 'neutral' },
      { label: 'Avg confidence', value: typeof d?.avg_confidence === 'number' ? d.avg_confidence.toFixed(2) : '—', tone: 'success' },
    ]
  }, [summary.data, items.length])

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <PageTitle />
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={loadSummary} disabled={summary.loading}>
            <RefreshCcw className="size-4" />
            Refresh
          </Button>
          <Button variant="secondary">
            <SlidersHorizontal className="size-4" />
            Configure
          </Button>
        </div>
      </div>

      {(state.error || summary.error) && (
        <div className="glass-panel rounded-[28px] border border-rose-200/60 bg-rose-50/60 p-5 text-sm text-rose-700">
          {state.error || summary.error}
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-3">
        {kpis.map((k) => (
          <Card key={k.label} variant="glass" className="p-5">
            <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">{k.label}</div>
            <div className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-slate-900">
              {summary.loading ? <Skeleton className="h-7 w-28" /> : String(k.value)}
            </div>
            <div className="mt-3">
              <Badge variant={k.tone} className="bg-white/70">
                {k.tone === 'success' ? 'High quality' : k.tone === 'info' ? 'Coverage' : 'Index'}
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
                <CardTitle>Active rules</CardTitle>
                <CardDescription>Filter by TPA and category.</CardDescription>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <div className="w-[220px] max-w-[44vw]">
                  <Input value={tpa} onChange={(e) => setTpa(e.target.value)} placeholder="TPA (e.g., ACME)" />
                </div>
                <div className="w-[240px] max-w-[44vw]">
                  <Input value={category} onChange={(e) => setCategory(e.target.value)} placeholder="Category (e.g., room_rent)" />
                </div>
                <Button variant="outline" onClick={runSearch} disabled={state.loading}>
                  Search
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="overflow-hidden rounded-[26px] border border-white/70 bg-white/55">
                <div className="grid grid-cols-12 gap-3 border-b border-white/70 bg-white/60 px-4 py-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-600">
                  <div className="col-span-3">TPA</div>
                  <div className="col-span-3">Category</div>
                  <div className="col-span-2">Type</div>
                  <div className="col-span-2">Confidence</div>
                  <div className="col-span-2">Version</div>
                </div>

                {state.loading ? (
                  <div className="space-y-2 p-4">
                    {Array.from({ length: 10 }).map((_, i) => (
                      <Skeleton key={i} className="h-12 w-full rounded-2xl" />
                    ))}
                  </div>
                ) : items.length ? (
                  <div className="divide-y divide-white/70">
                    {items.slice(0, 18).map((r) => {
                      const active = String(r?.id || '') === String(selectedId || '')
                      const conf = r?.confidence
                      const version = r?.version ?? r?.rule_version ?? r?.to_version ?? r?.current_version
                      return (
                        <button
                          key={r.id}
                          onClick={() => setSelectedId(String(r.id))}
                          className={cn(
                            'grid w-full grid-cols-12 gap-3 px-4 py-3 text-left outline-none transition hover:bg-white/70 focus-visible:ring-4 focus-visible:ring-[var(--ring)]',
                            active && 'bg-gradient-to-br from-blue-50/80 via-white/70 to-cyan-50/70',
                          )}
                        >
                          <div className="col-span-3 min-w-0">
                            <div className="truncate text-sm font-semibold text-slate-900">{fmt(r.tpa_name || r.tpa)}</div>
                            <div className="mt-0.5 truncate text-xs text-slate-600">{fmt(r.source)}</div>
                          </div>
                          <div className="col-span-3 min-w-0">
                            <div className="truncate text-sm text-slate-800">{fmt(r.category)}</div>
                            <div className="mt-0.5 truncate text-xs text-slate-600">{fmt(r.rule_id || r.id)}</div>
                          </div>
                          <div className="col-span-2 min-w-0">
                            <div className="truncate text-sm text-slate-800">{fmt(r.rule_type)}</div>
                            <div className="mt-0.5 truncate text-xs text-slate-600">{fmt(r.unit)}</div>
                          </div>
                          <div className="col-span-2 flex items-center">
                            <Badge variant={confidenceTone(conf)}>{fmt(typeof conf === 'number' ? conf.toFixed(2) : conf)}</Badge>
                          </div>
                          <div className="col-span-2 flex items-center">
                            <Badge variant="neutral">{fmt(version ?? 'v1')}</Badge>
                          </div>
                        </button>
                      )
                    })}
                  </div>
                ) : (
                  <div className="p-6 text-sm text-slate-600">No rules found.</div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="xl:col-span-2 space-y-4">
          <Card variant="glass">
            <CardHeader>
              <div>
                <CardTitle>Rule detail</CardTitle>
                <CardDescription>Value, unit, confidence, version.</CardDescription>
              </div>
              <Badge variant="neutral" className="bg-white/70">
                {selected ? 'Selected' : 'None'}
              </Badge>
            </CardHeader>
            <CardContent>
              {!selected ? (
                <div className="rounded-[26px] border border-white/70 bg-white/55 p-5 text-sm text-slate-600">
                  Select a rule to inspect.
                </div>
              ) : (
                <div className="space-y-3">
                  {[
                    { label: 'TPA', value: selected?.tpa_name || selected?.tpa },
                    { label: 'Category', value: selected?.category },
                    { label: 'Type', value: selected?.rule_type },
                    { label: 'Value', value: selected?.value_text ?? selected?.value },
                    { label: 'Confidence', value: typeof selected?.confidence === 'number' ? selected.confidence.toFixed(2) : selected?.confidence },
                    { label: 'Version', value: selected?.version ?? selected?.rule_version ?? 'v1' },
                  ].map((it) => (
                    <div key={it.label} className="rounded-[26px] border border-white/70 bg-white/55 p-4">
                      <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">{it.label}</div>
                      <div className="mt-2 text-sm font-semibold text-slate-900">{fmt(it.value)}</div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <div className="grid size-10 place-items-center rounded-2xl border border-white/70 bg-white/60">
                  <History className="size-4 text-slate-700" />
                </div>
                <div>
                  <CardTitle>Rule history</CardTitle>
                  <CardDescription>Version changes over time.</CardDescription>
                </div>
              </div>
              <Badge variant="info" className="bg-white/70">
                {historyState.loading ? 'Loading' : `${events.length} events`}
              </Badge>
            </CardHeader>
            <CardContent>
              {historyState.error ? (
                <div className="rounded-[26px] border border-rose-200/60 bg-rose-50/60 p-4 text-sm text-rose-700">
                  {historyState.error}
                </div>
              ) : historyState.loading ? (
                <div className="space-y-2">
                  {Array.from({ length: 6 }).map((_, i) => (
                    <Skeleton key={i} className="h-14 w-full rounded-2xl" />
                  ))}
                </div>
              ) : events.length ? (
                <div className="space-y-2">
                  {events.slice(0, 10).map((e) => (
                    <div
                      key={e.id}
                      className="rounded-[26px] border border-white/70 bg-white/55 p-4 shadow-[0_14px_50px_rgba(2,6,23,0.10)]"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div className="text-sm font-semibold text-slate-900">
                          v{fmt(e.from_version)} → v{fmt(e.to_version)}
                        </div>
                        <Badge variant="neutral">{fmt(e.changed_at)}</Badge>
                      </div>
                      <div className="mt-2 truncate text-xs text-slate-600">{fmt(JSON.stringify(e.diff || {}))}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="rounded-[26px] border border-white/70 bg-white/55 p-5 text-sm text-slate-600">
                  No history events for this rule.
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
