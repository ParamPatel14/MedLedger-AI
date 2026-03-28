import { useEffect, useMemo, useRef, useState } from 'react'
import { getDenialDashboard, voiceDenialQuery, voiceSpeak } from '../services/api'

function pillClass(status) {
  const s = String(status || '').toLowerCase()
  if (s === 'approved') return 'bg-emerald-50 text-emerald-700 border-emerald-200'
  if (s === 'resubmitted') return 'bg-sky-50 text-sky-700 border-sky-200'
  if (s === 'denied') return 'bg-rose-50 text-rose-700 border-rose-200'
  if (s === 'query') return 'bg-amber-50 text-amber-800 border-amber-200'
  return 'bg-slate-50 text-slate-700 border-slate-200'
}

function stageLabel(stage) {
  const s = String(stage || '').toLowerCase()
  if (s === 'submitted') return 'Submitted'
  if (s === 'denied') return 'Denied'
  if (s === 'fixed') return 'Fixed'
  if (s === 'resubmitted') return 'Resubmitted'
  if (s === 'approved') return 'Approved'
  return '—'
}

function formatInr(amount) {
  const n = Number(amount)
  if (!Number.isFinite(n)) return '—'
  try {
    return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(n)
  } catch {
    return `₹${Math.round(n)}`
  }
}

function Timeline({ items }) {
  const steps = useMemo(() => {
    const order = ['submitted', 'denied', 'fixed', 'resubmitted', 'approved']
    const byStep = new Map()
    for (const it of Array.isArray(items) ? items : []) {
      const step = String(it?.step || '').toLowerCase()
      if (!step) continue
      if (!byStep.has(step)) byStep.set(step, it)
    }
    return order.map((k) => ({ key: k, item: byStep.get(k) }))
  }, [items])

  return (
    <div className="flex flex-wrap items-center gap-2">
      {steps.map((s, idx) => {
        const done = Boolean(s.item)
        const cls = done ? 'bg-slate-900 text-white border-slate-900' : 'bg-white text-slate-400 border-slate-200'
        return (
          <div key={s.key} className="flex items-center gap-2">
            <div className={`rounded-full border px-2 py-1 text-[11px] font-semibold ${cls}`}>{stageLabel(s.key)}</div>
            {idx < steps.length - 1 && <div className="h-px w-5 bg-slate-200" aria-hidden="true"></div>}
          </div>
        )
      })}
    </div>
  )
}

export default function DenialRecoveryPanel() {
  const [state, setState] = useState('idle')
  const [error, setError] = useState('')
  const [data, setData] = useState(null)
  const [expanded, setExpanded] = useState({})
  const [selectedClaimId, setSelectedClaimId] = useState('')
  const [selectedDenialEventId, setSelectedDenialEventId] = useState(null)

  const [voiceState, setVoiceState] = useState('idle')
  const [voiceError, setVoiceError] = useState('')
  const [voiceTranscript, setVoiceTranscript] = useState('')
  const [voiceMessage, setVoiceMessage] = useState('')
  const [voicePrompt, setVoicePrompt] = useState('')
  const [voiceNeedsMoreInfo, setVoiceNeedsMoreInfo] = useState(false)
  const [voiceAgentRun, setVoiceAgentRun] = useState(null)
  const [ttsUrl, setTtsUrl] = useState('')

  const audioRef = useRef(null)
  const recRef = useRef(null)

  useEffect(() => {
    let active = true
    setState('loading')
    setError('')
    ;(async () => {
      try {
        const d = await getDenialDashboard()
        if (!active) return
        setData(d)
        setState('ok')
      } catch (e) {
        if (!active) return
        setState('error')
        setError(e?.message || 'Failed to load denial dashboard')
      }
    })()
    return () => {
      active = false
    }
  }, [])

  const refresh = async () => {
    setState('loading')
    setError('')
    try {
      const d = await getDenialDashboard()
      setData(d)
      setState('ok')
    } catch (e) {
      setState('error')
      setError(e?.message || 'Failed to load denial dashboard')
    }
  }

  const metrics = data?.metrics || {}
  const rows = Array.isArray(data?.denied_claims) ? data.denied_claims : []

  function stopTts() {
    if (audioRef.current) {
      try {
        audioRef.current.pause()
        audioRef.current.currentTime = 0
      } catch (e) {
        void e
      }
    }
  }

  useEffect(() => {
    return () => {
      if (ttsUrl) URL.revokeObjectURL(ttsUrl)
      stopTts()
    }
  }, [ttsUrl])

  async function playTts(text) {
    const t = String(text || '').trim()
    if (!t) return
    stopTts()
    setVoiceError('')
    try {
      const blob = await voiceSpeak(t)
      const url = URL.createObjectURL(blob)
      setTtsUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev)
        return url
      })
      const a = new Audio(url)
      audioRef.current = a
      await a.play()
    } catch (e) {
      setVoiceError(e?.message || 'Voice playback failed')
    }
  }

  const encodeWav = (buffers, sampleRate) => {
    const samples = buffers.reduce((acc, b) => acc + b.length, 0)
    const buffer = new ArrayBuffer(44 + samples * 2)
    const view = new DataView(buffer)
    const writeString = (offset, str) => {
      for (let i = 0; i < str.length; i += 1) view.setUint8(offset + i, str.charCodeAt(i))
    }
    const floatTo16BitPCM = (output, offset, input) => {
      let o = offset
      for (let i = 0; i < input.length; i += 1) {
        const s = Math.max(-1, Math.min(1, input[i]))
        output.setInt16(o, s < 0 ? s * 0x8000 : s * 0x7fff, true)
        o += 2
      }
      return o
    }
    writeString(0, 'RIFF')
    view.setUint32(4, 36 + samples * 2, true)
    writeString(8, 'WAVE')
    writeString(12, 'fmt ')
    view.setUint32(16, 16, true)
    view.setUint16(20, 1, true)
    view.setUint16(22, 1, true)
    view.setUint32(24, sampleRate, true)
    view.setUint32(28, sampleRate * 2, true)
    view.setUint16(32, 2, true)
    view.setUint16(34, 16, true)
    writeString(36, 'data')
    view.setUint32(40, samples * 2, true)
    let offset = 44
    for (const b of buffers) offset = floatTo16BitPCM(view, offset, b)
    return new Blob([view], { type: 'audio/wav' })
  }

  const startRecording = async () => {
    if (!selectedClaimId) {
      setVoiceError('Select a claim first (click a claim row).')
      return
    }
    stopTts()
    setVoiceError('')
    setVoiceTranscript('')
    setVoiceMessage('')
    setVoicePrompt('')
    setVoiceAgentRun(null)
    setVoiceState('recording')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const AudioCtx = window.AudioContext || window.webkitAudioContext
      const ctx = new AudioCtx()
      const source = ctx.createMediaStreamSource(stream)
      const processor = ctx.createScriptProcessor(4096, 1, 1)
      const buffers = []
      processor.onaudioprocess = (e) => {
        const input = e.inputBuffer.getChannelData(0)
        buffers.push(new Float32Array(input))
      }
      source.connect(processor)
      processor.connect(ctx.destination)
      recRef.current = { stream, ctx, source, processor, buffers }
    } catch (e) {
      setVoiceState('idle')
      setVoiceError(e?.message || 'Microphone access failed')
    }
  }

  const stopRecording = async () => {
    const rec = recRef.current
    if (!rec) return
    recRef.current = null
    setVoiceState('processing')
    try {
      try {
        rec.processor.disconnect()
        rec.source.disconnect()
      } catch (e) {
        void e
      }
      try {
        rec.stream.getTracks().forEach((t) => t.stop())
      } catch (e) {
        void e
      }
      let sampleRate = 16000
      try {
        sampleRate = Number(rec.ctx.sampleRate) || sampleRate
        await rec.ctx.close()
      } catch (e) {
        void e
      }

      const wav = encodeWav(rec.buffers, sampleRate)
      const mode = voiceNeedsMoreInfo ? 'provide_denial_reason' : 'auto'
      const out = await voiceDenialQuery({
        audioWavBlob: wav,
        claimId: selectedClaimId,
        denialEventId: selectedDenialEventId,
        mode,
      })
      setVoiceTranscript(String(out?.transcript || ''))
      setVoiceMessage(String(out?.message || ''))
      setVoicePrompt(String(out?.prompt || ''))
      setVoiceNeedsMoreInfo(Boolean(out?.needs_more_info))
      setVoiceAgentRun(out?.agent_run || null)
      setVoiceState('idle')
      const speakText = String(out?.prompt || out?.message || '').trim()
      if (speakText) await playTts(speakText)
    } catch (e) {
      setVoiceState('idle')
      setVoiceError(e?.message || 'Voice request failed')
    }
  }

  return (
    <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-base font-semibold text-slate-800">Denial Recovery Panel</div>
          <div className="mt-1 text-xs text-slate-500">Track denied claims, recovery progress, and outcomes.</div>
        </div>
        <button className="btn btnSecondary" onClick={refresh} disabled={state === 'loading'}>
          Refresh
        </button>
      </div>

      {error && (
        <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-600">{error}</div>
      )}

      <div className="mt-4 grid gap-3 md:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-500">Revenue Recovered</div>
          <div className="mt-2 text-2xl font-semibold text-slate-900">{formatInr(metrics.revenue_recovered || 0)}</div>
          <div className="mt-1 text-xs text-slate-500">₹ recovered from previously-denied claims</div>
        </div>
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-500">Denial Reduction</div>
          <div className="mt-2 text-2xl font-semibold text-slate-900">
            {Number(metrics.denial_reduction_percent ?? metrics.recovered_percent ?? 0).toFixed(1)}%
          </div>
          <div className="mt-1 text-xs text-slate-500">
            {Number(metrics.recovered_claims || 0)} recovered · {Number(metrics.denied_claims || 0)} denied
          </div>
        </div>
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-500">Automation</div>
          <div className="mt-2 text-2xl font-semibold text-slate-900">
            {Number(metrics.automation_percent || 0).toFixed(1)}%
          </div>
          <div className="mt-1 text-xs text-slate-500">Denied claims with auto correction/resubmission</div>
        </div>
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-500">Denial Rate</div>
          <div className="mt-2 text-2xl font-semibold text-slate-900">
            {Number(metrics.denial_rate_percent || 0).toFixed(1)}%
          </div>
          <div className="mt-1 text-xs text-slate-500">
            {Number(metrics.denied_claims || 0)} denied · {Number(metrics.total_claims || 0)} total
          </div>
        </div>
      </div>

      <div className="mt-5 rounded-lg border border-slate-200 bg-slate-50 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-sm font-semibold text-slate-800">Denial Voice Assistant</div>
            <div className="mt-1 text-xs text-slate-500">
              Uses Whisper (STT) + Piper (TTS). If denial details are missing, read the denial email and it will run corrections.
            </div>
          </div>
          <div className="flex items-center gap-2">
            {voiceState !== 'recording' ? (
              <button className="btn btnSecondary" onClick={startRecording} disabled={voiceState !== 'idle'}>
                Start Voice
              </button>
            ) : (
              <button className="btn btnPrimary text-white" onClick={stopRecording}>
                Stop & Send
              </button>
            )}
          </div>
        </div>

        <div className="mt-3 grid gap-3 md:grid-cols-2">
          <div className="rounded-lg border border-slate-200 bg-white p-3">
            <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Selected Claim</div>
            <div className="mt-2 text-xs text-slate-700">
              {selectedClaimId ? (
                <div className="font-semibold text-slate-900">{selectedClaimId}</div>
              ) : (
                <div className="text-slate-500">Click a claim row to select it.</div>
              )}
              {selectedDenialEventId ? <div className="mt-1 text-[11px] text-slate-500">Denial event: {String(selectedDenialEventId)}</div> : null}
            </div>
            {voiceState === 'processing' && <div className="mt-2 text-xs text-slate-500">Processing voice…</div>}
            {voiceError && <div className="mt-2 rounded-lg border border-red-200 bg-red-50 p-2 text-xs text-red-600">{voiceError}</div>}
          </div>

          <div className="rounded-lg border border-slate-200 bg-white p-3">
            <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Assistant Output</div>
            {voiceTranscript ? (
              <div className="mt-2">
                <div className="text-[11px] font-semibold text-slate-600">Transcript</div>
                <div className="mt-1 rounded-lg border border-slate-200 bg-slate-50 p-2 text-xs text-slate-700">{voiceTranscript}</div>
              </div>
            ) : (
              <div className="mt-2 text-xs text-slate-500">Say: “Summarize denial”, “Fix and resubmit”, or read the denial email.</div>
            )}
            {voiceMessage && (
              <div className="mt-3">
                <div className="text-[11px] font-semibold text-slate-600">Message</div>
                <div className="mt-1 text-xs text-slate-700">{voiceMessage}</div>
              </div>
            )}
            {voicePrompt && (
              <div className="mt-2 rounded-lg border border-amber-200 bg-amber-50 p-2 text-xs text-amber-900">
                {voicePrompt}
              </div>
            )}
          </div>
        </div>

        {voiceAgentRun && (
          <div className="mt-3 rounded-lg border border-slate-200 bg-white p-3">
            <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Agent Result</div>
            <pre className="mt-2 max-h-56 overflow-auto rounded-lg border border-slate-200 bg-slate-50 p-3 text-[11px] text-slate-700">
              {JSON.stringify(voiceAgentRun, null, 2)}
            </pre>
          </div>
        )}
      </div>

      <div className="mt-5 overflow-hidden rounded-lg border border-slate-200">
        <div className="grid grid-cols-12 gap-2 border-b border-slate-200 bg-slate-50 px-4 py-2 text-[11px] font-bold uppercase tracking-wider text-slate-500">
          <div className="col-span-3">Claim</div>
          <div className="col-span-2">Status</div>
          <div className="col-span-2">Progress</div>
          <div className="col-span-2 text-right">Amount</div>
          <div className="col-span-3">Timeline</div>
        </div>

        {state === 'loading' && (
          <div className="px-4 py-4 text-xs text-slate-500">Loading denial dashboard…</div>
        )}

        {state !== 'loading' && rows.length === 0 && (
          <div className="px-4 py-4 text-xs text-slate-500">No denied claims found.</div>
        )}

        {rows.map((r) => {
          const claimId = String(r?.claim_id || '')
          const isOpen = Boolean(expanded[claimId])
          const denialTypes = Array.isArray(r?.denial_types) ? r.denial_types : []
          const progress = r?.progress || {}
          const percent = Number(progress?.percent || 0)

          return (
            <div key={claimId} className="border-b border-slate-200 last:border-b-0">
              <button
                className="w-full text-left px-4 py-3 hover:bg-slate-50 transition-colors"
                onClick={() => {
                  setSelectedClaimId(claimId)
                  setSelectedDenialEventId(r?.last_denial_event_id ?? null)
                  setExpanded((p) => ({ ...p, [claimId]: !p[claimId] }))
                }}
              >
                <div className="grid grid-cols-12 items-center gap-2">
                  <div className="col-span-3">
                    <div className="text-sm font-semibold text-slate-900">{claimId.slice(0, 8)}</div>
                    <div className="mt-0.5 text-xs text-slate-500">
                      Denials: {Number(r?.denials_count || 0)} · Corrections: {Number(r?.corrections_count || 0)} · Resub: {Number(r?.resubmissions_count || 0)}
                    </div>
                    {denialTypes.length > 0 && (
                      <div className="mt-1 text-[11px] text-slate-500">{denialTypes.join(', ')}</div>
                    )}
                  </div>

                  <div className="col-span-2">
                    <div className={`inline-flex items-center rounded-full border px-2 py-1 text-xs font-semibold ${pillClass(r?.status)}`}>
                      {String(r?.status || '—')}
                    </div>
                    <div className="mt-1 text-[11px] text-slate-500">{r?.updated_at ? String(r.updated_at) : ''}</div>
                  </div>

                  <div className="col-span-2">
                    <div className="text-xs font-semibold text-slate-700">{stageLabel(progress?.stage)}</div>
                    <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-slate-100">
                      <div className="h-2 rounded-full bg-slate-900" style={{ width: `${Math.max(0, Math.min(100, percent))}%` }} />
                    </div>
                    <div className="mt-1 text-[11px] text-slate-500">{percent}%</div>
                  </div>

                  <div className="col-span-2 text-right">
                    <div className="text-sm font-semibold text-slate-900">{formatInr(r?.amount)}</div>
                    <div className="mt-0.5 text-[11px] text-slate-500">Last conf: {Number(r?.last_confidence || 0).toFixed(2)}</div>
                  </div>

                  <div className="col-span-3">
                    <Timeline items={r?.timeline} />
                  </div>
                </div>
              </button>

              {isOpen && (
                <div className="px-4 pb-4">
                  <div className="rounded-lg border border-slate-200 bg-white p-3">
                    <div className="text-xs font-bold uppercase tracking-wider text-slate-500">Claim Timeline</div>
                    <div className="mt-2">
                      <Timeline items={r?.timeline} />
                    </div>
                    <pre className="mt-3 max-h-56 overflow-auto rounded-lg border border-slate-200 bg-slate-50 p-3 text-[11px] text-slate-700">
                      {JSON.stringify(
                        {
                          claim_id: r?.claim_id,
                          status: r?.status,
                          denial_types: r?.denial_types,
                          progress: r?.progress,
                          last_denial_event_id: r?.last_denial_event_id,
                          last_correction_id: r?.last_correction_id,
                          last_resubmission_id: r?.last_resubmission_id,
                        },
                        null,
                        2,
                      )}
                    </pre>
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
