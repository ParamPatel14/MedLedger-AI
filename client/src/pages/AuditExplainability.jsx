import { useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { Timeline } from '../components/patterns/Timeline'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card'
import { Skeleton } from '../components/ui/skeleton'
import { Textarea } from '../components/ui/textarea'
import { getExplainabilityAudit, runClaimExplain } from '../services/api'

function PageTitle() {
  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-[-0.03em] text-slate-900 md:text-3xl">Audit & explainability</h1>
      <p className="mt-1 max-w-3xl text-sm text-slate-600">
        An audit-ready view of decision traces, explanation cards, and confidence breakdowns.
      </p>
    </div>
  )
}

function decisionTone(decision) {
  const d = String(decision || '').toUpperCase()
  if (d === 'APPROVE') return { badge: 'success', label: 'Approve' }
  if (d === 'WARN') return { badge: 'warning', label: 'Warn' }
  if (d === 'ESCALATE') return { badge: 'warning', label: 'Escalate' }
  if (d === 'BLOCK') return { badge: 'error', label: 'Block' }
  return { badge: 'neutral', label: '—' }
}

function fmt2(x) {
  const n = Number(x)
  if (!Number.isFinite(n)) return '0.00'
  return n.toFixed(2)
}

function pickGroups(explanations) {
  const list = Array.isArray(explanations) ? explanations : []
  const buckets = {}
  for (const it of list) {
    const t = String(it?.type || 'other').toLowerCase()
    if (!buckets[t]) buckets[t] = []
    buckets[t].push(it)
  }
  return buckets
}

function ExplanationCard({ title, items }) {
  const list = Array.isArray(items) ? items : []
  return (
    <Card variant="glass">
      <CardHeader>
        <div>
          <CardTitle>{title}</CardTitle>
          <CardDescription>High-signal narrative + confidence.</CardDescription>
        </div>
        <Badge variant="neutral" className="bg-white/70">
          {list.length} items
        </Badge>
      </CardHeader>
      <CardContent>
        {list.length ? (
          <div className="space-y-2">
            {list.slice(0, 6).map((it, idx) => (
              <div
                key={`${it?.type || 'exp'}-${idx}`}
                className="rounded-[26px] border border-white/70 bg-white/55 p-4 shadow-[0_14px_50px_rgba(2,6,23,0.10)]"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">{String(it?.type || 'explanation')}</div>
                  <Badge variant="info">Conf {fmt2(it?.confidence)}</Badge>
                </div>
                <div className="mt-2 text-sm font-semibold text-slate-900">{String(it?.explanation || '—')}</div>
                {it?.details ? (
                  <div className="mt-2 truncate text-xs text-slate-600">{JSON.stringify(it.details)}</div>
                ) : null}
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-[26px] border border-white/70 bg-white/55 p-5 text-sm text-slate-600">
            No explanations available.
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default function AuditExplainability() {
  const [text, setText] = useState('')
  const [state, setState] = useState({ loading: false, error: '', result: null })
  const [auditState, setAuditState] = useState({ loading: false, error: '', audit: null })

  const run = async () => {
    const payload = String(text || '').trim()
    if (!payload) return
    setState({ loading: true, error: '', result: null })
    setAuditState({ loading: false, error: '', audit: null })
    try {
      const out = await runClaimExplain(payload)
      setState({ loading: false, error: '', result: out })
    } catch (e) {
      setState({ loading: false, error: e?.message || 'Explain request failed', result: null })
    }
  }

  const loadAudit = async () => {
    const id = state.result?.audit_id
    if (!id) return
    setAuditState({ loading: true, error: '', audit: null })
    try {
      const a = await getExplainabilityAudit(id)
      setAuditState({ loading: false, error: '', audit: a })
    } catch (e) {
      setAuditState({ loading: false, error: e?.message || 'Audit request failed', audit: null })
    }
  }

  const grouped = useMemo(() => pickGroups(state.result?.explanations), [state.result])

  const timeline = useMemo(() => {
    const steps = Array.isArray(state.result?.trace?.steps) ? state.result.trace.steps : []
    if (steps.length) {
      return steps.slice(0, 10).map((s, idx) => ({
        id: `${s?.stage || 'stage'}-${idx}`,
        title: String(s?.stage || 'stage'),
        subtitle: String(s?.message || s?.status || ''),
        status: String(s?.status || '').toLowerCase() || 'ok',
        badgeLabel: String(s?.status || 'ok'),
        meta: s?.timestamp ? `Timestamp: ${String(s.timestamp)}` : '',
      }))
    }
    return [
      { id: 't1', title: 'Clinical extraction', subtitle: 'Entities + sections', status: 'ok', badgeLabel: 'Done' },
      { id: 't2', title: 'Coding', subtitle: 'ICD mapping + checks', status: 'ok', badgeLabel: 'Done' },
      { id: 't3', title: 'Rules', subtitle: 'TPA validation', status: 'warn', badgeLabel: 'Warn' },
      { id: 't4', title: 'Governance', subtitle: 'Guardrails + decision', status: 'ok', badgeLabel: 'Done' },
    ]
  }, [state.result])

  const confidenceData = useMemo(() => {
    const exps = Array.isArray(state.result?.explanations) ? state.result.explanations : []
    const by = {}
    for (const e of exps) {
      const t = String(e?.type || 'other').toLowerCase()
      if (!by[t]) by[t] = { type: t, avg: 0, count: 0 }
      const v = Number(e?.confidence)
      if (Number.isFinite(v)) {
        by[t].avg += v
        by[t].count += 1
      }
    }
    const rows = Object.values(by).map((r) => ({
      type: r.type,
      confidence: r.count ? r.avg / r.count : 0,
    }))
    if (rows.length) return rows
    return [
      { type: 'clinical', confidence: 0.92 },
      { type: 'coding', confidence: 0.88 },
      { type: 'rule', confidence: 0.84 },
      { type: 'policy', confidence: 0.9 },
    ]
  }, [state.result])

  const tone = decisionTone(state.result?.decision)

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <PageTitle />
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => setText('')} disabled={state.loading}>
            Reset
          </Button>
          <Button onClick={run} disabled={state.loading || !String(text || '').trim()}>
            Explain
          </Button>
        </div>
      </div>

      {(state.error || auditState.error) && (
        <div className="glass-panel rounded-[28px] border border-rose-200/60 bg-rose-50/60 p-5 text-sm text-rose-700">
          {state.error || auditState.error}
        </div>
      )}

      <div className="grid gap-4 xl:grid-cols-5">
        <div className="xl:col-span-2">
          <Card variant="glass">
            <CardHeader>
              <div>
                <CardTitle>Input</CardTitle>
                <CardDescription>Paste a clinical note for explainability.</CardDescription>
              </div>
              {state.result?.audit_id ? (
                <Badge variant="neutral" className="bg-white/70">
                  Audit {String(state.result.audit_id).slice(0, 8)}
                </Badge>
              ) : (
                <Badge variant="info" className="bg-white/70">
                  Explainable AI
                </Badge>
              )}
            </CardHeader>
            <CardContent>
              <Textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Paste clinical note text…"
                className="min-h-56"
              />
              <div className="mt-3 flex flex-wrap gap-2">
                <Button onClick={run} disabled={state.loading || !String(text || '').trim()}>
                  {state.loading ? 'Explaining…' : 'Explain claim'}
                </Button>
                {state.result?.audit_id ? (
                  <Button variant="outline" onClick={loadAudit} disabled={auditState.loading}>
                    {auditState.loading ? 'Loading audit…' : 'Load audit JSON'}
                  </Button>
                ) : null}
              </div>
            </CardContent>
          </Card>

          <Card className="mt-4">
            <CardHeader>
              <div>
                <CardTitle>Decision</CardTitle>
                <CardDescription>Outcome + top-level confidence.</CardDescription>
              </div>
              <Badge variant={tone.badge} className="bg-white/70">
                {tone.label}
              </Badge>
            </CardHeader>
            <CardContent>
              {state.loading ? (
                <div className="grid gap-2">
                  <Skeleton className="h-14 w-full rounded-[26px]" />
                  <Skeleton className="h-14 w-full rounded-[26px]" />
                </div>
              ) : (
                <div className="grid gap-3">
                  <div className="rounded-[26px] border border-white/70 bg-white/55 p-4">
                    <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Decision</div>
                    <div className="mt-2 text-xl font-semibold tracking-[-0.03em] text-slate-900">
                      {String(state.result?.decision || '—').toUpperCase()}
                    </div>
                  </div>
                  <div className="rounded-[26px] border border-white/70 bg-white/55 p-4">
                    <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Confidence</div>
                    <div className="mt-2 text-xl font-semibold tracking-[-0.03em] text-slate-900">
                      {fmt2(state.result?.confidence)}
                    </div>
                    <div className="mt-3 h-2.5 w-full overflow-hidden rounded-full bg-slate-200/70">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-blue-500 via-violet-500 to-cyan-400"
                        style={{ width: `${Math.round(Number(state.result?.confidence || 0.9) * 100)}%` }}
                      />
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="xl:col-span-3 space-y-4">
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Decision trace timeline</CardTitle>
                <CardDescription>Human-readable, audit-friendly ordering.</CardDescription>
              </div>
              <Badge variant="neutral" className="bg-white/70">
                Trace
              </Badge>
            </CardHeader>
            <CardContent>
              <Timeline items={timeline} />
            </CardContent>
          </Card>

          <Card variant="glass">
            <CardHeader>
              <div>
                <CardTitle>Confidence breakdown</CardTitle>
                <CardDescription>Average confidence per reasoning layer.</CardDescription>
              </div>
              <Badge variant="info" className="bg-white/70">
                Analytics
              </Badge>
            </CardHeader>
            <CardContent>
              <div className="h-[260px] w-full">
                {state.loading ? (
                  <div className="grid h-full grid-cols-12 gap-2">
                    {Array.from({ length: 18 }).map((_, i) => (
                      <Skeleton key={i} className="h-full w-full" />
                    ))}
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={confidenceData} margin={{ top: 12, right: 12, left: 0, bottom: 0 }}>
                      <CartesianGrid stroke="rgba(148,163,184,0.28)" vertical={false} />
                      <XAxis dataKey="type" tickLine={false} axisLine={false} fontSize={12} stroke="rgba(15,23,42,0.55)" />
                      <YAxis
                        tickLine={false}
                        axisLine={false}
                        fontSize={12}
                        stroke="rgba(15,23,42,0.55)"
                        domain={[0, 1]}
                        width={28}
                      />
                      <Tooltip
                        cursor={{ fill: 'rgba(37, 99, 235, 0.08)' }}
                        contentStyle={{
                          borderRadius: 18,
                          border: '1px solid rgba(148,163,184,0.35)',
                          background: 'rgba(255,255,255,0.78)',
                          backdropFilter: 'blur(12px)',
                          boxShadow: '0 30px 90px rgba(2,6,23,0.18)',
                        }}
                      />
                      <Bar dataKey="confidence" radius={[14, 14, 14, 14]} fill="rgba(37, 99, 235, 0.82)" />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>
            </CardContent>
          </Card>

          <div className="grid gap-4 lg:grid-cols-3">
            <ExplanationCard title="Clinical reasoning" items={grouped.clinical || []} />
            <ExplanationCard title="Coding logic" items={grouped.coding || []} />
            <ExplanationCard title="Rule validation" items={grouped.rule || []} />
          </div>

          {auditState.audit ? (
            <Card>
              <CardHeader>
                <div>
                  <CardTitle>Audit JSON</CardTitle>
                  <CardDescription>Raw payload for compliance workflows.</CardDescription>
                </div>
                <Badge variant="neutral" className="bg-white/70">
                  JSON
                </Badge>
              </CardHeader>
              <CardContent>
                <pre className="max-h-72 overflow-auto rounded-[26px] border border-white/70 bg-white/55 p-4 text-[11px] text-slate-700">
                  {JSON.stringify(auditState.audit, null, 2)}
                </pre>
              </CardContent>
            </Card>
          ) : null}
        </div>
      </div>
    </div>
  )
}
