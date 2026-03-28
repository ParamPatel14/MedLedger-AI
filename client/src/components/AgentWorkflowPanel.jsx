import { useMemo, useState } from 'react'
import { runAgentWorkflowTrace } from '../services/api'

function formatScore(value) {
  if (value === null || value === undefined) return '0.00'
  const n = Number(value)
  if (Number.isNaN(n)) return '0.00'
  return n.toFixed(2)
}

function pillColor(status) {
  const s = String(status || '').toLowerCase()
  if (s === 'ok') return 'bg-emerald-50 text-emerald-700 border-emerald-200'
  if (s === 'skipped') return 'bg-slate-50 text-slate-700 border-slate-200'
  return 'bg-rose-50 text-rose-700 border-rose-200'
}

function severityColor(severity) {
  const s = String(severity || '').toLowerCase()
  if (s === 'critical') return 'bg-rose-50 text-rose-700 border-rose-200'
  if (s === 'error') return 'bg-orange-50 text-orange-700 border-orange-200'
  if (s === 'warning') return 'bg-amber-50 text-amber-800 border-amber-200'
  return 'bg-slate-50 text-slate-700 border-slate-200'
}

function svmStatusColor(status) {
  const s = String(status || '').toLowerCase()
  if (s === 'pass') return 'bg-emerald-50 text-emerald-700 border-emerald-200'
  if (s === 'review') return 'bg-amber-50 text-amber-800 border-amber-200'
  if (s === 'escalated') return 'bg-rose-50 text-rose-700 border-rose-200'
  return 'bg-slate-50 text-slate-700 border-slate-200'
}

function decisionColor(decision) {
  const d = String(decision || '').toUpperCase()
  if (d === 'APPROVE') return 'bg-emerald-50 text-emerald-700 border-emerald-200'
  if (d === 'WARN') return 'bg-amber-50 text-amber-800 border-amber-200'
  if (d === 'ESCALATE') return 'bg-orange-50 text-orange-700 border-orange-200'
  if (d === 'BLOCK') return 'bg-rose-50 text-rose-700 border-rose-200'
  return 'bg-slate-50 text-slate-700 border-slate-200'
}

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

function renderTags(items, className) {
  const list = Array.isArray(items) ? items : []
  if (!list.length) {
    return <div className="text-xs text-slate-400">None</div>
  }
  return (
    <div className="flex flex-wrap gap-2">
      {list.map((item) => (
        <span
          key={String(item)}
          className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-medium ${className}`}
        >
          {String(item)}
        </span>
      ))}
    </div>
  )
}

export default function AgentWorkflowPanel() {
  const [text, setText] = useState('')
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

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

  const governanceIssues = useMemo(() => normalizeIssues(governance?.issues), [
    governance,
  ])
  const policyTriggered = useMemo(() => {
    return uniqStrings(
      governanceIssues
        .map((x) => x?.policy_id)
        .filter((x) => x !== null && x !== undefined),
    )
  }, [governanceIssues])
  const guardrailDetectors = useMemo(() => {
    return uniqStrings(
      governanceIssues
        .map((x) => x?.detector_id)
        .filter((x) => x !== null && x !== undefined),
    )
  }, [governanceIssues])
  const govCounts = useMemo(
    () => issueCounts(governanceIssues),
    [governanceIssues],
  )

  const decisionTimeline = useMemo(() => {
    const rows = []
    rows.push({
      step: 'Clinical',
      score: clinical?.confidence,
      decision: stageDecisionLabel(svm?.svm_after_clinical?.status),
      meta: svm?.svm_after_clinical?.status ? 'SVM after clinical' : '',
    })
    rows.push({
      step: 'Coding',
      score: coding?.confidence,
      decision: stageDecisionLabel(svm?.svm_after_coding?.status),
      meta: svm?.svm_after_coding?.status ? 'SVM after coding' : '',
    })
    rows.push({
      step: 'Rule',
      score: payer?.confidence,
      decision: stageDecisionLabel(svm?.svm_after_rules?.status),
      meta: payer ? (payer.is_valid ? 'Valid' : 'Invalid') : '',
    })
    rows.push({
      step: 'Policy',
      score: governance ? governanceIssues.length : null,
      decision:
        governanceIssues.length > 0
          ? String(
              governanceIssues.some((x) =>
                String(x?.severity || '').toLowerCase().includes('critical'),
              )
                ? 'VIOLATION'
                : 'FLAGGED',
            )
          : governance
            ? 'CLEAR'
            : '—',
      meta:
        policyTriggered.length || guardrailDetectors.length
          ? `${policyTriggered.length} policies, ${guardrailDetectors.length} detectors`
          : '',
    })
    rows.push({
      step: 'Decision',
      score: governance?.confidence,
      decision: String(governance?.decision || '—').toUpperCase(),
      meta: governance?.audit_id ? `Audit ${String(governance.audit_id).slice(0, 8)}` : '',
    })
    return rows
  }, [
    clinical,
    coding,
    payer,
    svm,
    governance,
    governanceIssues,
    policyTriggered,
    guardrailDetectors,
  ])

  const alertItems = useMemo(() => {
    const items = []
    if (governance?.refusal?.status === 'refused') {
      items.push({
        kind: 'refusal',
        severity: 'critical',
        title: 'Refusal',
        message: governance?.refusal?.message || 'Insufficient information. Cannot proceed.',
      })
    }
    if (governance?.escalation?.status === 'escalated') {
      items.push({
        kind: 'escalation',
        severity: 'warning',
        title: 'Escalation',
        message: governance?.escalation?.reason || 'Escalated to human review',
      })
    }
    for (const it of governanceIssues.slice(0, 10)) {
      items.push({
        kind: it?.type || 'issue',
        severity: it?.severity || 'warning',
        title: String(it?.type || 'issue'),
        message: String(it?.message || ''),
      })
    }
    return items
  }, [governance, governanceIssues])

  return (
    <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-base font-semibold text-slate-800">
            Agentic Coding Workflow
          </div>
          <p className="text-xs text-slate-500">
            Clinical → SVM → Coding → SVM → Rule → SVM → Governance, with guardrails and audit.
          </p>
        </div>
        {result?.record_id && (
          <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[11px] text-slate-600">
            Record {String(result.record_id).slice(0, 8)}
          </span>
        )}
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
          <label className="text-xs font-semibold text-slate-600">
            Clinical text
          </label>
          <textarea
            className="mt-2 w-full rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-800 outline-none focus:ring-2 focus:ring-sky-200"
            rows={6}
            value={text}
            placeholder="Paste clinical note text here…"
            onChange={(e) => setText(e.target.value)}
          />
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button
              type="button"
              className={`btn btnPrimary text-white ${status === 'loading' ? 'opacity-70 pointer-events-none' : ''}`}
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
              {status === 'loading' ? 'Running…' : 'Run Agent Workflow'}
            </button>
            <button
              type="button"
              className="btn btnGhost"
              onClick={() => {
                setText('')
                setResult(null)
                setError(null)
                setStatus('idle')
              }}
            >
              Reset
            </button>
          </div>
          {error && (
            <div className="mt-3 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700">
              {String(error)}
            </div>
          )}
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-3">
          <div className="flex items-center justify-between gap-3">
            <div className="text-sm font-semibold text-slate-800">
              Agent Flow Visualization
            </div>
            <span className="text-xs text-slate-500">
              Final confidence: {formatScore(governance?.confidence ?? result?.confidence)}
            </span>
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2">
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
              const svmStatus =
                s.key.startsWith('svm_') && svm && typeof svm === 'object'
                  ? svm?.[s.key]?.status
                  : null
              return (
                <div key={s.key} className="flex items-center gap-2">
                  <div className="flex flex-col">
                    <span className="text-xs font-semibold text-slate-700">
                      {s.label}
                    </span>
                    <span
                      className={`inline-flex w-fit items-center rounded-full border px-2 py-0.5 text-[11px] ${pillColor(stepStatus)}`}
                    >
                      {String(stepStatus)}
                    </span>
                    {svmStatus ? (
                      <span
                        className={`mt-1 inline-flex w-fit items-center rounded-full border px-2 py-0.5 text-[11px] ${svmStatusColor(
                          svmStatus,
                        )}`}
                      >
                        {String(svmStatus)}
                      </span>
                    ) : null}
                    {s.key === 'governance' && governance?.decision ? (
                      <span
                        className={`mt-1 inline-flex w-fit items-center rounded-full border px-2 py-0.5 text-[11px] ${decisionColor(
                          governance.decision,
                        )}`}
                      >
                        {String(governance.decision).toUpperCase()}
                      </span>
                    ) : null}
                  </div>
                  {idx < arr.length - 1 && (
                    <span className="text-slate-300" aria-hidden="true">
                      →
                    </span>
                  )}
                </div>
              )
            })}
          </div>

          <div className="mt-4 rounded-lg border border-slate-200 bg-white p-3">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                  Confidence + Decision
                </div>
                <div className="mt-1 text-xs text-slate-600">
                  {governance?.reason ? String(governance.reason) : '—'}
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold ${decisionColor(
                    governance?.decision,
                  )}`}
                >
                  {governance?.decision ? String(governance.decision).toUpperCase() : '—'}
                </span>
                {governance?.audit_id ? (
                  <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[11px] text-slate-600">
                    Audit {String(governance.audit_id).slice(0, 8)}
                  </span>
                ) : null}
              </div>
            </div>

            <div className="mt-3 overflow-auto rounded-lg border border-slate-200">
              <table className="min-w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-600">
                  <tr>
                    <th className="px-3 py-2 font-semibold">Step</th>
                    <th className="px-3 py-2 font-semibold">Score</th>
                    <th className="px-3 py-2 font-semibold">Decision</th>
                    <th className="px-3 py-2 font-semibold">Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {decisionTimeline.map((r, i) => (
                    <tr key={`${r.step}-${i}`} className="border-t border-slate-100">
                      <td className="px-3 py-2 font-semibold text-slate-800 whitespace-nowrap">
                        {r.step}
                      </td>
                      <td className="px-3 py-2 text-slate-700">
                        {r.step === 'Policy'
                          ? r.score === null || r.score === undefined
                            ? '—'
                            : String(r.score)
                          : formatScore(r.score)}
                      </td>
                      <td className="px-3 py-2">
                        {r.step === 'Decision' ? (
                          <span
                            className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold ${decisionColor(
                              r.decision,
                            )}`}
                          >
                            {r.decision}
                          </span>
                        ) : (
                          <span className="inline-flex items-center rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-semibold text-slate-700">
                            {r.decision}
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-slate-600">{r.meta || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                  Guardrail Panel
                </div>
                <span className="text-[11px] text-slate-500">
                  Triggered: {policyTriggered.length + guardrailDetectors.length}
                </span>
              </div>
              <div className="mt-2">
                <div className="text-[11px] font-semibold text-slate-600">
                  Policies triggered
                </div>
                <div className="mt-2">
                  {renderTags(policyTriggered, 'bg-white text-slate-700 border-slate-200')}
                </div>
              </div>
              <div className="mt-3">
                <div className="text-[11px] font-semibold text-slate-600">
                  Edge detectors
                </div>
                <div className="mt-2">
                  {renderTags(guardrailDetectors, 'bg-white text-slate-700 border-slate-200')}
                </div>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-slate-600">
                <span className={`rounded-full border px-2 py-0.5 ${severityColor('critical')}`}>
                  critical {govCounts.critical}
                </span>
                <span className={`rounded-full border px-2 py-0.5 ${severityColor('error')}`}>
                  error {govCounts.error}
                </span>
                <span className={`rounded-full border px-2 py-0.5 ${severityColor('warning')}`}>
                  warning {govCounts.warning}
                </span>
              </div>
              <div className="mt-3">
                <div className="text-[11px] font-semibold text-slate-600">
                  Violations
                </div>
                {governanceIssues.length ? (
                  <div className="mt-2 space-y-2">
                    {governanceIssues.slice(0, 8).map((issue, i) => (
                      <div
                        key={`${issue?.policy_id || issue?.detector_id || issue?.type || 'issue'}-${i}`}
                        className={`rounded-lg border px-3 py-2 text-xs ${severityColor(issue?.severity)}`}
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="font-semibold">
                            {String(issue?.type || 'issue')}
                          </span>
                          <span className="text-[11px]">
                            {String(issue?.severity || 'warning')}
                          </span>
                        </div>
                        <div className="mt-1">{String(issue?.message || '')}</div>
                        {(issue?.policy_id || issue?.detector_id) && (
                          <div className="mt-2 text-[11px] text-slate-600">
                            {issue?.policy_id ? `policy: ${String(issue.policy_id)}` : ''}
                            {issue?.policy_id && issue?.detector_id ? ' • ' : ''}
                            {issue?.detector_id ? `detector: ${String(issue.detector_id)}` : ''}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="mt-2 text-xs text-slate-400">No violations</div>
                )}
              </div>
            </div>

            <div className="rounded-lg border border-slate-200 bg-white p-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                  Alert System
                </div>
                <span className="text-[11px] text-slate-500">
                  Alerts: {alertItems.length}
                </span>
              </div>
              {alertItems.length ? (
                <div className="mt-3 space-y-2">
                  {alertItems.slice(0, 10).map((a, i) => (
                    <div
                      key={`${a.kind}-${i}`}
                      className={`rounded-lg border px-3 py-2 text-xs ${severityColor(a.severity)}`}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-semibold">{String(a.title)}</span>
                        <span className="text-[11px]">{String(a.severity)}</span>
                      </div>
                      <div className="mt-1">{String(a.message)}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="mt-3 text-xs text-slate-400">No alerts</div>
              )}

              <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3">
                <div className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                  Decision Timeline
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  {[
                    'Clinical',
                    'Coding',
                    'SVM',
                    'Policy',
                    'Decision',
                  ].map((label, idx, arr) => (
                    <div key={label} className="flex items-center gap-2">
                      <span className="inline-flex items-center rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-700">
                        {label}
                      </span>
                      {idx < arr.length - 1 && (
                        <span className="text-slate-300" aria-hidden="true">
                          →
                        </span>
                      )}
                    </div>
                  ))}
                </div>
                <div className="mt-3 text-xs text-slate-600">
                  Clinical → SVM → Coding → SVM → Rule → SVM → Policy → Decision
                </div>
              </div>
            </div>
          </div>

          <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3">
            <div className="flex items-center justify-between gap-3">
              <div className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                Validation Status
              </div>
              <span
                className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold ${
                  payer?.is_valid
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                    : 'bg-rose-50 text-rose-700 border-rose-200'
                }`}
              >
                {payer ? (payer.is_valid ? 'Valid' : 'Invalid') : '—'}
              </span>
            </div>
            <div className="mt-2 text-xs text-slate-600">
              Rule confidence: {formatScore(payer?.confidence)}
            </div>
            {payer?.issues && payer.issues.length > 0 ? (
              <div className="mt-3 space-y-2">
                {payer.issues.slice(0, 8).map((issue, i) => (
                  <div
                    key={`${issue?.type || 'issue'}-${i}`}
                    className={`rounded-lg border px-3 py-2 text-xs ${severityColor(issue?.severity)}`}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-semibold">
                        {String(issue?.type || 'issue')}
                      </span>
                      <span className="text-[11px]">
                        {String(issue?.severity || 'warning')}
                      </span>
                    </div>
                    <div className="mt-1">{String(issue?.message || '')}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="mt-3 text-xs text-slate-400">No issues</div>
            )}
          </div>

          <div className="mt-4 rounded-lg border border-slate-200 bg-white p-3">
            <div className="flex items-center justify-between gap-3">
              <div className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                Semantic Verification (SVM)
              </div>
              <span
                className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold ${svmStatusColor(
                  result?.status,
                )}`}
              >
                {result?.status ? String(result.status) : '—'}
              </span>
            </div>
            {svmStages.length ? (
              <div className="mt-3 space-y-2">
                {svmStages.map((stage) => {
                  const stageStatus = stage?.data?.status
                  const stageConfidence = stage?.data?.confidence
                  const issues = Array.isArray(stage?.data?.issues)
                    ? stage.data.issues
                    : []
                  const claims = Array.isArray(stage?.data?.claims)
                    ? stage.data.claims
                    : []
                  const scores =
                    stage?.data?.scores && typeof stage.data.scores === 'object'
                      ? stage.data.scores
                      : {}
                  return (
                    <details
                      key={stage.key}
                      className="rounded-lg border border-slate-200 bg-slate-50 p-3"
                    >
                      <summary className="cursor-pointer select-none">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="text-xs font-semibold text-slate-800">
                            {String(stage.key)}
                          </span>
                          <div className="flex flex-wrap items-center gap-2">
                            <span
                              className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] ${svmStatusColor(
                                stageStatus,
                              )}`}
                            >
                              {stageStatus ? String(stageStatus) : '—'}
                            </span>
                            <span className="text-[11px] text-slate-500">
                              conf {formatScore(stageConfidence)}
                            </span>
                          </div>
                        </div>
                      </summary>
                      <div className="mt-3 grid gap-3 md:grid-cols-2">
                        <div>
                          <div className="text-[11px] font-semibold text-slate-600">
                            Scores
                          </div>
                          <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-slate-600">
                            <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5">
                              source {formatScore(scores?.source_alignment)}
                            </span>
                            <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5">
                              consistency {formatScore(scores?.consistency)}
                            </span>
                            <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5">
                              reason {formatScore(scores?.reasonability)}
                            </span>
                          </div>
                          <div className="mt-3 text-[11px] font-semibold text-slate-600">
                            Claims ({claims.length})
                          </div>
                          <div className="mt-2">
                            {renderTags(
                              claims.slice(0, 10).map((c) => {
                                const t = String(c?.type || '').trim()
                                const v = String(c?.value || '').trim()
                                if (!t && !v) return 'claim'
                                if (!t) return v
                                if (!v) return t
                                return `${t}: ${v}`
                              }),
                              'bg-white text-slate-700 border-slate-200',
                            )}
                          </div>
                        </div>
                        <div>
                          <div className="text-[11px] font-semibold text-slate-600">
                            Issues ({issues.length})
                          </div>
                          {issues.length ? (
                            <div className="mt-2 space-y-2">
                              {issues.slice(0, 6).map((issue, i) => (
                                <div
                                  key={`${issue?.type || 'issue'}-${i}`}
                                  className={`rounded-lg border px-3 py-2 text-xs ${severityColor(
                                    issue?.severity,
                                  )}`}
                                >
                                  <div className="flex flex-wrap items-center justify-between gap-2">
                                    <span className="font-semibold">
                                      {String(issue?.type || 'issue')}
                                    </span>
                                    <span className="text-[11px]">
                                      {String(issue?.severity || 'warning')}
                                    </span>
                                  </div>
                                  <div className="mt-1">
                                    {String(issue?.message || '')}
                                  </div>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <div className="mt-2 text-xs text-slate-400">
                              No issues
                            </div>
                          )}
                        </div>
                      </div>
                    </details>
                  )
                })}
              </div>
            ) : (
              <div className="mt-3 text-xs text-slate-400">
                No SVM results
              </div>
            )}
          </div>
        </div>
      </div>

      {result && (
        <div className="mt-4 grid gap-3 lg:grid-cols-3">
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="text-sm font-semibold text-slate-800">
                Clinical Agent Output
              </div>
              <span className="text-xs text-slate-500">
                {formatScore(clinical?.confidence)}
              </span>
            </div>
            <div className="mt-3">
              <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
                Diagnosis extracted
              </div>
              {renderTags(
                clinical?.diagnosis,
                'bg-red-50 text-red-700 border-red-200',
              )}
            </div>
            <div className="mt-4">
              <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
                Procedures extracted
              </div>
              {renderTags(
                clinical?.procedures,
                'bg-sky-50 text-sky-700 border-sky-200',
              )}
            </div>
            {clinical?.explanation && (
              <div className="mt-4 text-xs text-slate-600">
                {String(clinical.explanation)}
              </div>
            )}
          </div>

          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="text-sm font-semibold text-slate-800">
                Coding Agent Output
              </div>
              <span className="text-xs text-slate-500">
                {formatScore(coding?.confidence)}
              </span>
            </div>
            <div className="mt-2 text-xs text-slate-600">
              {coding?.mapping_reason ? String(coding.mapping_reason) : '—'}
            </div>
            <div className="mt-3 overflow-auto rounded-lg border border-slate-200">
              <table className="min-w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-600">
                  <tr>
                    <th className="px-3 py-2 font-semibold">Code</th>
                    <th className="px-3 py-2 font-semibold">Description</th>
                    <th className="px-3 py-2 font-semibold">Score</th>
                    <th className="px-3 py-2 font-semibold">Source</th>
                  </tr>
                </thead>
                <tbody>
                  {icdCodes.length ? (
                    icdCodes.slice(0, 10).map((c, i) => (
                      <tr
                        key={`${c?.code || 'code'}-${i}`}
                        className="border-t border-slate-100"
                      >
                        <td className="px-3 py-2 whitespace-nowrap font-semibold text-slate-800">
                          {String(c?.code || '')}
                        </td>
                        <td className="px-3 py-2 text-slate-700">
                          {String(c?.description || '')}
                        </td>
                        <td className="px-3 py-2 text-slate-700">
                          {formatScore(c?.score)}
                          {c?.is_uncertain ? (
                            <span className="ml-2 inline-flex items-center rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-800">
                              Uncertain
                            </span>
                          ) : null}
                        </td>
                        <td className="px-3 py-2 text-slate-600">
                          {String(c?.source_text || '')}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr className="border-t border-slate-100">
                      <td
                        className="px-3 py-3 text-slate-400"
                        colSpan={4}
                      >
                        No codes
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="text-sm font-semibold text-slate-800">
                Rule Agent Output
              </div>
              <span className="text-xs text-slate-500">
                {formatScore(payer?.confidence)}
              </span>
            </div>
            <div className="mt-3">
              <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
                Validation status
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold ${
                    payer?.is_valid
                      ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                      : 'bg-rose-50 text-rose-700 border-rose-200'
                  }`}
                >
                  {payer ? (payer.is_valid ? 'Valid' : 'Invalid') : '—'}
                </span>
                <span className="text-xs text-slate-600">
                  Overall: {formatScore(result?.confidence)}
                </span>
              </div>
            </div>
            <div className="mt-4">
              <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
                Issues
              </div>
              {payer?.issues && payer.issues.length > 0 ? (
                <div className="space-y-2">
                  {payer.issues.slice(0, 8).map((issue, i) => (
                    <div
                      key={`${issue?.type || 'issue'}-${i}`}
                      className={`rounded-lg border px-3 py-2 text-xs ${severityColor(issue?.severity)}`}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-semibold">
                          {String(issue?.type || 'issue')}
                        </span>
                        <span className="text-[11px]">
                          {String(issue?.severity || 'warning')}
                        </span>
                      </div>
                      <div className="mt-1">{String(issue?.message || '')}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-xs text-slate-400">No issues</div>
              )}
            </div>
          </div>
        </div>
      )}

      {result && (
        <details className="mt-4 group">
          <summary className="text-xs font-medium text-slate-500 cursor-pointer hover:text-sky-600 transition-colors">
            View Raw Trace JSON
          </summary>
          <pre className="mt-2 overflow-auto rounded-lg border border-slate-200 bg-slate-50 p-3 text-[11px] text-slate-700">
            {JSON.stringify(result, null, 2)}
          </pre>
        </details>
      )}
    </div>
  )
}
