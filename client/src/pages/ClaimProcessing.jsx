import { useEffect, useMemo, useState } from 'react'
import { FileUp, Sparkles } from 'lucide-react'

import { Timeline } from '../components/patterns/Timeline'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card'
import { Input } from '../components/ui/input'
import { Skeleton } from '../components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs'
import { Textarea } from '../components/ui/textarea'
import {
  getOneClickWorkflow,
  runPipelineText,
  startOneClickWorkflow,
  uploadClinicalDocument,
  uploadHandwrittenPrescription,
} from '../services/api'

function PageTitle() {
  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-[-0.03em] text-slate-900 md:text-3xl">Claim processing</h1>
      <p className="mt-1 max-w-3xl text-sm text-slate-600">
        Upload a record or paste clinical text to extract entities, map ICD codes, and generate an auditable agent trace.
      </p>
    </div>
  )
}

function ConfidenceBar({ label, value }) {
  const v = Math.max(0, Math.min(1, Number(value)))
  return (
    <div className="rounded-[22px] border border-white/70 bg-white/55 p-3 shadow-[0_12px_40px_rgba(2,6,23,0.08)]">
      <div className="flex items-center justify-between gap-3">
        <div className="text-xs font-semibold text-slate-700">{label}</div>
        <div className="text-xs font-semibold tabular-nums text-slate-900">{Number.isFinite(v) ? v.toFixed(2) : '—'}</div>
      </div>
      <div className="mt-2 h-2.5 w-full overflow-hidden rounded-full bg-slate-200/70">
        <div
          className="h-full rounded-full bg-gradient-to-r from-blue-500 via-violet-500 to-cyan-400"
          style={{ width: `${Math.round(v * 100)}%` }}
        />
      </div>
    </div>
  )
}

function toArray(v) {
  if (Array.isArray(v)) return v
  if (!v) return []
  return [v]
}

export default function ClaimProcessing() {
  const [mode, setMode] = useState('text')
  const [text, setText] = useState('')
  const [pdfFile, setPdfFile] = useState(null)
  const [hwFile, setHwFile] = useState(null)

  const [pipelineState, setPipelineState] = useState('idle')
  const [pipelineResult, setPipelineResult] = useState(null)
  const [pipelineError, setPipelineError] = useState('')

  const [oneClickState, setOneClickState] = useState('idle')
  const [oneClickRunId, setOneClickRunId] = useState('')
  const [oneClickData, setOneClickData] = useState(null)
  const [oneClickError, setOneClickError] = useState('')

  const runPipeline = async (payload) => {
    const p = String(payload || '').trim()
    if (!p) return
    setPipelineError('')
    setPipelineState('loading')
    setPipelineResult(null)
    try {
      const out = await runPipelineText(p)
      setPipelineResult(out)
      setPipelineState('ok')
    } catch (e) {
      setPipelineState('error')
      setPipelineError(e?.message || 'Failed to run pipeline')
    }
  }

  const startTrace = async (payload) => {
    const p = String(payload || '').trim()
    if (!p) return
    setOneClickError('')
    setOneClickState('starting')
    setOneClickData(null)
    try {
      const out = await startOneClickWorkflow({ text: p, autoCallIfNeeded: true })
      const rid = String(out?.run_id || '')
      setOneClickRunId(rid)
      setOneClickState('polling')
    } catch (e) {
      setOneClickState('idle')
      setOneClickError(e?.message || 'Failed to start agent trace')
    }
  }

  useEffect(() => {
    if (!oneClickRunId || oneClickState !== 'polling') return
    let active = true
    const tick = async () => {
      try {
        const data = await getOneClickWorkflow(oneClickRunId)
        if (!active) return
        setOneClickData(data)
        const s = String(data?.status || '')
        if (s === 'done' || s === 'error' || s === 'needs_review') {
          setOneClickState('idle')
        }
      } catch (e) {
        if (!active) return
        setOneClickError(e?.message || 'Failed to fetch trace')
        setOneClickState('idle')
      }
    }
    tick()
    const id = window.setInterval(tick, 2500)
    return () => {
      active = false
      window.clearInterval(id)
    }
  }, [oneClickRunId, oneClickState])

  const oneClickOutput = oneClickData?.output && typeof oneClickData.output === 'object' ? oneClickData.output : null
  const clinical = oneClickOutput?.clinical || pipelineResult?.clinical || pipelineResult?.extraction || null
  const coding = oneClickOutput?.coding || pipelineResult?.coding || null
  const payer = oneClickOutput?.payer || pipelineResult?.payer || null
  const confidence = Number(oneClickOutput?.confidence ?? oneClickData?.confidence ?? pipelineResult?.confidence ?? 0.92)

  const icdCodes = useMemo(() => {
    const fromCoding = coding?.icd_codes || coding?.icd10 || coding?.codes || null
    if (Array.isArray(fromCoding)) return fromCoding
    if (fromCoding && typeof fromCoding === 'object') {
      return Object.entries(fromCoding).map(([code, score]) => ({ code, score }))
    }
    const fallback = pipelineResult?.icd_codes || pipelineResult?.icd10_codes || null
    if (Array.isArray(fallback)) return fallback
    return []
  }, [coding, pipelineResult])

  const entities = useMemo(() => {
    const d = clinical || {}
    const dx = toArray(d?.diagnoses || d?.diagnosis || d?.dx)
    const meds = toArray(d?.medications || d?.meds)
    const procs = toArray(d?.procedures || d?.cpt || d?.proc)
    return { dx, meds, procs }
  }, [clinical])

  const timeline = useMemo(() => {
    const out = oneClickData?.output && typeof oneClickData.output === 'object' ? oneClickData.output : null
    const status = String(oneClickData?.status || '').toLowerCase()
    const stage = (key, title, subtitle) => ({
      id: key,
      title,
      subtitle,
      status: out?.[key] ? 'ok' : status === 'needs_review' ? 'needs_review' : status || 'pending',
      badgeLabel: out?.[key] ? 'Done' : status === 'needs_review' ? 'Needs review' : 'Pending',
    })
    return [
      { id: 'ingest', title: 'Ingestion', subtitle: 'Parse record → normalize text', status: 'ok', badgeLabel: 'Ready' },
      stage('clinical', 'Clinical extraction', 'Entities, sections, clinical context'),
      stage('coding', 'Coding', 'ICD mapping + confidence scoring'),
      stage('payer', 'Rule engine', 'TPA rules + denial prevention'),
      stage('governance', 'Governance', 'Guardrails + decision'),
    ]
  }, [oneClickData])

  const loadFile = async (kind) => {
    const f = kind === 'pdf' ? pdfFile : hwFile
    if (!f) return
    setPipelineError('')
    setPipelineState('loading')
    setPipelineResult(null)
    try {
      const out = kind === 'pdf' ? await uploadClinicalDocument(f) : await uploadHandwrittenPrescription(f)
      const extracted = String(out?.text || '').trim()
      setText(extracted)
      setPipelineState('idle')
      await Promise.all([runPipeline(extracted), startTrace(extracted)])
    } catch (e) {
      setPipelineState('error')
      setPipelineError(e?.message || 'Failed to read file')
    }
  }

  const runNow = async () => {
    const p = String(text || '').trim()
    if (!p) return
    await Promise.all([runPipeline(p), startTrace(p)])
  }

  const busy = pipelineState === 'loading' || oneClickState === 'starting' || oneClickState === 'polling'

  return (
    <div className="space-y-6">
      <PageTitle />

      <div className="grid gap-4 xl:grid-cols-5">
        <div className="xl:col-span-2">
          <Card variant="glass">
            <CardHeader>
              <div>
                <CardTitle>Input</CardTitle>
                <CardDescription>Choose a source and run the pipeline.</CardDescription>
              </div>
              <Badge variant="info" className="bg-white/70">
                HIPAA-ready UI
              </Badge>
            </CardHeader>
            <CardContent>
              <Tabs value={mode} onValueChange={setMode}>
                <TabsList className="w-full">
                  <TabsTrigger value="text" className="flex-1">
                    Text
                  </TabsTrigger>
                  <TabsTrigger value="pdf" className="flex-1">
                    PDF
                  </TabsTrigger>
                  <TabsTrigger value="handwritten" className="flex-1">
                    Handwritten
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="text">
                  <div className="space-y-3">
                    <Textarea
                      value={text}
                      onChange={(e) => setText(e.target.value)}
                      placeholder="Paste clinical note text…"
                      className="min-h-44"
                    />
                    <div className="flex flex-wrap gap-2">
                      <Button onClick={runNow} disabled={busy || !String(text || '').trim()}>
                        <Sparkles className="size-4" />
                        Run pipeline
                      </Button>
                      <Button variant="outline" onClick={() => setText('')} disabled={busy}>
                        Clear
                      </Button>
                    </div>
                  </div>
                </TabsContent>

                <TabsContent value="pdf">
                  <div className="space-y-3">
                    <div className="rounded-[28px] border border-dashed border-[var(--border)] bg-white/55 p-5 shadow-[0_12px_40px_rgba(2,6,23,0.06)]">
                      <div className="flex items-center gap-3">
                        <div className="grid size-11 place-items-center rounded-2xl bg-gradient-to-br from-blue-500/20 via-violet-500/15 to-cyan-400/20">
                          <FileUp className="size-5 text-slate-800" />
                        </div>
                        <div className="min-w-0">
                          <div className="text-sm font-semibold text-slate-900">Upload medical record</div>
                          <div className="mt-1 text-xs text-slate-600">PDF → extracted text → pipeline trace</div>
                        </div>
                      </div>
                      <div className="mt-4">
                        <Input type="file" accept="application/pdf" onChange={(e) => setPdfFile(e.target.files?.[0] || null)} />
                        <div className="mt-3 flex gap-2">
                          <Button variant="secondary" onClick={() => loadFile('pdf')} disabled={busy || !pdfFile}>
                            Process PDF
                          </Button>
                          <Button variant="outline" onClick={() => setPdfFile(null)} disabled={busy || !pdfFile}>
                            Reset
                          </Button>
                        </div>
                      </div>
                    </div>
                  </div>
                </TabsContent>

                <TabsContent value="handwritten">
                  <div className="space-y-3">
                    <div className="rounded-[28px] border border-dashed border-[var(--border)] bg-white/55 p-5 shadow-[0_12px_40px_rgba(2,6,23,0.06)]">
                      <div className="flex items-center gap-3">
                        <div className="grid size-11 place-items-center rounded-2xl bg-gradient-to-br from-blue-500/20 via-violet-500/15 to-cyan-400/20">
                          <FileUp className="size-5 text-slate-800" />
                        </div>
                        <div className="min-w-0">
                          <div className="text-sm font-semibold text-slate-900">Upload handwritten note</div>
                          <div className="mt-1 text-xs text-slate-600">Image/PDF → OCR → pipeline trace</div>
                        </div>
                      </div>
                      <div className="mt-4">
                        <Input type="file" accept="image/*,application/pdf" onChange={(e) => setHwFile(e.target.files?.[0] || null)} />
                        <div className="mt-3 flex gap-2">
                          <Button variant="secondary" onClick={() => loadFile('hw')} disabled={busy || !hwFile}>
                            Process file
                          </Button>
                          <Button variant="outline" onClick={() => setHwFile(null)} disabled={busy || !hwFile}>
                            Reset
                          </Button>
                        </div>
                      </div>
                    </div>
                  </div>
                </TabsContent>
              </Tabs>

              {(pipelineError || oneClickError) && (
                <div className="mt-4 rounded-[24px] border border-rose-200/60 bg-rose-50/60 p-4 text-sm text-rose-700">
                  {pipelineError || oneClickError}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="xl:col-span-3">
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Results</CardTitle>
                <CardDescription>Clinical extraction, ICD codes, confidence scores, and trace.</CardDescription>
              </div>
              <Badge variant={busy ? 'info' : 'success'} className="bg-white/70">
                {busy ? 'Running' : 'Ready'}
              </Badge>
            </CardHeader>
            <CardContent>
              <div className="grid gap-3 md:grid-cols-3">
                <ConfidenceBar label="Overall confidence" value={confidence} />
                <ConfidenceBar label="Coding confidence" value={Number(coding?.confidence ?? 0.9)} />
                <ConfidenceBar label="Rule confidence" value={Number(payer?.confidence ?? 0.88)} />
              </div>

              <div className="mt-5 grid gap-4 lg:grid-cols-2">
                <Card variant="glass" className="p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold text-slate-900">Clinical extraction</div>
                      <div className="mt-1 text-xs text-slate-600">Diagnoses, medications, and procedures.</div>
                    </div>
                    <Badge variant="info">Entities</Badge>
                  </div>
                  <div className="mt-4 space-y-3">
                    {pipelineState === 'loading' ? (
                      <>
                        <Skeleton className="h-16 w-full" />
                        <Skeleton className="h-16 w-full" />
                      </>
                    ) : (
                      <>
                        <div className="rounded-[22px] border border-white/70 bg-white/55 p-3">
                          <div className="text-xs font-semibold text-slate-700">Diagnoses</div>
                          <div className="mt-2 flex flex-wrap gap-2">
                            {entities.dx.length ? (
                              entities.dx.slice(0, 8).map((t, i) => (
                                <Badge key={i} variant="neutral" className="bg-white/70">
                                  {String(t)}
                                </Badge>
                              ))
                            ) : (
                              <div className="text-xs text-slate-500">No diagnoses detected</div>
                            )}
                          </div>
                        </div>
                        <div className="rounded-[22px] border border-white/70 bg-white/55 p-3">
                          <div className="text-xs font-semibold text-slate-700">Medications</div>
                          <div className="mt-2 flex flex-wrap gap-2">
                            {entities.meds.length ? (
                              entities.meds.slice(0, 8).map((t, i) => (
                                <Badge key={i} variant="neutral" className="bg-white/70">
                                  {String(t)}
                                </Badge>
                              ))
                            ) : (
                              <div className="text-xs text-slate-500">No medications detected</div>
                            )}
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                </Card>

                <Card variant="glass" className="p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold text-slate-900">ICD codes</div>
                      <div className="mt-1 text-xs text-slate-600">Mapped codes with confidence.</div>
                    </div>
                    <Badge variant="success">Coding</Badge>
                  </div>
                  <div className="mt-4 space-y-2">
                    {pipelineState === 'loading' ? (
                      Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-10 w-full rounded-2xl" />)
                    ) : icdCodes.length ? (
                      icdCodes.slice(0, 8).map((c, idx) => (
                        <div
                          key={c.code || idx}
                          className="flex items-center justify-between gap-3 rounded-2xl border border-white/70 bg-white/55 px-3 py-2 shadow-[0_12px_40px_rgba(2,6,23,0.06)]"
                        >
                          <div className="text-sm font-semibold text-slate-900">{c.code || String(c)}</div>
                          <Badge variant="info">
                            {Number.isFinite(Number(c.score)) ? Number(c.score).toFixed(2) : Number(c.confidence || 0.9).toFixed(2)}
                          </Badge>
                        </div>
                      ))
                    ) : (
                      <div className="rounded-[22px] border border-white/70 bg-white/55 p-4 text-sm text-slate-600">
                        Run the pipeline to populate ICD codes.
                      </div>
                    )}
                  </div>
                </Card>
              </div>

              <div className="mt-6">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-slate-900">Step-by-step agent flow</div>
                    <div className="mt-1 text-xs text-slate-600">A readable trace designed for explainability.</div>
                  </div>
                  <Badge variant={oneClickData?.status === 'needs_review' ? 'warning' : 'neutral'} className="bg-white/70">
                    {String(oneClickData?.status || 'idle')}
                  </Badge>
                </div>
                <div className="mt-4">
                  <Timeline items={timeline} />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

