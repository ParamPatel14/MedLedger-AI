import { useEffect, useMemo, useState } from 'react'
import AgentWorkflowPanel from './AgentWorkflowPanel'
import {
  getOneClickWorkflow,
  overrideOneClickWorkflow,
  runPipelineText,
  startOneClickWorkflow,
  uploadClinicalDocument,
  uploadHandwrittenPrescription,
} from '../services/api'

export default function ClinicalExtractorPanel() {
  const [inputMode, setInputMode] = useState('text')
  const [pdfFile, setPdfFile] = useState(null)
  const [handwrittenFile, setHandwrittenFile] = useState(null)
  const [loadState, setLoadState] = useState('idle')
  const [clinicalText, setClinicalText] = useState('')
  const [nlpResult, setNlpResult] = useState(null)
  const [nlpState, setNlpState] = useState('idle')
  const [oneClickAuto, setOneClickAuto] = useState(true)
  const [insurerNumber, setInsurerNumber] = useState('')
  const [oneClickState, setOneClickState] = useState('idle')
  const [oneClickError, setOneClickError] = useState('')
  const [oneClickRunId, setOneClickRunId] = useState('')
  const [oneClickData, setOneClickData] = useState(null)

  const oneClickOutput = oneClickData?.output && typeof oneClickData.output === 'object' ? oneClickData.output : null
  const oneClickClinical = oneClickOutput?.clinical || null
  const oneClickCoding = oneClickOutput?.coding || null
  const oneClickPayer = oneClickOutput?.payer || null
  const oneClickSvm = oneClickOutput?.svm || null
  const oneClickGov = oneClickOutput?.governance || null
  const overrideUsed = Boolean(oneClickOutput?.override_guardrails)

  const svmOverall = useMemo(() => {
    const v1 = String(oneClickOutput?.svm_status || '').trim()
    if (v1) return v1.toLowerCase()
    const v2 = String(oneClickSvm?.summary?.overall || '').trim()
    if (v2) return v2.toLowerCase()
    return ''
  }, [oneClickOutput, oneClickSvm])

  const normalizedSvm = useMemo(() => {
    if (!oneClickSvm || typeof oneClickSvm !== 'object') {
      if (!svmOverall) return null
      return {
        svm_after_clinical: { status: svmOverall, scores: {}, decision: { status: svmOverall }, issues: [] },
        svm_after_coding: { status: svmOverall, scores: {}, decision: { status: svmOverall }, issues: [] },
        svm_after_rules: { status: svmOverall, scores: {}, decision: { status: svmOverall }, issues: [] },
      }
    }
    const keys = Object.keys(oneClickSvm || {})
    const hasStages = keys.some((k) => String(k).startsWith('svm_after_'))
    if (hasStages) return oneClickSvm
    if (!svmOverall) return oneClickSvm
    return {
      svm_after_clinical: { status: svmOverall, scores: {}, decision: { status: svmOverall }, issues: [] },
      svm_after_coding: { status: svmOverall, scores: {}, decision: { status: svmOverall }, issues: [] },
      svm_after_rules: { status: svmOverall, scores: {}, decision: { status: svmOverall }, issues: [] },
      summary: { overall: svmOverall },
    }
  }, [oneClickSvm, svmOverall])

  const oneClickTrace = useMemo(() => {
    if (!oneClickData || !oneClickOutput) return null
    const flow = [
      { agent: 'clinical', status: oneClickClinical ? 'ok' : 'skipped' },
      { agent: 'svm_after_clinical', status: normalizedSvm?.svm_after_clinical || svmOverall ? 'ok' : 'skipped' },
      { agent: 'coding', status: oneClickCoding ? 'ok' : 'skipped' },
      { agent: 'svm_after_coding', status: normalizedSvm?.svm_after_coding || svmOverall ? 'ok' : 'skipped' },
      { agent: 'rule', status: oneClickPayer ? 'ok' : 'skipped' },
      { agent: 'svm_after_rules', status: normalizedSvm?.svm_after_rules || svmOverall ? 'ok' : 'skipped' },
      { agent: 'governance', status: oneClickGov ? 'ok' : 'skipped' },
    ]
    return {
      record_id: oneClickData?.record_id || '',
      flow,
      clinical: oneClickClinical || null,
      coding: oneClickCoding || null,
      payer: oneClickPayer || null,
      svm: normalizedSvm || oneClickSvm || null,
      governance: oneClickGov || null,
      confidence: oneClickGov?.confidence ?? oneClickOutput?.confidence ?? 0,
      status: String(oneClickData?.status || 'idle'),
    }
  }, [
    oneClickData,
    oneClickOutput,
    oneClickClinical,
    oneClickCoding,
    oneClickPayer,
    oneClickSvm,
    oneClickGov,
    normalizedSvm,
    svmOverall,
  ])

  const pollOneClick = async (runId) => {
    if (!runId) return
    try {
      const data = await getOneClickWorkflow(runId)
      setOneClickData(data)
      const s = String(data?.status || '')
      if (s === 'done' || s === 'error' || s === 'needs_review') {
        setOneClickState('idle')
      }
    } catch (e) {
      setOneClickState('idle')
      setOneClickError(e?.message || 'Failed to fetch workflow status')
    }
  }

  const startOneClick = async (text, opts = {}) => {
    const payload = String(text || '').trim()
    if (!payload) return
    setOneClickError('')
    setOneClickData(null)
    setOneClickState('starting')
    try {
      const out = await startOneClickWorkflow({
        text: payload,
        insurerNumber: String(insurerNumber || '').trim(),
        autoCallIfNeeded: true,
        overrideGuardrails: Boolean(opts?.overrideGuardrails),
      })
      const rid = String(out?.run_id || '')
      setOneClickRunId(rid)
      setOneClickState('polling')
      await pollOneClick(rid)
    } catch (e) {
      setOneClickState('idle')
      setOneClickError(e?.message || 'Failed to start workflow')
    }
  }

  const overrideOneClick = async (runId) => {
    const rid = String(runId || '').trim()
    if (!rid) return
    setOneClickError('')
    setOneClickState('starting')
    try {
      const data = await overrideOneClickWorkflow(rid)
      setOneClickData(data)
      setOneClickState('polling')
      await pollOneClick(rid)
    } catch (e) {
      const msg = String(e?.message || '')
      if (msg.includes('(404)') && clinicalText.trim()) {
        await startOneClick(clinicalText, { overrideGuardrails: true })
        return
      }
      setOneClickState('idle')
      setOneClickError(e?.message || 'Failed to override guardrails')
    }
  }

  useEffect(() => {
    if (!oneClickRunId || oneClickState !== 'polling') return
    const id = window.setInterval(() => {
      pollOneClick(oneClickRunId)
    }, 2500)
    return () => window.clearInterval(id)
  }, [oneClickRunId, oneClickState])

  const loadFromPdf = async () => {
    if (!pdfFile) return
    setLoadState('loading')
    setNlpResult(null)
    try {
      const data = await uploadClinicalDocument(pdfFile)
      setClinicalText(data?.text || '')
      setLoadState('ok')
      if (oneClickAuto) {
        await startOneClick(data?.text || '')
      }
    } catch (e) {
      setNlpResult({ error: e?.message || 'Failed to read PDF' })
      setLoadState('error')
    }
  }

  const loadFromHandwritten = async () => {
    if (!handwrittenFile) return
    setLoadState('loading')
    setNlpResult(null)
    try {
      const data = await uploadHandwrittenPrescription(handwrittenFile)
      setClinicalText(data?.text || '')
      setLoadState('ok')
      if (oneClickAuto) {
        await startOneClick(data?.text || '')
      }
    } catch (e) {
      setNlpResult({ error: e?.message || 'Failed to read handwritten prescription' })
      setLoadState('error')
    }
  }

  const run = async () => {
    setNlpState('loading')
    setNlpResult(null)
    try {
      const data = await runPipelineText(clinicalText)
      setNlpResult(data)
      setNlpState('ok')
    } catch (e) {
      setNlpResult({ error: e?.message || 'Failed to extract entities' })
      setNlpState('error')
    }
  }

  const renderTags = (items, colorClass) => {
    if (!items || items.length === 0) return <span className="text-slate-400 italic text-xs">None found</span>;
    return (
      <div className="flex flex-wrap gap-2">
        {items.map((item, i) => (
          <span key={i} className={`px-2 py-1 rounded-md text-xs font-medium border ${colorClass}`}>
            {item}
          </span>
        ))}
      </div>
    );
  }

  return (
    <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="text-base font-semibold text-slate-800">
        Clinical Entity Extraction
      </div>
      <p className="text-xs text-slate-500 mb-3">
        Paste text, upload a PDF, or upload a handwritten prescription to extract diagnoses, procedures, and medications.
      </p>

      <div className="mb-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-sm font-semibold text-slate-800">One-click Hospital Workflow</div>
            <div className="mt-1 text-xs text-slate-500">
              Upload → analysis + verification + guardrails → submit → denial recovery → resubmit → approve (simulated).
            </div>
          </div>
          <button
            type="button"
            className="btn btnPrimary text-white"
            onClick={() => startOneClick(clinicalText)}
            disabled={!clinicalText.trim() || oneClickState === 'starting' || oneClickState === 'polling'}
          >
            {oneClickState === 'starting' ? 'Starting…' : oneClickState === 'polling' ? 'Running…' : 'Run Full Workflow'}
          </button>
        </div>

        <div className="mt-3 grid gap-3 lg:grid-cols-2">
          <div>
            <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Insurer Phone Number (optional)</div>
            <input
              className="mt-2 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-slate-400"
              placeholder="+14155552671"
              value={insurerNumber}
              onChange={(e) => setInsurerNumber(e.target.value)}
            />
            <div className="mt-2 flex items-center gap-2">
              <input
                id="autoOneClick"
                type="checkbox"
                checked={oneClickAuto}
                onChange={(e) => setOneClickAuto(Boolean(e.target.checked))}
              />
              <label htmlFor="autoOneClick" className="text-xs text-slate-600">
                Auto-run after upload
              </label>
            </div>
            {oneClickError && (
              <div className="mt-2 rounded-lg border border-red-200 bg-red-50 p-2 text-xs text-red-600">{oneClickError}</div>
            )}
          </div>

          <div>
            <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Workflow Status</div>
            {oneClickData ? (
              <div className="mt-2 rounded-lg border border-slate-200 bg-white p-3">
                <div className="text-xs text-slate-700">
                  <div><span className="font-semibold">Status:</span> {String(oneClickData?.status || '')}</div>
                  <div className="mt-1"><span className="font-semibold">Step:</span> {String(oneClickData?.step || '')}</div>
                  {oneClickData?.claim_id ? <div className="mt-1"><span className="font-semibold">Claim:</span> {String(oneClickData.claim_id).slice(0, 8)}</div> : null}
                  {oneClickData?.denial_event_id ? <div className="mt-1"><span className="font-semibold">Denial Event:</span> {String(oneClickData.denial_event_id)}</div> : null}
                  {oneClickData?.call_id ? <div className="mt-1"><span className="font-semibold">Call:</span> {String(oneClickData.call_id).slice(0, 8)}</div> : null}
                  {oneClickData?.record_id ? <div className="mt-1"><span className="font-semibold">Record:</span> {String(oneClickData.record_id).slice(0, 8)}</div> : null}
                  {overrideUsed ? <div className="mt-1"><span className="font-semibold">Override:</span> Enabled</div> : null}
                </div>

                {Array.isArray(oneClickData?.events) && oneClickData.events.length > 0 ? (
                  <div className="mt-3">
                    <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Events</div>
                    <div className="mt-2 max-h-40 overflow-auto rounded-md border border-slate-200 bg-slate-50 p-2 text-[11px] text-slate-700">
                      {oneClickData.events.slice(-12).map((ev, idx) => (
                        <div key={idx}>
                          [{String(ev?.step || '')}] {String(ev?.message || '')}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
                <div className="mt-3 flex gap-2">
                  <button
                    type="button"
                    className="btn btnSecondary"
                    onClick={() => pollOneClick(oneClickRunId)}
                    disabled={!oneClickRunId}
                  >
                    Refresh Status
                  </button>
                  {String(oneClickData?.status || '') === 'needs_review' ? (
                    <button
                      type="button"
                      className="btn btnPrimary text-white"
                      onClick={() => overrideOneClick(oneClickRunId)}
                      disabled={!oneClickRunId || oneClickState === 'starting' || oneClickState === 'polling'}
                    >
                      Continue (Override Guardrails)
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className="btn btnGhost"
                    onClick={() => {
                      setOneClickRunId('')
                      setOneClickData(null)
                      setOneClickError('')
                      setOneClickState('idle')
                    }}
                  >
                    Clear
                  </button>
                </div>

                <details className="mt-3">
                  <summary className="cursor-pointer text-xs font-semibold text-slate-600">Raw One-Click JSON</summary>
                  <pre className="mt-2 max-h-64 overflow-auto rounded-md border border-slate-200 bg-slate-50 p-2 text-[11px] text-slate-700">
                    {JSON.stringify(oneClickData, null, 2)}
                  </pre>
                </details>
              </div>
            ) : (
              <div className="mt-2 text-xs text-slate-500">
                {oneClickRunId ? 'Fetching status…' : 'No workflow running yet.'}
              </div>
            )}
          </div>
        </div>

        {oneClickTrace ? (
          <div className="mt-3">
            <details
              className="rounded-lg border border-slate-200 bg-white p-3"
              open={
                oneClickState === 'polling' ||
                String(oneClickData?.status || '') === 'needs_review'
              }
            >
              <summary className="cursor-pointer text-xs font-semibold text-slate-600">
                Full Agent Flow + Verification + Guardrails
              </summary>
              <div className="mt-3">
                <AgentWorkflowPanel
                  view="full"
                  externalResult={oneClickTrace}
                  externalText={clinicalText}
                  hideControls={true}
                  title="Agent Flow Visualization"
                />
              </div>
            </details>
          </div>
        ) : null}
      </div>

      <div className="flex flex-wrap gap-2 mb-3">
        <button
          type="button"
          className={`btn ${inputMode === 'text' ? 'btnPrimary text-white' : 'btnGhost'}`}
          onClick={() => {
            setInputMode('text')
            setLoadState('idle')
          }}
        >
          Paste Text
        </button>
        <button
          type="button"
          className={`btn ${inputMode === 'pdf' ? 'btnPrimary text-white' : 'btnGhost'}`}
          onClick={() => {
            setInputMode('pdf')
            setLoadState('idle')
          }}
        >
          Upload PDF
        </button>
        <button
          type="button"
          className={`btn ${inputMode === 'handwritten' ? 'btnPrimary text-white' : 'btnGhost'}`}
          onClick={() => {
            setInputMode('handwritten')
            setLoadState('idle')
          }}
        >
          Handwritten
        </button>
      </div>

      {inputMode === 'pdf' && (
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <input
            type="file"
            accept="application/pdf"
            className="block text-sm text-slate-700 file:mr-3 file:rounded-lg file:border file:border-slate-200 file:bg-white file:px-3 file:py-2 file:text-sm file:font-medium file:text-slate-700 hover:file:border-sky-300"
            onChange={(e) => setPdfFile(e.target.files?.[0] || null)}
          />
          <button
            type="button"
            className="btn btnSecondary"
            onClick={loadFromPdf}
            disabled={!pdfFile || loadState === 'loading'}
          >
            {loadState === 'loading' ? 'Reading…' : 'Read PDF'}
          </button>
        </div>
      )}

      {inputMode === 'handwritten' && (
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <input
            type="file"
            accept="image/*,application/pdf"
            className="block text-sm text-slate-700 file:mr-3 file:rounded-lg file:border file:border-slate-200 file:bg-white file:px-3 file:py-2 file:text-sm file:font-medium file:text-slate-700 hover:file:border-sky-300"
            onChange={(e) => setHandwrittenFile(e.target.files?.[0] || null)}
          />
          <button
            type="button"
            className="btn btnSecondary"
            onClick={loadFromHandwritten}
            disabled={!handwrittenFile || loadState === 'loading'}
          >
            {loadState === 'loading' ? 'Reading…' : 'Read Prescription'}
          </button>
        </div>
      )}

      <textarea
        className="w-full rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-800 outline-none ring-0 placeholder:text-slate-400 focus:border-sky-400 focus:ring-1 focus:ring-sky-400 transition-all"
        rows={4}
        value={clinicalText}
        onChange={(e) => setClinicalText(e.target.value)}
        placeholder={
          inputMode === 'pdf'
            ? 'Click "Read PDF" to load text here, then run extraction...'
            : inputMode === 'handwritten'
              ? 'Click "Read Prescription" to load text here, then run extraction...'
              : 'Paste physician note text here... (example: Pt w/ HTN and diabtes. BP elevated. Started on Metformin.)'
        }
      />
      <div className="mt-3 flex items-center justify-between gap-3">
        <div className="text-xs text-slate-500 font-medium">
          {nlpState === 'loading'
            ? 'Processing with Medical NLP Models...'
            : nlpState === 'ok'
              ? 'Extraction Complete'
              : nlpState === 'error'
                ? 'Extraction Failed'
                : ''}
        </div>
        <button
          className="btn btnPrimary text-white"
          onClick={run}
          disabled={!clinicalText.trim() || nlpState === 'loading'}
        >
          {nlpState === 'loading' ? 'Extracting...' : 'Run Extraction'}
        </button>
      </div>

      {nlpResult && !nlpResult.error && (
        <div className="mt-5 space-y-4 border-t border-slate-100 pt-4">
          {nlpResult.nlp_model && (
            <div className="flex flex-wrap gap-2 text-xs">
              <span className="px-2 py-1 rounded-md border bg-slate-50 text-slate-700">Model: {nlpResult.nlp_model}</span>
              {nlpResult.icd_embed_model && (
                <span className="px-2 py-1 rounded-md border bg-slate-50 text-slate-700">ICD Embeddings: {nlpResult.icd_embed_model}</span>
              )}
            </div>
          )}
          {(() => {
            const extracted = nlpResult.extracted || nlpResult
            return (
              <>
                <div>
                  <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Diagnoses</h4>
                  {renderTags(extracted.diagnosis, "bg-red-50 text-red-700 border-red-200")}
                </div>
                <div>
                  <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Procedures</h4>
                  {renderTags(extracted.procedures, "bg-sky-50 text-sky-700 border-sky-200")}
                </div>
                <div>
                  <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Medications</h4>
                  {renderTags(extracted.medications, "bg-emerald-50 text-emerald-700 border-emerald-200")}
                </div>
                {extracted.entities && extracted.entities.length > 0 && (
                  <details className="mt-4 group">
                    <summary className="text-xs font-medium text-slate-500 cursor-pointer hover:text-sky-600 transition-colors">
                      View Raw Entity Data
                    </summary>
                    <pre className="mt-2 overflow-auto rounded-lg border border-slate-200 bg-slate-50 p-3 text-[11px] text-slate-700">
                      {JSON.stringify(extracted.entities, null, 2)}
                    </pre>
                  </details>
                )}
              </>
            )
          })()}
          {nlpResult.codes && nlpResult.codes.length > 0 && (
            <div className="mt-4">
              <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">ICD-10 Codes</h4>
              <div className="flex flex-col gap-2">
                {nlpResult.codes.map((c, i) => (
                  <div key={i} className="flex items-center justify-between rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-[12px]">
                    <div className="font-semibold text-slate-800">{c.code}</div>
                    <div className="text-slate-600 flex-1 px-3">{c.description}</div>
                    <div className="text-slate-500">score: {(c.confidence ?? 0).toFixed(3)}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {nlpResult && nlpResult.error && (
        <div className="mt-4 rounded-lg bg-red-50 p-3 border border-red-100 text-sm text-red-600">
          {nlpResult.error}
        </div>
      )}
    </div>
  )
}

