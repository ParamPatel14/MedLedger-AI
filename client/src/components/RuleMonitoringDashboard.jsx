import { useCallback, useEffect, useMemo, useState } from 'react'
import { getRuleSummary, getRuleUpdates } from '../services/api'

function numberOrZero(x) {
  const n = Number(x)
  return Number.isFinite(n) ? n : 0
}

export default function RuleMonitoringDashboard() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [summary, setSummary] = useState(null)
  const [updates, setUpdates] = useState([])

  const topTpas = useMemo(() => {
    const map = summary?.by_tpa || {}
    const pairs = Object.entries(map).map(([k, v]) => [k, numberOrZero(v)])
    pairs.sort((a, b) => b[1] - a[1])
    return pairs.slice(0, 8)
  }, [summary])

  const topSources = useMemo(() => {
    const map = summary?.by_source || {}
    const pairs = Object.entries(map).map(([k, v]) => [k, numberOrZero(v)])
    pairs.sort((a, b) => b[1] - a[1])
    return pairs
  }, [summary])

  const refresh = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [s, u] = await Promise.all([getRuleSummary(), getRuleUpdates({ limit: 25 })])
      setSummary(s)
      setUpdates(Array.isArray(u?.items) ? u.items : [])
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
        <div className="text-sm font-semibold text-slate-800">Active Rules & Recent Updates</div>
        <button type="button" className="btn btnGhost" onClick={refresh} disabled={loading}>
          {loading ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {error ? <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{error}</div> : null}

      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <div className="rounded-lg border border-slate-200 p-3">
          <div className="text-xs text-slate-500">Active rules</div>
          <div className="mt-1 text-2xl font-semibold text-slate-900">{numberOrZero(summary?.total_active)}</div>
          <div className="mt-2 text-xs text-slate-500">By source</div>
          <div className="mt-1 space-y-1 text-xs">
            {topSources.length ? (
              topSources.map(([k, v]) => (
                <div key={k} className="flex items-center justify-between gap-2">
                  <span className="truncate text-slate-700">{k || 'unknown'}</span>
                  <span className="tabular-nums text-slate-900">{v}</span>
                </div>
              ))
            ) : (
              <div className="text-slate-400">No data</div>
            )}
          </div>
        </div>

        <div className="rounded-lg border border-slate-200 p-3">
          <div className="text-xs text-slate-500">Top TPAs (active rules)</div>
          <div className="mt-2 space-y-1 text-xs">
            {topTpas.length ? (
              topTpas.map(([k, v]) => (
                <div key={k} className="flex items-center justify-between gap-2">
                  <span className="truncate text-slate-700">{k || 'unknown'}</span>
                  <span className="tabular-nums text-slate-900">{v}</span>
                </div>
              ))
            ) : (
              <div className="text-slate-400">No data</div>
            )}
          </div>
        </div>

        <div className="rounded-lg border border-slate-200 p-3">
          <div className="text-xs text-slate-500">Recent updates</div>
          <div className="mt-2 max-h-[280px] space-y-2 overflow-auto pr-1 text-xs">
            {updates.length ? (
              updates.map((u) => (
                <div key={u.id} className="rounded-md border border-slate-100 bg-slate-50 px-2 py-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="font-semibold text-slate-800">
                      {(u.tpa_name || 'TPA')} · {(u.category || 'category')} · {(u.rule_type || 'type')}
                    </div>
                    <div className="text-[11px] text-slate-500">
                      v{numberOrZero(u.from_version)} → v{numberOrZero(u.to_version)}
                    </div>
                  </div>
                  <div className="mt-1 text-[11px] text-slate-500">{String(u.changed_at || '')}</div>
                  <div className="mt-1 truncate text-[11px] text-slate-700">{JSON.stringify(u.diff || {})}</div>
                </div>
              ))
            ) : (
              <div className="text-slate-400">No updates found</div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
