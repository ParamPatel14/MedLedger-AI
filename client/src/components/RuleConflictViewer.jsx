import { useCallback, useEffect, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { getRuleConflicts } from '../services/api'
import { Button } from './ui/button'

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
    <div className="panel">
      <div className="panelHead">
        <div>
          <div className="panelHeadTitle">Conflicting Rules</div>
          <div className="panelHeadSub">Groups of rules with conflicting values for the same TPA and category.</div>
        </div>
        <Button variant="outline" size="sm" onClick={refresh} disabled={loading}>
          <RefreshCw size={13} />
          {loading ? 'Refreshing…' : 'Refresh'}
        </Button>
      </div>
      <div className="panelBody">

      {error ? <div style={{ marginBottom: 14, borderRadius: 6, border: '1px solid #FECACA', background: '#FEF2F2', padding: '8px 12px', fontSize: 12, color: '#991B1B' }}>{error}</div> : null}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {groups.length ? (
          groups.map((g, idx) => (
            <div key={`${g.tpa_name}-${g.category}-${g.rule_type}-${idx}`} style={{ border: '1px solid #FDE68A', borderRadius: 'var(--radius)', background: '#FFFBEB', overflow: 'hidden' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', borderBottom: '1px solid #FDE68A', background: '#FEF3C7' }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-strong)' }}>
                  {fmt(g.tpa_name)} · {fmt(g.category)} · {fmt(g.rule_type)}
                </span>
                <span style={{ fontSize: 11, fontWeight: 600, color: '#92400E', background: '#FDE68A', borderRadius: 4, padding: '2px 8px' }}>{fmt(g.reason || 'potential_conflict')}</span>
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table className="dataTable" style={{ background: 'transparent' }}>
                  <thead>
                    <tr style={{ background: 'transparent' }}>
                      <th>Value</th><th>Unit</th><th>Confidence</th><th>Conditions</th><th>Source</th><th>Updated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(Array.isArray(g.rules) ? g.rules : []).map((r) => (
                      <tr key={r.id}>
                        <td style={{ fontWeight: 600 }}>{fmt(r.value_text || r.value)}</td>
                        <td>{fmt(r.unit)}</td>
                        <td style={{ fontVariantNumeric: 'tabular-nums' }}>{fmt(r.confidence)}</td>
                        <td style={{ maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{JSON.stringify(r.conditions || {})}</td>
                        <td>{fmt(r.source)}</td>
                        <td style={{ color: 'var(--text-muted)' }}>{fmt(r.updated_at || '')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))
        ) : (
          <div style={{ fontSize: 13, color: 'var(--text-muted)', padding: '8px 0' }}>No conflicts detected.</div>
        )}
      </div>
      </div>
    </div>
  )
}

