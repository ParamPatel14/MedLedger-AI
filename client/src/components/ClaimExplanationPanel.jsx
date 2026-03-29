import { useMemo, useState } from 'react'
import { Brain, ChevronDown, ChevronUp, FileSearch, RefreshCw, RotateCcw, ShieldCheck } from 'lucide-react'
import { getExplainabilityAudit, runClaimExplain } from '../services/api'
import { Button } from './ui/button'

function formatScore(value) {
  const n = Number(value)
  if (Number.isNaN(n)) return '0.00'
  return n.toFixed(2)
}

function decisionBadgeClass(decision) {
  const d = String(decision || '').toUpperCase()
  if (d === 'APPROVE') return 'statusBadge approved'
  if (d === 'WARN') return 'statusBadge query'
  if (d === 'ESCALATE') return 'statusBadge resubmitted'
  if (d === 'BLOCK') return 'statusBadge denied'
  return 'statusBadge'
}

function typeTitle(type) {
  const t = String(type || '').toLowerCase()
  if (t === 'clinical') return 'Diagnosis Reasoning'
  if (t === 'coding') return 'Code Assignment Logic'
  if (t === 'rule') return 'Rule Validation'
  if (t === 'policy') return 'Policy / Guardrails'
  if (t === 'svm') return 'Verification (Stages)'
  if (t === 'svm_verification') return 'Verification (Overall)'
  if (t === 'decision') return 'Decision'
  if (t === 'denial') return 'Denial / Refusal'
  return `Other (${t || 'unknown'})`
}

function ExplanationItem({ item }) {
  const [open, setOpen] = useState(false)
  const details = item?.details && typeof item.details === 'object' ? item.details : null
  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', background: 'var(--surface)', padding: '10px 12px', marginBottom: 6 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-strong)' }}>
          Confidence {formatScore(item?.confidence)}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{String(item?.type || '')}</span>
          {details ? (
            <button
              type="button"
              style={{ fontSize: 11, color: 'var(--primary)', background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 3, padding: 0 }}
              onClick={() => setOpen((v) => !v)}
            >
              {open ? <><ChevronUp size={11} />Hide</> : <><ChevronDown size={11} />Details</>}
            </button>
          ) : null}
        </div>
      </div>
      <div style={{ marginTop: 6, fontSize: 13, color: 'var(--text)' }}>
        {String(item?.explanation || '')}
      </div>
      {open && details ? (
        <pre style={{ marginTop: 8, maxHeight: 192, overflow: 'auto', borderRadius: 6, border: '1px solid var(--border)', background: 'var(--surface-2)', padding: '8px 10px', fontSize: 11, color: 'var(--text-muted)' }}>
          {JSON.stringify(details, null, 2)}
        </pre>
      ) : null}
    </div>
  )
}

function ExplanationList({ items }) {
  const list = Array.isArray(items) ? items : []
  if (!list.length) {
    return <div style={{ fontSize: 12, color: 'var(--text-muted)', padding: '6px 0' }}>No explanations available</div>
  }
  return (
    <div>
      {list.map((x, i) => <ExplanationItem key={`${x?.type || 'exp'}-${i}`} item={x} />)}
    </div>
  )
}

export default function ClaimExplanationPanel() {
  const [text, setText] = useState('')
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const [auditStatus, setAuditStatus] = useState('idle')
  const [auditError, setAuditError] = useState(null)
  const [audit, setAudit] = useState(null)

  const grouped = useMemo(() => {
    const exps = Array.isArray(result?.explanations) ? result.explanations : []
    const buckets = {}
    for (const x of exps) {
      const t = String(x?.type || '').toLowerCase()
      if (!t) continue
      if (!buckets[t]) buckets[t] = []
      buckets[t].push(x)
    }
    return buckets
  }, [result])

  const otherExplanations = useMemo(() => {
    const exps = Array.isArray(result?.explanations) ? result.explanations : []
    const keep = new Set(['clinical', 'coding', 'rule'])
    return exps.filter((x) => !keep.has(String(x?.type || '').toLowerCase()))
  }, [result])

  const otherByType = useMemo(() => {
    const buckets = {}
    for (const x of otherExplanations) {
      const t = String(x?.type || '').toLowerCase() || 'other'
      if (!buckets[t]) buckets[t] = []
      buckets[t].push(x)
    }
    const order = ['policy', 'svm_verification', 'svm', 'decision', 'denial', 'other']
    const keys = Object.keys(buckets)
    keys.sort((a, b) => {
      const ia = order.indexOf(a)
      const ib = order.indexOf(b)
      if (ia === -1 && ib === -1) return a.localeCompare(b)
      if (ia === -1) return 1
      if (ib === -1) return -1
      return ia - ib
    })
    return { buckets, keys }
  }, [otherExplanations])

  const traceSteps = useMemo(() => {
    const steps = result?.trace?.steps
    return Array.isArray(steps) ? steps : []
  }, [result])

  return (
    <div className="panel">
      <div className="panelHead">
        <div>
          <div className="panelHeadTitle">Claim Explanation Panel</div>
          <div className="panelHeadSub">Diagnosis reasoning, code assignment logic, and rule validation explanations.</div>
        </div>
        {result?.audit_id ? (
          <span style={{ fontSize: 11, color: 'var(--text-muted)', background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 20, padding: '3px 10px' }}>
            Audit {String(result.audit_id).slice(0, 8)}
          </span>
        ) : null}
      </div>
      <div className="panelBody">

        {/* Input + Decision row */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
          <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: 'var(--surface-2)', padding: 14 }}>
            <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.4px' }}>
              Clinical Text
            </label>
            <textarea
              style={{ marginTop: 8, width: '100%', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', background: 'var(--surface)', padding: '10px 12px', fontSize: 13, color: 'var(--text)', outline: 'none', resize: 'vertical', boxSizing: 'border-box' }}
              rows={6}
              value={text}
              placeholder="Paste clinical note text here..."
              onChange={(e) => setText(e.target.value)}
            />
            <div style={{ marginTop: 10, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              <Button
                disabled={status === 'loading'}
                onClick={async () => {
                  const payload = (text || '').trim()
                  if (!payload) return
                  setStatus('loading')
                  setError(null)
                  setResult(null)
                  setAudit(null)
                  setAuditError(null)
                  setAuditStatus('idle')
                  try {
                    const data = await runClaimExplain(payload)
                    setResult(data)
                    setStatus('done')
                  } catch (e) {
                    setError(e?.message || 'Request failed')
                    setStatus('error')
                  }
                }}
              >
                <Brain size={13} />
                {status === 'loading' ? 'Explaining...' : 'Explain Claim'}
              </Button>
              <Button variant="outline" size="sm" onClick={() => {
                setText('')
                setResult(null)
                setError(null)
                setStatus('idle')
                setAudit(null)
                setAuditError(null)
                setAuditStatus('idle')
              }}>
                <RotateCcw size={12} />
                Reset
              </Button>
              {result?.audit_id ? (
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={auditStatus === 'loading'}
                  onClick={async () => {
                    setAuditStatus('loading')
                    setAuditError(null)
                    setAudit(null)
                    try {
                      const data = await getExplainabilityAudit(result.audit_id)
                      setAudit(data)
                      setAuditStatus('done')
                    } catch (e) {
                      setAuditError(e?.message || 'Audit request failed')
                      setAuditStatus('error')
                    }
                  }}
                >
                  <FileSearch size={12} />
                  {auditStatus === 'loading' ? 'Loading...' : 'Load Audit JSON'}
                </Button>
              ) : null}
            </div>
            {error && (
              <div style={{ marginTop: 10, borderRadius: 6, border: '1px solid #FECACA', background: '#FEF2F2', padding: '8px 12px', fontSize: 12, color: '#991B1B' }}>
                {String(error)}
              </div>
            )}
            {auditError && (
              <div style={{ marginTop: 10, borderRadius: 6, border: '1px solid #FECACA', background: '#FEF2F2', padding: '8px 12px', fontSize: 12, color: '#991B1B' }}>
                {String(auditError)}
              </div>
            )}
          </div>

          <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: 'var(--surface)', padding: 14 }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-strong)' }}>Decision</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8 }}>
                <span className={decisionBadgeClass(result?.decision)}>
                  {result?.decision ? String(result.decision).toUpperCase() : '—'}
                </span>
                <span style={{ fontSize: 11, background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 20, padding: '3px 10px', color: 'var(--text-muted)' }}>
                  Conf {formatScore(result?.confidence)}
                </span>
              </div>
            </div>

            <div style={{ marginTop: 14 }}>
              <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-muted)', marginBottom: 8 }}>
                Trace
              </div>
              {traceSteps.length ? (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {traceSteps.slice(0, 8).map((s, i) => (
                    <span
                      key={`${s?.stage || 'step'}-${i}`}
                      style={{ fontSize: 11, background: 'var(--primary-light)', border: '1px solid var(--primary-border)', color: 'var(--primary)', borderRadius: 20, padding: '2px 10px' }}
                      title={String(s?.timestamp || '')}
                    >
                      {String(s?.stage || 'stage')}:{String(s?.status || '—')}
                    </span>
                  ))}
                </div>
              ) : (
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>No trace steps</div>
              )}
            </div>
          </div>
        </div>

        {/* Explanation buckets */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14, marginTop: 14 }}>
          {[
            { key: 'clinical', title: 'Diagnosis Reasoning', icon: Brain },
            { key: 'coding', title: 'Code Assignment Logic', icon: FileSearch },
            { key: 'rule', title: 'Rule Validation', icon: ShieldCheck },
          ].map(({ key, title, icon: Icon }) => (
            <div key={key} style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: 'var(--surface-2)', padding: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 10 }}>
                <Icon size={13} style={{ color: 'var(--primary)' }} />
                <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-muted)' }}>
                  {title}
                </div>
              </div>
              <ExplanationList items={grouped[key] || []} />
            </div>
          ))}
        </div>

        {otherExplanations.length ? (
          <div style={{ marginTop: 14, border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: 'var(--surface)', padding: 14 }}>
            <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-muted)', marginBottom: 12 }}>
              Additional Explanation Types
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              {otherByType.keys.map((k) => (
                <div key={k} style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', background: 'var(--surface-2)', padding: 12 }}>
                  <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-muted)', marginBottom: 8 }}>
                    {typeTitle(k)}
                  </div>
                  <ExplanationList items={otherByType.buckets[k]} />
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {audit ? (
          <div style={{ marginTop: 14, border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: 'var(--surface)', padding: 14 }}>
            <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-muted)', marginBottom: 8 }}>
              Audit JSON
            </div>
            <pre style={{ maxHeight: 288, overflow: 'auto', borderRadius: 6, border: '1px solid var(--border)', background: 'var(--surface-2)', padding: '10px 12px', fontSize: 11, color: 'var(--text-muted)' }}>
              {JSON.stringify(audit, null, 2)}
            </pre>
          </div>
        ) : null}

      </div>
    </div>
  )
}
