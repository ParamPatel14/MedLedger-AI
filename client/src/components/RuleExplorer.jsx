import { useCallback, useEffect, useMemo, useState } from 'react'
import { getRuleHistory, listRules } from '../services/api'

function fmt(x) {
  if (x === null || x === undefined) return ''
  if (typeof x === 'number' && Number.isFinite(x)) return String(x)
  return String(x)
}

export default function RuleExplorer() {
  const [tpa, setTpa] = useState('')
  const [category, setCategory] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [items, setItems] = useState([])
  const [selectedRuleId, setSelectedRuleId] = useState('')
  const [history, setHistory] = useState(null)
  const [historyLoading, setHistoryLoading] = useState(false)

  const runSearch = useCallback(async () => {
    setLoading(true)
    setError('')
    setSelectedRuleId('')
    setHistory(null)
    try {
      const payload = await listRules({ tpa: tpa.trim(), category: category.trim(), active: true, limit: 100, offset: 0 })
      setItems(Array.isArray(payload?.items) ? payload.items : [])
    } catch (e) {
      setError(String(e?.message || e))
    } finally {
      setLoading(false)
    }
  }, [tpa, category])

  useEffect(() => {
    runSearch()
  }, [runSearch])

  const selectRule = useCallback(async (ruleId) => {
    setSelectedRuleId(ruleId)
    setHistory(null)
    setHistoryLoading(true)
    try {
      const h = await getRuleHistory(ruleId)
      setHistory(h)
    } catch (e) {
      setError(String(e?.message || e))
    } finally {
      setHistoryLoading(false)
    }
  }, [])

  const selectedEvents = useMemo(() => {
    const events = history?.events
    return Array.isArray(events) ? events : []
  }, [history])

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="text-sm font-semibold text-slate-800">Search Rules</div>

      <div className="mt-3 grid gap-3 md:grid-cols-3">
        <div>
          <label className="text-xs font-semibold text-slate-700">TPA</label>
          <input
            value={tpa}
            onChange={(e) => setTpa(e.target.value)}
            placeholder="e.g., ACME"
            className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="text-xs font-semibold text-slate-700">Category</label>
          <input
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            placeholder="e.g., room_rent"
            className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2 text-sm"
          />
        </div>
        <div className="flex items-end">
          <button type="button" className="btn btnPrimary w-full" onClick={runSearch} disabled={loading}>
            {loading ? 'Searching…' : 'Search'}
          </button>
        </div>
      </div>

      {error ? <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{error}</div> : null}

      <div className="mt-4 overflow-auto">
        <table className="min-w-full text-left text-xs">
          <thead>
            <tr className="border-b border-slate-200 text-[11px] text-slate-600">
              <th className="py-2 pr-4 font-semibold">TPA</th>
              <th className="py-2 pr-4 font-semibold">Category</th>
              <th className="py-2 pr-4 font-semibold">Type</th>
              <th className="py-2 pr-4 font-semibold">Value</th>
              <th className="py-2 pr-4 font-semibold">Unit</th>
              <th className="py-2 pr-4 font-semibold">Confidence</th>
              <th className="py-2 pr-2 font-semibold">Source</th>
            </tr>
          </thead>
          <tbody>
            {items.length ? (
              items.map((r) => (
                <tr
                  key={r.id}
                  className={`cursor-pointer border-b border-slate-100 last:border-0 hover:bg-slate-50 ${
                    selectedRuleId === r.id ? 'bg-slate-50' : ''
                  }`}
                  onClick={() => selectRule(r.id)}
                >
                  <td className="py-2 pr-4 text-slate-700">{fmt(r.tpa_name)}</td>
                  <td className="py-2 pr-4 text-slate-700">{fmt(r.category)}</td>
                  <td className="py-2 pr-4 text-slate-700">{fmt(r.rule_type)}</td>
                  <td className="py-2 pr-4 font-semibold text-slate-900">{fmt(r.value_text || r.value)}</td>
                  <td className="py-2 pr-4 text-slate-700">{fmt(r.unit)}</td>
                  <td className="py-2 pr-4 tabular-nums text-slate-700">{fmt(r.confidence)}</td>
                  <td className="py-2 pr-2 text-slate-700">{fmt(r.source)}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={7} className="py-5 text-center text-sm text-slate-500">
                  No rules found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="mt-4 rounded-lg border border-slate-200 p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="text-xs font-semibold text-slate-700">Rule History</div>
          <div className="text-[11px] text-slate-500">{selectedRuleId ? `Rule: ${selectedRuleId}` : 'Select a rule'}</div>
        </div>

        {historyLoading ? <div className="mt-2 text-sm text-slate-500">Loading…</div> : null}
        {!historyLoading && selectedRuleId && !selectedEvents.length ? <div className="mt-2 text-sm text-slate-500">No history</div> : null}

        {selectedEvents.length ? (
          <div className="mt-2 max-h-[220px] space-y-2 overflow-auto pr-1 text-xs">
            {selectedEvents.map((e) => (
              <div key={e.id} className="rounded-md border border-slate-100 bg-slate-50 px-2 py-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="font-semibold text-slate-800">
                    v{fmt(e.from_version)} → v{fmt(e.to_version)}
                  </div>
                  <div className="text-[11px] text-slate-500">{fmt(e.changed_at)}</div>
                </div>
                <div className="mt-1 truncate text-[11px] text-slate-700">{JSON.stringify(e.diff || {})}</div>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  )
}
