import { useEffect, useMemo, useState } from 'react'
import { Activity, ChevronDown, ChevronUp, GitBranch, Play, RotateCcw, ShieldCheck } from 'lucide-react'
import { runAgentWorkflowTrace } from '../services/api'
import { Button } from './ui/button'

function formatScore(value) {
  if (value === null || value === undefined) return '0.00'
  const n = Number(value)
  if (Number.isNaN(n)) return '0.00'
  return n.toFixed(2)
}

/* ── Inline style helpers (replaces Tailwind color classes) ── */
function pillStyle(status) {
  const s = String(status || '').toLowerCase()
  if (s === 'ok') return { background: '#D1FAE5', color: '#065F46', border: '1px solid #A7F3D0' }
  if (s === 'skipped') return { background: 'var(--surface-2)', color: 'var(--text-muted)', border: '1px solid var(--border)' }
  return { background: '#FEF2F2', color: '#991B1B', border: '1px solid #FECACA' }
}

function severityStyle(severity) {
  const s = String(severity || '').toLowerCase()
  if (s === 'critical') return { background: '#FEF2F2', color: '#991B1B', border: '1px solid #FECACA' }
  if (s === 'error') return { background: '#FFF7ED', color: '#C2410C', border: '1px solid #FED7AA' }
  if (s === 'warning') return { background: '#FFFBEB', color: '#92400E', border: '1px solid #FDE68A' }
  return { background: 'var(--surface-2)', color: 'var(--text-muted)', border: '1px solid var(--border)' }
}

function svmStyle(status) {
  const s = String(status || '').toLowerCase()
  if (s === 'pass') return { background: '#D1FAE5', color: '#065F46', border: '1px solid #A7F3D0' }
  if (s === 'review') return { background: '#FFFBEB', color: '#92400E', border: '1px solid #FDE68A' }
  if (s === 'escalated') return { background: '#FEF2F2', color: '#991B1B', border: '1px solid #FECACA' }
  return { background: 'var(--surface-2)', color: 'var(--text-muted)', border: '1px solid var(--border)' }
}

function decisionStyle(decision) {
  const d = String(decision || '').toUpperCase()
  if (d === 'APPROVE') return { background: '#D1FAE5', color: '#065F46', border: '1px solid #A7F3D0' }
  if (d === 'WARN') return { background: '#FFFBEB', color: '#92400E', border: '1px solid #FDE68A' }
  if (d === 'ESCALATE') return { background: '#FFF7ED', color: '#C2410C', border: '1px solid #FED7AA' }
  if (d === 'BLOCK') return { background: '#FEF2F2', color: '#991B1B', border: '1px solid #FECACA' }
  return { background: 'var(--surface-2)', color: 'var(--text-muted)', border: '1px solid var(--border)' }
}

const pillBase = { display: 'inline-flex', alignItems: 'center', borderRadius: 20, padding: '2px 10px', fontSize: 11, fontWeight: 600 }

function normalizeIssues(items) {
  const list = Array.isArray(items) ? items : []
  return list.filter((x) => x && typeof x === 'object')
}

function issueCounts(issues) {
  const list = normalizeIssues(issues)
  const counts = { critical: 0, error: 0, warning: 0, info: 0, other: 0 }
  for (const it of list) {
    const s = String(it?.severity || '').toLowerCase()
    if (s === 'critical') counts.critical += 1
    else if (s === 'error') counts.error += 1
    else if (s === 'warning') counts.warning += 1
    else if (s === 'info') counts.info += 1
    else counts.other += 1
  }
  return counts
}

function uniqStrings(items) {
  const list = Array.isArray(items) ? items : []
  const seen = new Set()
  const out = []
  for (const x of list) {
    const s = String(x || '').trim()
    if (!s) continue
    if (seen.has(s)) continue
    seen.add(s)
    out.push(s)
  }
  return out
}

function stageDecisionLabel(status) {
  const s = String(status || '').toLowerCase()
  if (s === 'pass') return 'PASS'
  if (s === 'review') return 'WARN'
  if (s === 'escalated') return 'ESCALATE'
  return '—'
}

function TagList({ items, style: tagStyle }) {
  const list = Array.isArray(items) ? items : []
  if (!list.length) return <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>None</div>
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
      {list.map((item) => (
        <span key={String(item)} style={{ ...pillBase, ...tagStyle }}>
          {String(item)}
        </span>
      ))}
    </div>
  )
}

function IssueCard({ issue, i }) {
  const style = severityStyle(issue?.severity)
  return (
    <div key={`${issue?.policy_id || issue?.detector_id || issue?.type || 'issue'}-${i}`}
      style={{ ...style, borderRadius: 6, padding: '8px 12px', fontSize: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
        <span style={{ fontWeight: 600 }}>{String(issue?.type || 'issue')}</span>
        <span style={{ fontSize: 11 }}>{String(issue?.severity || 'warning')}</span>
      </div>
      <div style={{ marginTop: 4 }}>{String(issue?.message || '')}</div>
      {(issue?.policy_id || issue?.detector_id) && (
        <div style={{ marginTop: 6, fontSize: 11, opacity: 0.75 }}>
          {issue?.policy_id ? `policy: ${String(issue.policy_id)}` : ''}
          {issue?.policy_id && issue?.detector_id ? ' \u2022 ' : ''}
          {issue?.detector_id ? `detector: ${String(issue.detector_id)}` : ''}
        </div>
      )}
    </div>
  )
}

export default function AgentWorkflowPanel({
  view = 'full',
  externalResult = null,
  externalText = '',
  hideControls = false,
  title = 'Agentic Coding Workflow',
}) {
  const [text, setText] = useState(String(externalText || ''))
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState(null)
  const [result, setResult] = useState(externalResult)
  const [rawOpen, setRawOpen] = useState(false)

  useEffect(() => {
    if (!hideControls) return
    setText(String(externalText || ''))
  }, [externalText, hideControls])

  useEffect(() => {
    if (!externalResult) return
    setResult(externalResult)
    setError(null)
    setStatus('done')
  }, [externalResult])

  const showOutputs = view === 'full' || view === 'flow'
  const showVerification = view === 'full' || view === 'verification'

  const flow = useMemo(() => {
    const f = result?.flow
    return Array.isArray(f) ? f : []
  }, [result])

  const clinical = result?.clinical || null
  const coding = result?.coding || null
  const payer = result?.payer || null
  const svm = result?.svm || null
  const governance = result?.governance || null

  const svmStages = useMemo(() => {
    if (!svm || typeof svm !== 'object') return []
    const order = ['svm_after_clinical', 'svm_after_coding', 'svm_after_rules']
    return order
      .map((key) => ({ key, data: svm?.[key] }))
      .filter((x) => x.data && typeof x.data === 'object')
  }, [svm])

  const icdCodes = useMemo(() => {
    const list = coding?.icd_codes
    return Array.isArray(list) ? list : []
  }, [coding])

  const governanceIssues = useMemo(() => normalizeIssues(governance?.issues), [governance])
  const policyTriggered = useMemo(() => uniqStrings(governanceIssues.map((x) => x?.policy_id).filter((x) => x !== null && x !== undefined)), [governanceIssues])
  const guardrailDetectors = useMemo(() => uniqStrings(governanceIssues.map((x) => x?.detector_id).filter((x) => x !== null && x !== undefined)), [governanceIssues])
  const govCounts = useMemo(() => issueCounts(governanceIssues), [governanceIssues])

  const decisionTimeline = useMemo(() => {
    const rows = []
    rows.push({ step: 'Clinical', score: clinical?.confidence, decision: stageDecisionLabel(svm?.svm_after_clinical?.status), meta: svm?.svm_after_clinical?.status ? 'SVM after clinical' : '' })
    rows.push({ step: 'Coding', score: coding?.confidence, decision: stageDecisionLabel(svm?.svm_after_coding?.status), meta: svm?.svm_after_coding?.status ? 'SVM after coding' : '' })
    rows.push({ step: 'Rule', score: payer?.confidence, decision: stageDecisionLabel(svm?.svm_after_rules?.status), meta: payer ? (payer.is_valid ? 'Valid' : 'Invalid') : '' })
    rows.push({
      step: 'Policy',
      score: governance ? governanceIssues.length : null,
      decision: governanceIssues.length > 0 ? String(governanceIssues.some((x) => String(x?.severity || '').toLowerCase().includes('critical')) ? 'VIOLATION' : 'FLAGGED') : governance ? 'CLEAR' : '—',
      meta: policyTriggered.length || guardrailDetectors.length ? `${policyTriggered.length} policies, ${guardrailDetectors.length} detectors` : '',
    })
    rows.push({ step: 'Decision', score: governance?.confidence, decision: String(governance?.decision || '—').toUpperCase(), meta: governance?.audit_id ? `Audit ${String(governance.audit_id).slice(0, 8)}` : '' })
    return rows
  }, [clinical, coding, payer, svm, governance, governanceIssues, policyTriggered, guardrailDetectors])

  const alertItems = useMemo(() => {
    const items = []
    if (governance?.refusal?.status === 'refused') items.push({ kind: 'refusal', severity: 'critical', title: 'Refusal', message: governance?.refusal?.message || 'Insufficient information. Cannot proceed.' })
    if (governance?.escalation?.status === 'escalated') items.push({ kind: 'escalation', severity: 'warning', title: 'Escalation', message: governance?.escalation?.reason || 'Escalated to human review' })
    for (const it of governanceIssues.slice(0, 10)) items.push({ kind: it?.type || 'issue', severity: it?.severity || 'warning', title: String(it?.type || 'issue'), message: String(it?.message || '') })
    return items
  }, [governance, governanceIssues])

  return (
    <div className="panel">
      <div className="panelHead">
        <div>
          <div className="panelHeadTitle">{String(title || 'Agentic Coding Workflow')}</div>
          <div className="panelHeadSub">Clinical &rarr; SVM &rarr; Coding &rarr; SVM &rarr; Rule &rarr; SVM &rarr; Governance, with guardrails and audit.</div>
        </div>
        {result?.record_id && (
          <span style={{ fontSize: 11, color: 'var(--text-muted)', background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 20, padding: '3px 10px' }}>
            Record {String(result.record_id).slice(0, 8)}
          </span>
        )}
      </div>
      <div className="panelBody">

        {/* Input + Flow row */}
        <div style={{ display: 'grid', gridTemplateColumns: hideControls ? '1fr' : '1fr 1fr', gap: 14 }}>

          {!hideControls ? (
            <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: 'var(--surface-2)', padding: 14 }}>
              <label style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.4px', color: 'var(--text-muted)' }}>
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
                    try {
                      const data = await runAgentWorkflowTrace(payload)
                      setResult(data)
                      setStatus('done')
                    } catch (e) {
                      setError(e?.message || 'Request failed')
                      setStatus('error')
                    }
                  }}
                >
                  <Play size={13} />
                  {status === 'loading' ? 'Running...' : 'Run Agent Workflow'}
                </Button>
                <Button variant="outline" size="sm" onClick={() => { setText(''); setResult(null); setError(null); setStatus('idle') }}>
                  <RotateCcw size={12} />
                  Reset
                </Button>
              </div>
              {error && (
                <div style={{ marginTop: 10, borderRadius: 6, border: '1px solid #FECACA', background: '#FEF2F2', padding: '8px 12px', fontSize: 12, color: '#991B1B' }}>
                  {String(error)}
                </div>
              )}
            </div>
          ) : null}

          {/* Agent flow visualization */}
          <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: 'var(--surface)', padding: 14 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                <GitBranch size={13} style={{ color: 'var(--primary)' }} />
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-strong)' }}>Agent Flow</div>
              </div>
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                Final confidence: {formatScore(governance?.confidence ?? result?.confidence)}
              </span>
            </div>

            <div style={{ overflowX: 'auto', paddingBottom: 4 }}>
              <div style={{ display: 'flex', flexWrap: 'nowrap', alignItems: 'center', gap: 8, minWidth: 'max-content' }}>
                {[
                  { key: 'clinical', label: 'Clinical' },
                  { key: 'svm_after_clinical', label: 'SVM' },
                  { key: 'coding', label: 'Coding' },
                  { key: 'svm_after_coding', label: 'SVM' },
                  { key: 'rule', label: 'Rule' },
                  { key: 'svm_after_rules', label: 'SVM' },
                  { key: 'governance', label: 'Governance' },
                ].map((s, idx, arr) => {
                  const step = flow.find((x) => x?.agent === s.key)
                  const stepStatus = step?.status || (result ? 'skipped' : 'idle')
                  const svmStatus = s.key.startsWith('svm_') && svm && typeof svm === 'object' ? svm?.[s.key]?.status : null
                  return (
                    <div key={s.key} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, alignItems: 'flex-start' }}>
                        <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-strong)', textTransform: 'uppercase', letterSpacing: '0.3px' }}>
                          {s.label}
                        </span>
                        <span style={{ ...pillBase, ...pillStyle(stepStatus) }}>
                          {String(stepStatus)}
                        </span>
                        {svmStatus ? (
                          <span style={{ ...pillBase, ...svmStyle(svmStatus) }}>
                            {String(svmStatus)}
                          </span>
                        ) : null}
                        {s.key === 'governance' && governance?.decision ? (
                          <span style={{ ...pillBase, ...decisionStyle(governance.decision) }}>
                            {String(governance.decision).toUpperCase()}
                          </span>
                        ) : null}
                      </div>
                      {idx < arr.length - 1 && (
                        <span style={{ color: 'var(--text-muted)', fontSize: 16 }} aria-hidden="true">&rarr;</span>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Decision table */}
            <div style={{ marginTop: 14 }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 10 }}>
                <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-muted)' }}>
                  Confidence + Decision
                </div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                  <span style={{ ...pillBase, ...decisionStyle(governance?.decision) }}>
                    {governance?.decision ? String(governance.decision).toUpperCase() : '—'}
                  </span>
                  {governance?.audit_id ? (
                    <span style={{ fontSize: 11, color: 'var(--text-muted)', background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 20, padding: '3px 10px' }}>
                      Audit {String(governance.audit_id).slice(0, 8)}
                    </span>
                  ) : null}
                </div>
              </div>
              {governance?.reason ? (
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 10 }}>{String(governance.reason)}</div>
              ) : null}
              <table className="dataTable">
                <thead>
                  <tr>
                    <th>Step</th>
                    <th>Score</th>
                    <th>Decision</th>
                    <th>Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {decisionTimeline.map((r, i) => (
                    <tr key={`${r.step}-${i}`}>
                      <td style={{ fontWeight: 600 }}>{r.step}</td>
                      <td style={{ fontVariantNumeric: 'tabular-nums' }}>
                        {r.step === 'Policy' ? (r.score === null || r.score === undefined ? '—' : String(r.score)) : formatScore(r.score)}
                      </td>
                      <td>
                        {r.step === 'Decision' ? (
                          <span style={{ ...pillBase, ...decisionStyle(r.decision) }}>{r.decision}</span>
                        ) : (
                          <span style={{ ...pillBase, background: 'var(--surface-2)', color: 'var(--text)', border: '1px solid var(--border)' }}>{r.decision}</span>
                        )}
                      </td>
                      <td style={{ color: 'var(--text-muted)' }}>{r.meta || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Verification panels */}
        {showVerification ? (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginTop: 14 }}>
            {/* Guardrail panel */}
            <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: 'var(--surface-2)', padding: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                  <ShieldCheck size={13} style={{ color: 'var(--primary)' }} />
                  <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-muted)' }}>Guardrail Panel</div>
                </div>
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Triggered: {policyTriggered.length + guardrailDetectors.length}</span>
              </div>

              <div style={{ marginBottom: 10 }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 6 }}>Policies triggered</div>
                <TagList items={policyTriggered} style={{ background: 'var(--surface)', color: 'var(--text)', border: '1px solid var(--border)' }} />
              </div>
              <div style={{ marginBottom: 10 }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 6 }}>Edge detectors</div>
                <TagList items={guardrailDetectors} style={{ background: 'var(--surface)', color: 'var(--text)', border: '1px solid var(--border)' }} />
              </div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
                {[['critical', govCounts.critical], ['error', govCounts.error], ['warning', govCounts.warning]].map(([sev, count]) => (
                  <span key={sev} style={{ ...pillBase, ...severityStyle(sev) }}>{sev} {count}</span>
                ))}
              </div>

              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 6 }}>Violations</div>
              {governanceIssues.length ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {governanceIssues.slice(0, 8).map((issue, i) => <IssueCard key={i} issue={issue} i={i} />)}
                </div>
              ) : (
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>No violations</div>
              )}
            </div>

            {/* Alert system */}
            <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: 'var(--surface)', padding: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                  <Activity size={13} style={{ color: 'var(--primary)' }} />
                  <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-muted)' }}>Alert System</div>
                </div>
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Alerts: {alertItems.length}</span>
              </div>

              {alertItems.length ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 14 }}>
                  {alertItems.slice(0, 10).map((a, i) => (
                    <div key={`${a.kind}-${i}`} style={{ ...severityStyle(a.severity), borderRadius: 6, padding: '8px 12px', fontSize: 12 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                        <span style={{ fontWeight: 600 }}>{String(a.title)}</span>
                        <span style={{ fontSize: 11 }}>{String(a.severity)}</span>
                      </div>
                      <div style={{ marginTop: 4 }}>{String(a.message)}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 14 }}>No alerts</div>
              )}

              <div style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: 12 }}>
                <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-muted)', marginBottom: 8 }}>Decision Timeline</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 6 }}>
                  {['Clinical', 'Coding', 'SVM', 'Policy', 'Decision'].map((label, idx, arr) => (
                    <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{ ...pillBase, background: 'var(--primary-light)', color: 'var(--primary)', border: '1px solid var(--primary-border)' }}>{label}</span>
                      {idx < arr.length - 1 && <span style={{ color: 'var(--text-muted)' }}>&rarr;</span>}
                    </div>
                  ))}
                </div>
                <div style={{ marginTop: 8, fontSize: 11, color: 'var(--text-muted)' }}>
                  Clinical &rarr; SVM &rarr; Coding &rarr; SVM &rarr; Rule &rarr; SVM &rarr; Policy &rarr; Decision
                </div>
              </div>
            </div>
          </div>
        ) : null}

        {/* Validation status */}
        {showVerification ? (
          <div style={{ marginTop: 14, border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: 'var(--surface-2)', padding: 14 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-muted)' }}>Validation Status</div>
              <span style={{ ...pillBase, ...(payer?.is_valid ? { background: '#D1FAE5', color: '#065F46', border: '1px solid #A7F3D0' } : { background: '#FEF2F2', color: '#991B1B', border: '1px solid #FECACA' }) }}>
                {payer ? (payer.is_valid ? 'Valid' : 'Invalid') : '—'}
              </span>
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>Rule confidence: {formatScore(payer?.confidence)}</div>
            {payer?.issues && payer.issues.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {payer.issues.slice(0, 8).map((issue, i) => <IssueCard key={i} issue={issue} i={i} />)}
              </div>
            ) : (
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>No issues</div>
            )}
          </div>
        ) : null}

        {/* SVM Stages */}
        {showVerification ? (
          <div style={{ marginTop: 14, border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: 'var(--surface)', padding: 14 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-muted)' }}>Semantic Verification (SVM)</div>
              <span style={{ ...pillBase, ...svmStyle(result?.status) }}>
                {result?.status ? String(result.status) : '—'}
              </span>
            </div>
            {svmStages.length ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {svmStages.map((stage) => {
                  const stageStatus = stage?.data?.status
                  const stageConf = stage?.data?.confidence
                  const issues = Array.isArray(stage?.data?.issues) ? stage.data.issues : []
                  const claims = Array.isArray(stage?.data?.claims) ? stage.data.claims : []
                  const scores = stage?.data?.scores && typeof stage.data.scores === 'object' ? stage.data.scores : {}
                  return (
                    <SvmStageItem
                      key={stage.key}
                      stage={stage}
                      stageStatus={stageStatus}
                      stageConf={stageConf}
                      issues={issues}
                      claims={claims}
                      scores={scores}
                    />
                  )
                })}
              </div>
            ) : (
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>No SVM results</div>
            )}
          </div>
        ) : null}

        {/* Agent outputs */}
        {result && showOutputs && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14, marginTop: 14 }}>
            {/* Clinical */}
            <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: 'var(--surface)', padding: 14 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-strong)' }}>Clinical Agent</div>
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{formatScore(clinical?.confidence)}</span>
              </div>
              <div style={{ marginBottom: 10 }}>
                <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-muted)', marginBottom: 6 }}>Diagnosis extracted</div>
                <TagList items={clinical?.diagnosis} style={{ background: '#FEF2F2', color: '#991B1B', border: '1px solid #FECACA' }} />
              </div>
              <div>
                <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-muted)', marginBottom: 6 }}>Procedures extracted</div>
                <TagList items={clinical?.procedures} style={{ background: '#EFF6FF', color: '#1D4ED8', border: '1px solid #BFDBFE' }} />
              </div>
              {clinical?.explanation && (
                <div style={{ marginTop: 10, fontSize: 12, color: 'var(--text-muted)' }}>{String(clinical.explanation)}</div>
              )}
            </div>

            {/* Coding */}
            <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: 'var(--surface)', padding: 14 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-strong)' }}>Coding Agent</div>
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{formatScore(coding?.confidence)}</span>
              </div>
              {coding?.mapping_reason && (
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 10 }}>{String(coding.mapping_reason)}</div>
              )}
              <table className="dataTable">
                <thead>
                  <tr>
                    <th>Code</th>
                    <th>Description</th>
                    <th>Score</th>
                    <th>Source</th>
                  </tr>
                </thead>
                <tbody>
                  {icdCodes.length ? (
                    icdCodes.slice(0, 10).map((c, i) => (
                      <tr key={`${c?.code || 'code'}-${i}`}>
                        <td style={{ fontWeight: 600, whiteSpace: 'nowrap' }}>{String(c?.code || '')}</td>
                        <td>{String(c?.description || '')}</td>
                        <td style={{ fontVariantNumeric: 'tabular-nums' }}>
                          {formatScore(c?.score)}
                          {c?.is_uncertain ? (
                            <span style={{ ...pillBase, marginLeft: 6, background: '#FFFBEB', color: '#92400E', border: '1px solid #FDE68A', fontSize: 10 }}>Uncertain</span>
                          ) : null}
                        </td>
                        <td style={{ color: 'var(--text-muted)' }}>{String(c?.source_text || '')}</td>
                      </tr>
                    ))
                  ) : (
                    <tr><td colSpan={4} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>No codes</td></tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Rule */}
            <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: 'var(--surface)', padding: 14 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-strong)' }}>Rule Agent</div>
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{formatScore(payer?.confidence)}</span>
              </div>
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-muted)', marginBottom: 6 }}>Validation Status</div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                  <span style={{ ...pillBase, ...(payer?.is_valid ? { background: '#D1FAE5', color: '#065F46', border: '1px solid #A7F3D0' } : { background: '#FEF2F2', color: '#991B1B', border: '1px solid #FECACA' }) }}>
                    {payer ? (payer.is_valid ? 'Valid' : 'Invalid') : '—'}
                  </span>
                  <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Overall: {formatScore(result?.confidence)}</span>
                </div>
              </div>
              <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-muted)', marginBottom: 6 }}>Issues</div>
              {payer?.issues && payer.issues.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {payer.issues.slice(0, 8).map((issue, i) => <IssueCard key={i} issue={issue} i={i} />)}
                </div>
              ) : (
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>No issues</div>
              )}
            </div>
          </div>
        )}

        {/* Raw JSON toggle */}
        {result && (
          <div style={{ marginTop: 14 }}>
            <button
              type="button"
              onClick={() => setRawOpen((v) => !v)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 12, color: 'var(--primary)', display: 'flex', alignItems: 'center', gap: 4, padding: 0 }}
            >
              {rawOpen ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
              {rawOpen ? 'Hide' : 'View'} Raw Trace JSON
            </button>
            {rawOpen && (
              <pre style={{ marginTop: 8, overflow: 'auto', borderRadius: 6, border: '1px solid var(--border)', background: 'var(--surface-2)', padding: '10px 12px', fontSize: 11, color: 'var(--text-muted)' }}>
                {JSON.stringify(result, null, 2)}
              </pre>
            )}
          </div>
        )}

      </div>
    </div>
  )
}

/* ── SVM stage collapsible ── */
function SvmStageItem({ stage, stageStatus, stageConf, issues, claims, scores }) {
  const [open, setOpen] = useState(false)
  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', background: 'var(--surface-2)', overflow: 'hidden' }}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{ width: '100%', background: 'none', border: 'none', cursor: 'pointer', padding: '10px 14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}
      >
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-strong)' }}>{String(stage.key)}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', borderRadius: 20, padding: '2px 10px', fontSize: 11, fontWeight: 600, ...svmStyle(stageStatus) }}>
            {stageStatus ? String(stageStatus) : '—'}
          </span>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>conf {formatScore(stageConf)}</span>
          {open ? <ChevronUp size={13} style={{ color: 'var(--text-muted)' }} /> : <ChevronDown size={13} style={{ color: 'var(--text-muted)' }} />}
        </div>
      </button>
      {open && (
        <div style={{ padding: '0 14px 14px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <div>
            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 6 }}>Scores</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {[['source', scores?.source_alignment], ['consistency', scores?.consistency], ['reason', scores?.reasonability]].map(([label, val]) => (
                <span key={label} style={{ fontSize: 11, background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 20, padding: '2px 8px', color: 'var(--text)' }}>
                  {label} {formatScore(val)}
                </span>
              ))}
            </div>
            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', marginTop: 10, marginBottom: 6 }}>Claims ({claims.length})</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {claims.slice(0, 10).map((c, i) => {
                const t = String(c?.type || '').trim()
                const v = String(c?.value || '').trim()
                const label = !t && !v ? 'claim' : !t ? v : !v ? t : `${t}: ${v}`
                return (
                  <span key={i} style={{ fontSize: 11, background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 20, padding: '2px 8px', color: 'var(--text)' }}>
                    {label}
                  </span>
                )
              })}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 6 }}>Issues ({issues.length})</div>
            {issues.length ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {issues.slice(0, 6).map((issue, i) => (
                  <div key={i} style={{ ...severityStyle(issue?.severity), borderRadius: 6, padding: '8px 10px', fontSize: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                      <span style={{ fontWeight: 600 }}>{String(issue?.type || 'issue')}</span>
                      <span style={{ fontSize: 11 }}>{String(issue?.severity || 'warning')}</span>
                    </div>
                    <div style={{ marginTop: 4 }}>{String(issue?.message || '')}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>No issues</div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
