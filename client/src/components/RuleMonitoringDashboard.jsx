import { useCallback, useEffect, useMemo, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { getRuleSummary, getRuleUpdates } from '../services/api'
import { Button } from './ui/button'

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
    <div className="panel">
      <div className="panelHead">
        <div>
          <div className="panelHeadTitle">Active Rules &amp; Recent Updates</div>
          <div className="panelHeadSub">Sync from web, email, or PDF sources.</div>
        </div>
        <Button variant="outline" size="sm" onClick={refresh} disabled={loading}>
          <RefreshCw size={13} />
          {loading ? 'Refreshing…' : 'Refresh'}
        </Button>
      </div>
      <div className="panelBody">

      {error ? <div style={{ marginBottom: 16, borderRadius: 6, border: '1px solid #FECACA', background: '#FEF2F2', padding: '8px 12px', fontSize: 12, color: '#991B1B' }}>{error}</div> : null}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14 }}>
        {/* Active rules card */}
        <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: 'var(--surface-2)', padding: 16 }}>
          <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-muted)', marginBottom: 6 }}>Active Rules</div>
          <div style={{ fontSize: 32, fontWeight: 800, color: 'var(--primary)', letterSpacing: '-0.8px', lineHeight: 1 }}>{numberOrZero(summary?.total_active)}</div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 12, marginBottom: 6, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.4px' }}>By Source</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {topSources.length ? topSources.map(([k, v]) => (
              <div key={k} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--text)' }}>
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--text-muted)' }}>{k || 'unknown'}</span>
                <span style={{ fontWeight: 700, color: 'var(--text-strong)', fontVariantNumeric: 'tabular-nums' }}>{v}</span>
              </div>
            )) : <div style={{ fontSize: 12, color: 'var(--text-subtle)' }}>No data</div>}
          </div>
        </div>

        {/* Top TPAs card */}
        <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: 'var(--surface-2)', padding: 16 }}>
          <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-muted)', marginBottom: 10 }}>Top TPAs</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {topTpas.length ? topTpas.map(([k, v]) => (
              <div key={k} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 12 }}>
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--text)', maxWidth: '70%' }}>{k || 'unknown'}</span>
                <span style={{ fontWeight: 700, color: 'var(--primary)', fontVariantNumeric: 'tabular-nums', background: 'var(--primary-light)', border: '1px solid var(--primary-border)', borderRadius: 4, padding: '1px 7px', fontSize: 11 }}>{v}</span>
              </div>
            )) : <div style={{ fontSize: 12, color: 'var(--text-subtle)' }}>No data</div>}
          </div>
        </div>

        {/* Recent updates card */}
        <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: 'var(--surface-2)', padding: 16 }}>
          <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-muted)', marginBottom: 10 }}>Recent Updates</div>
          <div style={{ maxHeight: 280, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 6 }}>
            {updates.length ? updates.map((u) => (
              <div key={u.id} style={{ border: '1px solid var(--border)', borderRadius: 6, padding: '8px 10px', background: 'white' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
                  <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-strong)' }}>{u.tpa_name || 'TPA'} · {u.category || 'category'}</span>
                  <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>v{numberOrZero(u.from_version)} → v{numberOrZero(u.to_version)}</span>
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{String(u.changed_at || '')}</div>
              </div>
            )) : <div style={{ fontSize: 12, color: 'var(--text-subtle)' }}>No updates found</div>}
          </div>
        </div>
      </div>
      </div>
    </div>
  )
}
