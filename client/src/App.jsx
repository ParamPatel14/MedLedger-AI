import { useEffect, useRef, useState } from 'react'
import { motion, useInView } from 'framer-motion'
import {
  Activity,
  BarChart3,
  Brain,
  ChevronRight,
  FileSearch,
  GitBranch,
  ShieldCheck,
  TrendingUp,
} from 'lucide-react'
import Extract from './pages/Extract'
import Denials from './pages/Denials'
import Rules from './pages/Rules'
import AgentWorkflowPanel from './components/AgentWorkflowPanel'
import ClaimExplanationPanel from './components/ClaimExplanationPanel'
import { Button } from './components/ui/button'
import { PageHeader } from './components/ui/page-header'
import './App.css'

/* ── Animated counter ── */
function useCountUp(target, duration = 1800, start = false) {
  const [value, setValue] = useState(0)
  useEffect(() => {
    if (!start) return
    let startTime = null
    const step = (timestamp) => {
      if (!startTime) startTime = timestamp
      const progress = Math.min((timestamp - startTime) / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      setValue(Math.round(eased * target))
      if (progress < 1) requestAnimationFrame(step)
    }
    requestAnimationFrame(step)
  }, [target, duration, start])
  return value
}

/* ── Stat item ── */
function StatItem({ value, suffix = '', label, start }) {
  const count = useCountUp(value, 1600, start)
  return (
    <div className="heroStat">
      <div className="heroStatValue">
        {count}
        {suffix}
      </div>
      <div className="heroStatLabel">{label}</div>
    </div>
  )
}

/* ── Feature card ── */
function FeatureCard({ icon: Icon, title, body, delay = 0 }) {
  const ref = useRef(null)
  const inView = useInView(ref, { once: true, margin: '-60px' })
  return (
    <motion.div
      ref={ref}
      className="card"
      initial={{ opacity: 0, y: 24 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.45, delay, ease: [0.25, 0.46, 0.45, 0.94] }}
    >
      <div className="cardIcon">
        <Icon size={18} strokeWidth={2} />
      </div>
      <div className="cardTitle">{title}</div>
      <div className="cardBody">{body}</div>
    </motion.div>
  )
}

/* ── Workflow step ── */
function WorkflowStep({ num, title, desc, delay = 0 }) {
  const ref = useRef(null)
  const inView = useInView(ref, { once: true, margin: '-40px' })
  return (
    <motion.div
      ref={ref}
      className="workflowStep"
      initial={{ opacity: 0, y: 20 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.4, delay, ease: 'easeOut' }}
    >
      <div className="workflowNum">{num}</div>
      <div className="workflowStepTitle">{title}</div>
      <div className="workflowStepDesc">{desc}</div>
    </motion.div>
  )
}

/* ── EKG animated card ── */
function HeroVisualCard() {
  return (
    <motion.div
      className="heroVisual"
      initial={{ opacity: 0, x: 30 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.6, delay: 0.3, ease: [0.25, 0.46, 0.45, 0.94] }}
    >
      <div className="heroCard">
        <div className="heroCardHeader">
          <span className="heroCardTitle">Live Pipeline Monitor</span>
          <span className="heroCardLive">
            <span className="heroCardLiveDot" />
            Active
          </span>
        </div>
        <div className="heroCardBody">
          {/* EKG Line */}
          <div className="ekgContainer">
            <svg className="ekgSvg" viewBox="0 0 320 40" preserveAspectRatio="none">
              {/* Static base line */}
              <path
                className="ekgPath"
                d="M0,20 L60,20 L70,20 L75,5 L80,35 L85,20 L100,20 L105,14 L110,26 L115,20 L160,20 L165,5 L170,35 L175,20 L200,20 L205,14 L210,26 L215,20 L260,20 L265,5 L270,35 L275,20 L320,20"
                opacity="0.15"
              />
              {/* Animated draw */}
              <path
                className="ekgPathAnim"
                d="M0,20 L60,20 L70,20 L75,5 L80,35 L85,20 L100,20 L105,14 L110,26 L115,20 L160,20 L165,5 L170,35 L175,20 L200,20 L205,14 L210,26 L215,20 L260,20 L265,5 L270,35 L275,20 L320,20"
              />
            </svg>
          </div>

          {/* Stats grid */}
          <div className="heroCardGrid">
            {[
              { label: 'Models Loaded', value: '3' },
              { label: 'Accuracy', value: '98%' },
              { label: 'ICD-10 Codes', value: '70K+' },
              { label: 'Avg Latency', value: '<1s' },
            ].map(({ label, value }) => (
              <div key={label} className="heroCardStat">
                <div className="heroCardStatLabel">{label}</div>
                <div className="heroCardStatValue">{value}</div>
              </div>
            ))}
          </div>

          <div className="heroCardStatus">
            <span className="heroCardStatusText">NLP pipeline ready</span>
            <span className="heroCardStatusBadge">
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#059669', display: 'inline-block' }} />
              Operational
            </span>
          </div>
        </div>
      </div>
    </motion.div>
  )
}

/* ══════════════════════════════════════
   MAIN APP
══════════════════════════════════════ */
export default function App() {
  const [path, setPath] = useState(window.location.pathname || '/')
  useEffect(() => {
    const onPop = () => setPath(window.location.pathname || '/')
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  const navigate = (to) => {
    if (to === path) return
    window.history.pushState({}, '', to)
    setPath(to)
  }

  const isClaim = path === '/claim' || path === '/extract'
  const isFlow = path === '/flow'
  const isVerify = path === '/verify'
  const isImpact = path === '/impact' || path === '/denials'
  const isRules = path === '/rules'
  const isHome = !(isClaim || isFlow || isVerify || isImpact || isRules)

  /* Stats counter trigger */
  const statsRef = useRef(null)
  const statsInView = useInView(statsRef, { once: true })

  return (
    <div className="appShell">
      {/* ── Header ── */}
      <header className="topBar">
        <div className="container topBarInner">
          {/* Brand */}
          <div className="brand">
            <div className="brandMark" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 20 20" fill="none">
                <rect x="7.5" y="1" width="5" height="18" rx="1.5" fill="white" />
                <rect x="1" y="7.5" width="18" height="5" rx="1.5" fill="white" />
              </svg>
            </div>
            <div className="brandText">
              <div className="brandName">MedLedger AI</div>
              <div className="brandTag">Clinical Intelligence</div>
            </div>
          </div>

          {/* Nav */}
          <nav className="nav">
            {[
              { to: '/', label: 'Home', active: isHome },
              { to: '/claim', label: 'Claim Processing', active: isClaim },
              { to: '/flow', label: 'Agent Flow', active: isFlow },
              { to: '/verify', label: 'Verification', active: isVerify },
              { to: '/impact', label: 'Impact', active: isImpact },
              { to: '/rules', label: 'Rules', active: isRules },
            ].map(({ to, label, active }) => (
              <a
                key={to}
                className={`navLink${active ? ' active' : ''}`}
                href={to}
                onClick={(e) => { e.preventDefault(); navigate(to) }}
              >
                {label}
              </a>
            ))}
            <div className="navStatus">
              <span className="navStatusDot" />
              Live
            </div>
          </nav>
        </div>
      </header>

      {/* ── Main Content ── */}
      <main style={{ flex: 1 }}>
        {/* ── HOME ── */}
        {isHome && (
          <>
            {/* Hero */}
            <div className="container">
              <section className="heroSection">
                {/* Left copy */}
                <motion.div
                  className="heroCopy"
                  initial={{ opacity: 0, y: 28 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.55, ease: [0.25, 0.46, 0.45, 0.94] }}
                >
                  <div className="heroEyebrow">
                    <Activity size={12} />
                    Healthcare Claims Intelligence
                  </div>

                  <h1 className="heroTitle">
                    Automate clinical<br />
                    <em>claims processing</em>
                  </h1>

                  <p className="heroSubtitle">
                    Extract diagnoses, map ICD&#8209;10 codes, validate payer rules, and recover denied claims — all in a single auditable pipeline.
                  </p>

                  <div className="heroActions">
                    <Button
                      size="lg"
                      onClick={() => navigate('/claim')}
                    >
                      Start Demo
                      <ChevronRight size={16} />
                    </Button>
                    <Button
                      variant="outline"
                      size="lg"
                      onClick={() => navigate('/flow')}
                    >
                      View Pipeline
                    </Button>
                  </div>

                  {/* Animated stats */}
                  <div className="heroStats" ref={statsRef}>
                    <StatItem value={98} suffix="%" label="Extraction accuracy" start={statsInView} />
                    <StatItem value={70} suffix="K+" label="ICD-10 codes indexed" start={statsInView} />
                    <StatItem value={3} suffix="x" label="Faster than manual" start={statsInView} />
                  </div>
                </motion.div>

                {/* Right visual */}
                <HeroVisualCard />
              </section>
            </div>

            {/* Features */}
            <section className="featuresSection" id="features">
              <div className="container">
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.5 }}
                >
                  <div className="featuresEyebrow">Capabilities</div>
                  <h2 className="featuresTitle">Built for hospital workflows</h2>
                  <p className="featuresSub">
                    A layered clinical intelligence platform combining biomedical NLP, semantic coding, governance, and denial recovery.
                  </p>
                </motion.div>

                <div className="grid3" style={{ marginTop: 36 }}>
                  <FeatureCard
                    icon={Brain}
                    title="Biomedical NLP"
                    body="scispaCy's BC5CDR model extracts diagnoses, procedures, and medications from unstructured physician notes with high clinical accuracy."
                    delay={0}
                  />
                  <FeatureCard
                    icon={FileSearch}
                    title="ICD-10 Semantic Coding"
                    body="Sentence-transformers + FAISS index over 70,000+ codes for semantic similarity search, with RapidFuzz fuzzy matching as fallback."
                    delay={0.08}
                  />
                  <FeatureCard
                    icon={ShieldCheck}
                    title="Payer Rule Validation"
                    body="Evaluate claims against payer-specific guardrails — missing docs, billing constraints, diagnosis-procedure links — with full audit trails."
                    delay={0.16}
                  />
                  <FeatureCard
                    icon={Activity}
                    title="Semantic Verification"
                    body="SVM middleware scores every pipeline stage for source alignment, inter-agent consistency, and reasonability before decisions are made."
                    delay={0.24}
                  />
                  <FeatureCard
                    icon={TrendingUp}
                    title="Denial Recovery"
                    body="Root cause analysis, auto-correction proposals, resubmission generation, and outcome learning — all automated end to end."
                    delay={0.32}
                  />
                  <FeatureCard
                    icon={BarChart3}
                    title="Business Impact Dashboard"
                    body="Track revenue recovered, denial reduction percentage, and automation rate with a real-time KPI dashboard."
                    delay={0.4}
                  />
                </div>
              </div>
            </section>

            {/* Workflow Steps */}
            <section className="workflowSection">
              <div className="container">
                <motion.div
                  initial={{ opacity: 0, y: 18 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.45 }}
                  style={{ textAlign: 'center', marginBottom: 48 }}
                >
                  <div className="featuresEyebrow" style={{ justifyContent: 'center', display: 'flex', marginBottom: 10 }}>
                    Pipeline
                  </div>
                  <h2 className="featuresTitle" style={{ textAlign: 'center' }}>
                    From upload to approval
                  </h2>
                </motion.div>

                <div className="workflowSteps">
                  <WorkflowStep num="1" title="Ingest" desc="Upload PDF, paste text, or scan a handwritten prescription via Gemini Vision." delay={0} />
                  <WorkflowStep num="2" title="Extract & Code" desc="Clinical NLP identifies entities; semantic search maps ICD-10 codes with confidence scores." delay={0.1} />
                  <WorkflowStep num="3" title="Verify & Govern" desc="SVM middleware and policy engine validate quality, consistency, and compliance." delay={0.2} />
                  <WorkflowStep num="4" title="Submit & Recover" desc="Auto-resubmit corrected claims; voice outreach to payers for denied cases." delay={0.3} />
                </div>
              </div>
            </section>
          </>
        )}

        {/* ── INNER PAGES ── */}
        {isClaim && (
          <motion.div
            key="claim"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            <Extract />
          </motion.div>
        )}
        {isFlow && (
          <motion.div key="flow" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
            <PageHeader
              title="Agent Flow Visualization"
              subtitle="Clinical → Coding → Rule → Final with per-agent confidence scores."
              icon={GitBranch}
            />
            <div className="container pageContent">
              <AgentWorkflowPanel view="flow" />
            </div>
          </motion.div>
        )}
        {isVerify && (
          <motion.div key="verify" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
            <PageHeader
              title="Verification & Guardrails"
              subtitle="SVM stage results, governance policy decisions, and audit explanations."
              icon={ShieldCheck}
            />
            <div className="container pageContent">
              <AgentWorkflowPanel view="verification" />
              <div style={{ marginTop: 28 }}>
                <ClaimExplanationPanel />
              </div>
            </div>
          </motion.div>
        )}
        {isImpact && (
          <motion.div
            key="impact"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            <Denials />
          </motion.div>
        )}
        {isRules && (
          <motion.div
            key="rules"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            <Rules />
          </motion.div>
        )}
      </main>

      {/* ── Footer ── */}
      <footer className="footer">
        <div className="container footerInner">
          <div className="footerLeft">
            <div className="brandMark" style={{ width: 26, height: 26, borderRadius: 6 }} aria-hidden="true">
              <svg width="14" height="14" viewBox="0 0 20 20" fill="none">
                <rect x="7.5" y="1" width="5" height="18" rx="1.5" fill="white" />
                <rect x="1" y="7.5" width="18" height="5" rx="1.5" fill="white" />
              </svg>
            </div>
            MedLedger AI
          </div>
          <div>Hospital-grade NLP &nbsp;&middot;&nbsp; ICD-10 Coding &nbsp;&middot;&nbsp; Denial Recovery</div>
        </div>
      </footer>
    </div>
  )
}
