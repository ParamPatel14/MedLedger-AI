import { useCallback, useEffect, useState } from 'react'
import { getRuleConflicts } from '../services/api'

function fmt(x) {
  if (x === null || x === undefined) return ''
  if (typeof x === 'number' && Number.isFinite(x)) return String(x)
  return String(x)
}

export default function RuleConflictViewer() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [groups, setGroups] = useState([])

  const refresh = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const payload = await getRuleConflicts({ limitGroups: 25 })
      setGroups(Array.isArray(payload?.items) ? payload.items : [])
    } catch (e) {
      setError(String(e?.message || e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-sm font-semibold text-slate-800">Conflicting Rules</div>
        <button type="button" className="btn btnGhost" onClick={refresh} disabled={loading}>
          {loading ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {error ? <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{error}</div> : null}

      <div className="mt-4 space-y-3">
        {groups.length ? (
          groups.map((g, idx) => (
            <div key={`${g.tpa_name}-${g.category}-${g.rule_type}-${idx}`} className="rounded-lg border border-amber-200 bg-amber-50 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="text-sm font-semibold text-slate-900">
                  {fmt(g.tpa_name)} · {fmt(g.category)} · {fmt(g.rule_type)}
                </div>
                <div className="text-xs text-amber-800">{fmt(g.reason || 'potential_conflict')}</div>
              </div>

              <div className="mt-2 overflow-auto">
                <table className="min-w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-amber-200 text-[11px] text-slate-600">
                      <th className="py-2 pr-4 font-semibold">Value</th>
                      <th className="py-2 pr-4 font-semibold">Unit</th>
                      <th className="py-2 pr-4 font-semibold">Confidence</th>
                      <th className="py-2 pr-4 font-semibold">Conditions</th>
                      <th className="py-2 pr-4 font-semibold">Source</th>
                      <th className="py-2 pr-2 font-semibold">Updated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(Array.isArray(g.rules) ? g.rules : []).map((r) => (
                      <tr key={r.id} className="border-b border-amber-100 last:border-0">
                        <td className="py-2 pr-4 font-semibold text-slate-900">{fmt(r.value_text || r.value)}</td>
                        <td className="py-2 pr-4 text-slate-700">{fmt(r.unit)}</td>
                        <td className="py-2 pr-4 tabular-nums text-slate-700">{fmt(r.confidence)}</td>
                        <td className="py-2 pr-4 text-slate-700">{JSON.stringify(r.conditions || {})}</td>
                        <td className="py-2 pr-4 text-slate-700">{fmt(r.source)}</td>
                        <td className="py-2 pr-2 text-slate-500">{fmt(r.updated_at || '')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))
        ) : (
          <div className="text-sm text-slate-500">No conflicts detected</div>
        )}
      </div>
    </div>
  )
}

