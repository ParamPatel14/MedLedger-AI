import { useCallback, useEffect, useMemo, useState } from 'react'
import { History, Search } from 'lucide-react'
import { getRuleHistory, listRules } from '../services/api'
import { Button } from './ui/button'

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

  const inputStyle = {
    width: '100%',
    borderRadius: 'var(--radius-sm)',
    border: '1px solid var(--border)',
    background: 'var(--surface)',
    padding: '8px 12px',
    fontSize: 13,
    color: 'var(--text)',
    outline: 'none',
    boxSizing: 'border-box',
  }

  return (
    <div className="panel">
      <div className="panelHead">
        <div>
          <div className="panelHeadTitle">Rule Explorer</div>
          <div className="panelHeadSub">Search and inspect payer rules by TPA and category.</div>
        </div>
      </div>
      <div className="panelBody">

        {/* Search form */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: 12, alignItems: 'end', marginBottom: 16 }}>
          <div>
            <label style={{ display: 'block', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.4px', color: 'var(--text-muted)', marginBottom: 6 }}>TPA</label>
            <input
              value={tpa}
              onChange={(e) => setTpa(e.target.value)}
              placeholder="e.g., ACME"
              style={inputStyle}
              onKeyDown={(e) => e.key === 'Enter' && runSearch()}
            />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.4px', color: 'var(--text-muted)', marginBottom: 6 }}>Category</label>
            <input
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              placeholder="e.g., room_rent"
              style={inputStyle}
              onKeyDown={(e) => e.key === 'Enter' && runSearch()}
            />
          </div>
          <Button onClick={runSearch} disabled={loading}>
            <Search size={13} />
            {loading ? 'Searching...' : 'Search'}
          </Button>
        </div>

        {error ? (
          <div style={{ marginBottom: 14, borderRadius: 6, border: '1px solid #FECACA', background: '#FEF2F2', padding: '8px 12px', fontSize: 12, color: '#991B1B' }}>
            {error}
          </div>
        ) : null}

        {/* Rules table */}
        <div style={{ overflowX: 'auto' }}>
          <table className="dataTable">
            <thead>
              <tr>
                <th>TPA</th>
                <th>Category</th>
                <th>Type</th>
                <th>Value</th>
                <th>Unit</th>
                <th>Confidence</th>
                <th>Source</th>
              </tr>
            </thead>
            <tbody>
              {items.length ? (
                items.map((r) => (
                  <tr
                    key={r.id}
                    style={{ cursor: 'pointer', background: selectedRuleId === r.id ? 'var(--primary-light)' : undefined }}
                    onClick={() => selectRule(r.id)}
                  >
                    <td>{fmt(r.tpa_name)}</td>
                    <td>{fmt(r.category)}</td>
                    <td>{fmt(r.rule_type)}</td>
                    <td style={{ fontWeight: 600 }}>{fmt(r.value_text || r.value)}</td>
                    <td>{fmt(r.unit)}</td>
                    <td style={{ fontVariantNumeric: 'tabular-nums' }}>{fmt(r.confidence)}</td>
                    <td>{fmt(r.source)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '20px 0' }}>
                    No rules found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Rule history panel */}
        <div style={{ marginTop: 16, border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: 'var(--surface-2)', padding: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 10 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
              <History size={13} style={{ color: 'var(--primary)' }} />
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-strong)' }}>Rule History</div>
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              {selectedRuleId ? `Rule: ${selectedRuleId}` : 'Select a row above'}
            </div>
          </div>

          {historyLoading ? (
            <div style={{ fontSize: 13, color: 'var(--text-muted)', padding: '8px 0' }}>Loading...</div>
          ) : null}
          {!historyLoading && selectedRuleId && !selectedEvents.length ? (
            <div style={{ fontSize: 13, color: 'var(--text-muted)', padding: '8px 0' }}>No history found</div>
          ) : null}

          {selectedEvents.length ? (
            <div style={{ maxHeight: 220, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 8 }}>
              {selectedEvents.map((e) => (
                <div key={e.id} style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', background: 'var(--surface)', padding: '8px 12px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-strong)' }}>
                      v{fmt(e.from_version)} &rarr; v{fmt(e.to_version)}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{fmt(e.changed_at)}</div>
                  </div>
                  <div style={{ marginTop: 4, fontSize: 11, color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {JSON.stringify(e.diff || {})}
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </div>

      </div>
    </div>
  )
}
